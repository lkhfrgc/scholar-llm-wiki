#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tag 审计：扫描 wiki 全部页面，统计 frontmatter tags 使用情况并对照受控词表。

用法:
  python .dsh/scripts/tag_audit.py                     # 控制台报告
  python .dsh/scripts/tag_audit.py --report out.md     # 报告写入文件
  python .dsh/scripts/tag_audit.py --json out.json     # 机器可读全量数据
  python .dsh/scripts/tag_audit.py --unregistered      # 只列出未登记进词表的 tag

退出码：0 = 全部合规；1 = 存在未登记 tag 或硬性违规。

扫描范围与目录名来自 `wiki_env`（`dirs.wiki`），报告写到调用方指定的路径。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio  # noqa: E402
import tag_vocab as V  # noqa: E402

ensure_utf8_stdio()

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
# 正文里的内联 #tag。经验：只认「小写字母开头且含连字符」的形态，
# 否则表格与图注里的短标记（#P、#A1 之类）会被误报成 tag。
INLINE_TAG_RE = re.compile(r"(?<![\w/\[#])#([a-z][a-z0-9]+(?:-[a-z0-9]+)+|母概念|子概念)")

MAX_TOPIC = 8
FACET_CAP = {"domain": 2, "task": 4, "modality": 4, "method": 6,
             "challenge": 4, "data": 2, "meta": 2}


def wiki_root(root: Path) -> Path:
    """wiki 目录名来自配置，不写死字面量。"""
    return root / cfg("dirs", "wiki", default="wiki")


def parse_tags_from_fm(fm: str) -> list:
    """解析 frontmatter 的 tags：兼容 `tags: [a, b]` 与 YAML 块序列两种写法。"""
    m = re.search(r"(?m)^tags:[ \t]*(.*)$", fm)
    if not m:
        return []
    line = m.group(1).strip()
    if line and line not in ("|", ">"):
        return [t.strip().strip("'\"") for t in line.strip("[]").split(",") if t.strip()]
    out = []
    for ln in fm[m.end():].splitlines():
        s = ln.strip()
        if s.startswith("- "):
            out.append(s[2:].strip().strip("'\""))
        elif s:
            break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="审计 wiki 页面的 tag 使用情况（对照受控词表）。",
        epilog="示例: python .dsh/scripts/tag_audit.py --json .dsh/tmp/audit.json",
    )
    ap.add_argument("--json", default=None, help="把机器可读的全量数据写入该路径")
    ap.add_argument("--report", default=None, help="把 Markdown 报告写入该路径")
    ap.add_argument("--unregistered", action="store_true", help="只列出未登记的 tag")
    ap.add_argument("--root", default=None, help="改用别的工作区根（默认取 wiki_env 解析结果）")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结论")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        V.require_vocab()
    except V.VocabError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    root = Path(args.root).resolve() if args.root else WS
    files = sorted(wiki_root(root).rglob("*.md"))

    known = set(V.canonical_by_name())
    tag_files: dict = defaultdict(list)
    file_tags: dict = {}
    unregistered: dict = defaultdict(list)
    type_counter: Counter = Counter()
    inline_hits: dict = defaultdict(list)
    block_style: list = []
    hard: list = []
    soft: list = []
    no_fm: list = []

    for f in files:
        rel = f.relative_to(root).as_posix()
        text = f.read_bytes().decode("utf-8")
        m = FM_RE.match(text)
        if not m:
            no_fm.append(rel)
            file_tags[rel] = []
            continue
        fm = m.group(1)
        tags = parse_tags_from_fm(fm)
        dedup: list = []
        for t in tags:
            if t not in dedup:
                dedup.append(t)
        file_tags[rel] = dedup
        for t in dedup:
            tag_files[t].append(rel)
            if t not in known:
                unregistered[t].append(rel)
        tm = re.search(r"(?m)^type:\s*(.+)$", fm)
        type_counter[tm.group(1).strip().strip("'\"") if tm else "(缺失)"] += 1
        seg = re.search(r"(?ms)^tags:(.*?)(?=^\S|\Z)", fm)
        if seg and re.search(r"(?m)^\s+-", seg.group(1)):
            block_style.append(rel)

        topic = [t for t in dedup if t not in V.ROLE_TAGS]
        if len(topic) > MAX_TOPIC:
            hard.append(f"{rel}: 主题 tag {len(topic)} 个 > {MAX_TOPIC}")
        if not topic:
            hard.append(f"{rel}: 无主题 tag")
        per = Counter(t.split("/", 1)[0] for t in topic if "/" in t)
        for facet, n in per.items():
            if n > FACET_CAP.get(facet, 3):
                soft.append(f"{rel}: 分面 {facet}/ {n} 个 > 软上限 {FACET_CAP.get(facet, 3)}")
        if len(topic) < 3:
            soft.append(f"{rel}: 主题 tag 仅 {len(topic)} 个（推荐 3–5）")

        for it in set(INLINE_TAG_RE.findall(text[m.end():])):
            inline_hits[it].append(rel)

    n_files = len(files)
    L: list = []
    L.append(f"# Tag 审计报告  ({n_files} 个页面)")
    L.append("")
    cold = V.is_cold_start()
    L.append(f"- 不同 tag 总数: **{len(tag_files)}**（词表容量 {len(known)}）")
    L.append("- 词表状态: " + ("**冷启动** —— `canonical` 为空，词表尚未建立" if cold
                              else f"已建立（{len(known)} 条规范 tag）"))
    L.append(f"- 未登记 tag: **{len(unregistered)}**"
             + ("（冷启动阶段，属预期）" if cold and unregistered else ""))
    L.append(f"- type 分布: " + ", ".join(f"{k} {v}" for k, v in type_counter.most_common()))
    L.append(f"- frontmatter 缺失: {len(no_fm)}" + (f"  {no_fm}" if no_fm else ""))
    L.append(f"- 块序列写法（建议统一为内联）: {len(block_style)}")
    dist = Counter(len([t for t in v if t not in V.ROLE_TAGS]) for v in file_tags.values())
    L.append("- 主题 tag 数分布: " + ", ".join(f"{k}个×{v}页" for k, v in sorted(dist.items())))
    L.append("")
    if unregistered and cold:
        L.append(f"## ⚠ 待登记进词表 ({len(unregistered)}) —— 冷启动阶段，这不是错误")
        L.append("")
        L.append("出厂词表是空的，所以页面上的每个 tag 都会出现在这里。**冷启动阶段免于")
        L.append("「≥3 个页面」门槛**，但必须在本次 ingest 收尾前把它们登记进")
        L.append("`.dsh/tag-vocab.json`：`canonical` 加 `叶节点: 中文释义`，`map` 里登记来源词。")
        L.append("登记完重跑本命令，退出码就回到 0。详见 `TAGS.md` 的「冷启动」一节。")
        L.append("")
        for t, v in sorted(unregistered.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            L.append(f"- `{t}` × {len(v)}  — 例: {v[0]}")
        L.append("")
    elif unregistered:
        L.append(f"## ✗ 未登记 tag ({len(unregistered)})")
        L.append("")
        for t, v in sorted(unregistered.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            L.append(f"- `{t}` × {len(v)}  — 例: {v[0]}")
        L.append("")
    if hard:
        L.append(f"## ✗ 硬性违规 ({len(hard)})")
        L.append("")
        L += [f"- {w}" for w in hard]
        L.append("")
    if soft:
        L.append(f"## 软性提示 ({len(soft)})")
        L.append("")
        L += [f"- {w}" for w in soft]
        L.append("")
    L.append("## tag 使用频次")
    L.append("")
    for t, v in sorted(tag_files.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        mark = "" if t in known else "  ✗未登记"
        L.append(f"| `{t}` | {len(v)} |{mark}")
    L.append("")
    if inline_hits:
        L.append("## 正文内联 #tag")
        L.append("")
        for t, v in sorted(inline_hits.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            L.append(f"- `#{t}` × {len(v)}  — 例: {v[0]}")
    text = "\n".join(L)

    if args.unregistered:
        for t, v in sorted(unregistered.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"{len(v):3d}  {t}   ({v[0]})")
        return 1 if unregistered else 0

    if args.quiet:
        ok = not unregistered and not hard
        print(f"审计{'通过 ✓' if ok else '未通过'}  页面 {n_files}  未登记 {len(unregistered)}   "
              f"硬性违规 {len(hard)}   词表{'冷启动' if cold else '已建立'}")
    else:
        print(text)
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        if not args.quiet:
            print(f"\n[report] -> {args.report}")
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "n_files": n_files,
            "cold_start": cold,
            "tag_counts": {t: len(v) for t, v in tag_files.items()},
            "tag_files": dict(tag_files),
            "file_tags": file_tags,
            "unregistered": dict(unregistered),
            "types": dict(type_counter),
            "block_style": block_style,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"[json] -> {args.json}")
    ok = not unregistered and not hard
    if not args.quiet:
        msg = "审计通过 ✓" if ok else f"审计未通过：未登记 {len(unregistered)}，硬性违规 {len(hard)}"
        if not ok and cold and not hard:
            msg += "　（冷启动：把上面这些词登记进 .dsh/tag-vocab.json 即可，不用删 tag）"
        print("\n" + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
