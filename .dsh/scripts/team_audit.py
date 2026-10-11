#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文团队字段审计：校验论文页的 `team` 是否合规。

规则：
    R1 每个论文页必须有非空 team 字段
    R2 team 的每个取值必须是团队词表里的规范名（写了别名会直接给出应写的规范名）
    R3 论文页不得保留旧的 affiliations 字段（已被 team 取代）
    R4 归一化后同名的疑似重复（机构 ↔ 其实验室属正常父子关系，不算）
    R5 frontmatter 结构：team 是合法单行内联列表、必需字段齐全、无孤立块序列

用法：
    python .dsh/scripts/team_audit.py            # 报告 + 退出码（0 = 通过）
    python .dsh/scripts/team_audit.py --stats    # 附带每团队论文数排行
    python .dsh/scripts/team_audit.py --vocab <path>   # 用别的词表文件

出厂状态（还没有论文页）下返回 0 并说明"尚无论文页"，不报错。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import team_vocab as TV  # noqa: E402
from wiki_env import WS, cfg, ensure_utf8_stdio, wiki_dir  # noqa: E402

ensure_utf8_stdio()

PLACEHOLDER = "待确认"
# 论文页 frontmatter 的必需字段（team 的存在性检查在 R1，其余在此兜底）
REQUIRED = ("title", "type", "authors", "year", "venue", "created", "updated", "sources", "questions", "tags")


def paper_dirs() -> list:
    """配置里 type == "paper" 的 wiki 子目录。"""
    types = cfg("wiki_types", default={}) or {}
    subs = [sub for sub, t in types.items() if str(t) == "paper"]
    if not subs:
        subs = ["papers"]
    return [wiki_dir(sub) for sub in subs]


def frontmatter(text: str):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="论文 team 字段审计")
    ap.add_argument("--stats", action="store_true", help="附带每团队论文数排行")
    ap.add_argument("--vocab", default=None, help="用别的团队词表文件")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结论")
    args = ap.parse_args()

    try:
        TV.reload_vocab(args.vocab)
    except TV.VocabError as exc:
        print(exc, file=sys.stderr)
        return 1

    known = set(TV.TEAMS)
    aliases = TV.ALIASES
    counts: Counter = Counter()
    errors: list = []
    warns: list = []
    placeholders: list = []
    pages = []
    for d in paper_dirs():
        if d.is_dir():
            pages.extend(sorted(d.glob("*.md")))

    if not pages:
        print(f"尚无论文页（扫描目录：{', '.join(str(p) for p in paper_dirs())}）—— 团队审计跳过，退出码 0。")
        print("第一次摄入后会自动纳入审计；团队词表登记流程见 TEAMS.md。")
        return 0

    for md in pages:
        text = md.read_text(encoding="utf-8")
        block = frontmatter(text)
        name = md.stem
        if block is None:
            errors.append(f"R5 {name}：无 frontmatter")
            continue
        if re.search(r"^affiliations\s*:", block, re.M):
            errors.append(f"R3 {name}：仍保留 affiliations 字段（应已并入 team）")
        inline = re.search(r"^team:\s*\[(.*)\]\s*$", block, re.M)
        if not inline:
            if re.search(r"^team\s*:", block, re.M):
                errors.append(f"R5 {name}：team 不是单行内联列表")
            else:
                errors.append(f"R1 {name}：缺 team 字段")
            continue
        teams = TV.eval_list(inline.group(1))
        if not teams:
            errors.append(f"R1 {name}：team 为空或无法解析")
            continue
        for t in teams:
            counts[t] += 1
            if t in aliases:
                errors.append(f"R2 {name}：写了别名「{t}」，应写规范名「{aliases[t]}」")
            elif t not in known:
                errors.append(f"R2 {name}：未登记团队「{t}」（需先按 TEAMS.md 登记词表）")
            if t == PLACEHOLDER:
                placeholders.append(name)
        fields = set(re.findall(r"^([a-zA-Z_]+)\s*:", block, re.M))
        missing = [f for f in REQUIRED if f not in fields]
        if missing:
            errors.append(f"R5 {name}：缺字段 {missing}")
        if re.search(r"^team:\s*$", block, re.M):
            errors.append(f"R5 {name}：team 后跟块序列（YAML 会解析失败）")

    # R4 归一化同名（父子的机构↔实验室不算）
    def norm_key(nm: str) -> str:
        base = nm
        if "(" in nm and nm.rstrip().endswith(")"):
            head, _, tail = nm.rpartition("(")
            if any(k in tail for k in ("Laborator", "Lab", "Center", "Centre", "Institute", "Key", "Research")):
                base = head
        keep = [t for t in base.lower().replace("-", " ").replace(",", " ").split()
                if t not in ("the", "of", "and", "for", "in", "at")]
        return " ".join(keep)

    used = [t for t in counts if t != PLACEHOLDER]
    buckets: dict = {}
    for nm in used:
        buckets.setdefault(norm_key(nm), []).append(nm)
    for _, names in buckets.items():
        if len(names) > 1:
            labs = [n for n in names if TV.TEAMS.get(n, {}).get("type") == "实验室"]
            parents = {TV.TEAMS[n]["base"] for n in labs}
            rest = [n for n in names if n not in parents]
            if len(rest) > 1:
                warns.append("R4 归一化后同名（疑似同一团队两种写法）：" + "、".join(rest))

    if not args.quiet:
        print(f"论文页 {len(pages)} ｜ 有 team {len(pages) - sum(1 for e in errors if e.startswith('R1'))} ｜ "
              f"词表规范名 {len(known)} ｜ 被引用 {len(used)}")
        if TV.is_empty() and counts:
            print("  ⚠️ 词表仍为空但有页面写了 team —— 先按 TEAMS.md 登记词表再写页面。")
        if placeholders:
            print(f"\n[占位] {len(placeholders)} 页写的是「{PLACEHOLDER}」（双盲或来源不足，待确认）：")
            for p in placeholders:
                print(f"   - {p}")
        if warns:
            print(f"\n[告警] {len(warns)} 项：")
            for w in warns:
                print("   " + w)
        if errors:
            print(f"\n[错误] {len(errors)} 项：")
            for e in errors:
                print("   " + e)
        if args.stats and counts:
            print("\n=== 每团队论文数（前 25） ===")
            for t, n in counts.most_common(25):
                print(f"  {n:>2}  {t}")

    ok = not errors
    print(f"结论：{'通过（退出码 0）' if ok else '不通过（退出码 1）'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
