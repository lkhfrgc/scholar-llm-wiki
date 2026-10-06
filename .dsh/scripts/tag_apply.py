#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按受控词表批量改写 wiki 页面的 frontmatter `tags:` 字段。

用法：
    python .dsh/scripts/tag_apply.py                          # 预演（只报告，不写盘）
    python .dsh/scripts/tag_apply.py --apply                  # 实际写入，并生成备份
    python .dsh/scripts/tag_apply.py --rollback <备份.json>    # 从备份还原

设计要点：
  * 只改 `tags:` 那一行，其余字节原样保留（用 read_bytes/write_bytes，避免换行符被归一化）。
  * 角色 tag（母概念/子概念）由 `tag_vocab.order_tags` 保证仍位于首位。
  * 未登记的 tag 会报错并中止，绝不静默丢弃。
  * 扫描范围、备份目录全部来自 `wiki_env`：扫 `<WS>/<dirs.wiki>`，备份写 `<WS>/<dirs.tmp>`。

退出码：
    0 = 无需改写或已成功写盘；2 = 存在未登记的 tag（中止）；3 = 存在硬性违规（未写盘）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio, tmp_dir  # noqa: E402
import tag_vocab as V  # noqa: E402

ensure_utf8_stdio()

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
# 用 [^\r\n]* 而非 .*：显式排除 CR，保证 CRLF 文件的 tags 行仍以 \r\n 结尾
# （若用 .* 则 \r 会被吞进匹配，替换后该行变成裸 LF → 文件行尾混用）
TAGS_LINE_RE = re.compile(r"(?m)^tags:[ \t]*[^\r\n]*")
TAGS_BLOCK_RE = re.compile(r"(?m)^tags:[ \t]*(?:\r?\n[ \t]*-[ \t]*[^\r\n]*)+")
MAX_TOPIC = 8       # 硬上限
MIN_TOPIC = 1       # 硬下限（禁止 0 个主题 tag）
RECOMMEND = (3, 5)  # 推荐区间
FACET_CAP = {       # 分面软上限（超出仅提示）
    "domain": 2, "task": 4, "modality": 4, "method": 6,
    "challenge": 4, "data": 2, "meta": 2,
}


def parse_tags_from_fm(fm: str) -> list:
    """从 frontmatter 文本里解析 tags（兼容内联列表与块序列）。"""
    m = re.search(r"(?m)^tags:[ \t]*(.*)$", fm)
    if not m:
        return []
    line = m.group(1).strip()
    if line and line not in ("|", ">"):
        body = line.strip("[]")
        return [t.strip().strip("'\"") for t in body.split(",") if t.strip()]
    # 块序列
    out = []
    tail = fm[m.end():]
    for ln in tail.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            out.append(s[2:].strip().strip("'\""))
        elif s:
            break
    return out


def wiki_root(root: Path) -> Path:
    """root 下的 wiki 目录名来自配置，不写死字面量。"""
    return root / cfg("dirs", "wiki", default="wiki")


def tmp_root(root: Path) -> Path:
    """备份目录：默认工作区用 wiki_env 解析结果；`--root` 指定别的库时按同一配置项拼。"""
    if root == WS:
        return tmp_dir()
    rel = Path(cfg("dirs", "tmp", default=".dsh/tmp"))
    return rel if rel.is_absolute() else (root / rel)


def collect(root: Path) -> list:
    return sorted(wiki_root(root).rglob("*.md"))


def analyze(root: Path):
    rows, unmapped = [], defaultdict(list)
    for f in collect(root):
        raw = f.read_bytes()
        text = raw.decode("utf-8")
        m = FM_RE.match(text)
        rel = f.relative_to(root).as_posix()
        if not m:
            rows.append(dict(file=rel, old=[], new=[], note="无 frontmatter"))
            continue
        fm = m.group(1)
        old = parse_tags_from_fm(fm)
        try:
            new = V.translate(old, rel)
        except KeyError as e:
            for t in re.findall(r"'([^']+)'", str(e)):
                unmapped[t].append(rel)
            new = []
        rows.append(dict(file=rel, old=old, new=new))
    return rows, unmapped


def lint_rows(rows):
    hard, soft = [], []
    for r in rows:
        topic = [t for t in r["new"] if t not in V.ROLE_TAGS]
        if len(topic) > MAX_TOPIC:
            hard.append(f"{r['file']}: 主题 tag {len(topic)} 个 > {MAX_TOPIC}")
        if r["new"] and len(topic) < MIN_TOPIC:
            hard.append(f"{r['file']}: 主题 tag {len(topic)} 个 < {MIN_TOPIC}")
        if r["new"] and len(topic) < RECOMMEND[0]:
            soft.append(f"{r['file']}: 主题 tag 仅 {len(topic)} 个（推荐 {RECOMMEND[0]}–{RECOMMEND[1]}）")
        per = Counter(t.split("/", 1)[0] for t in topic if "/" in t)
        for facet, n in per.items():
            if n > FACET_CAP.get(facet, 3):
                soft.append(f"{r['file']}: 分面 {facet}/ 有 {n} 个 > 软上限 {FACET_CAP.get(facet, 3)}")
    return hard, soft


def rewrite(text: str, new_tags: list) -> str:
    """把 frontmatter 里的 tags 行替换为新的内联列表。"""
    m = FM_RE.match(text)
    if not m:
        return text
    fm = m.group(1)
    line = "tags: [" + ", ".join(new_tags) + "]"
    if TAGS_LINE_RE.search(fm):
        # 先处理块序列，再处理单行
        if TAGS_BLOCK_RE.search(fm):
            new_fm = TAGS_BLOCK_RE.sub(lambda _: line, fm, count=1)
        else:
            new_fm = TAGS_LINE_RE.sub(lambda _: line, fm, count=1)
    else:
        new_fm = fm + "\n" + line
    return text[:m.start(1)] + new_fm + text[m.end(1):]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="按受控词表迁移 wiki 页面的 tags（默认预演）。",
        epilog="示例: python .dsh/scripts/tag_apply.py --apply",
    )
    ap.add_argument("--apply", action="store_true", help="实际写盘（默认只预演）")
    ap.add_argument("--rollback", default=None, help="从 tags 备份 JSON 还原（不读词表）")
    ap.add_argument("--root", default=None, help="改用别的工作区根（默认取 wiki_env 解析结果）")
    ap.add_argument("--report", default=None, help="把对照报告写入该路径")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结论")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    root = Path(args.root).resolve() if args.root else WS

    # ---------------- 回滚 ----------------
    if args.rollback:
        bk = json.loads(Path(args.rollback).read_text(encoding="utf-8"))
        n = 0
        for rel, old_line in bk["files"].items():
            p = root / rel
            text = p.read_bytes().decode("utf-8")
            p.write_bytes(rewrite(text, old_line).encode("utf-8"))
            n += 1
        print(f"已回滚 {n} 个文件 -> {args.rollback}")
        return 0

    try:
        V.require_vocab()
    except V.VocabError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    rows, unmapped = analyze(root)

    if unmapped:
        print("✗ 存在未登记的 tag，已中止：")
        for t, files in sorted(unmapped.items()):
            print(f"  {t}  ({len(files)} 处, 例: {files[0]})")
        print("\n请在 `.dsh/tag-vocab.json` 的 `map` 中登记来源词后重试。")
        return 2

    changed = [r for r in rows if r["old"] != r["new"]]
    hard, soft = lint_rows(rows)

    tag_counter = Counter(t for r in rows for t in r["new"] if t not in V.ROLE_TAGS)
    dist = Counter(len([t for t in r["new"] if t not in V.ROLE_TAGS]) for r in rows)
    lines = []
    lines.append(f"# Tag 迁移报告  ({len(rows)} 页)")
    lines.append("")
    lines.append(f"- 需改写页面: **{len(changed)}** / {len(rows)}")
    lines.append(f"- 迁移后不同 tag: **{len(tag_counter)}**（词表容量 {len(V.all_canonical_tags())}）")
    lines.append("- 主题 tag 数分布: " + ", ".join(f"{k}个×{v}页" for k, v in sorted(dist.items())))
    lines.append(f"- 平均主题 tag/页: {sum(len([t for t in r['new'] if t not in V.ROLE_TAGS]) for r in rows) / max(len(rows), 1):.2f}")
    lines.append("")
    lines.append("## 规范 tag 使用频次")
    lines.append("")
    for t, c in sorted(tag_counter.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- `{t}` × {c}")
    lines.append("")
    lines.append(f"## 硬性违规 ({len(hard)})")
    lines.append("")
    for w in hard:
        lines.append(f"- ✗ {w}")
    lines.append("")
    lines.append(f"## 软性提示 ({len(soft)})")
    lines.append("")
    for w in soft:
        lines.append(f"- {w}")
    lines.append("")
    lines.append("## 逐页对照")
    lines.append("")
    for r in changed:
        lines.append(f"### {r['file']}")
        lines.append(f"- 旧: `{', '.join(r['old'])}`")
        lines.append(f"- 新: `{', '.join(r['new'])}`")
    text = "\n".join(lines)

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        if not args.quiet:
            print(f"[report] -> {args.report}")

    if hard:
        if args.quiet:
            print(f"✗ 硬性违规 {len(hard)} 项，已中止（需改写 {len(changed)}/{len(rows)}）")
        else:
            print(f"需改写: {len(changed)}/{len(rows)}   规范 tag: {len(tag_counter)}   硬性违规: {len(hard)}   软提示: {len(soft)}")
            print("✗ 存在硬性违规，请先修正（见报告）：")
            for w in hard:
                print("   ", w)
        return 3

    if not args.apply:
        if args.quiet:
            print(f"预演完成：需改写 {len(changed)}/{len(rows)}，未写盘")
        else:
            print(f"需改写: {len(changed)}/{len(rows)}   规范 tag: {len(tag_counter)}   硬性违规: 0   软提示: {len(soft)}")
            print("（预演模式，未写盘。加 --apply 实际执行）")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = tmp_root(root) / f"tags-backup-{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    bk = {"stamp": stamp, "files": {}}
    for r in changed:
        p = root / r["file"]
        text = p.read_bytes().decode("utf-8")
        bk["files"][r["file"]] = r["old"]
        p.write_bytes(rewrite(text, r["new"]).encode("utf-8"))
        n += 1
    backup.write_text(json.dumps(bk, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {n} 个文件；备份 -> {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
