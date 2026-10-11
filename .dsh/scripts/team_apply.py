#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把团队映射写进论文页 frontmatter：新增/替换 `team` 字段，并删除旧的 `affiliations`。

用法（默认预演，不写盘）：
    python .dsh/scripts/team_apply.py                     # 预演：只报告将要改动什么
    python .dsh/scripts/team_apply.py --apply             # 写盘（自动备份到 .dsh/tmp/）
    python .dsh/scripts/team_apply.py --mapping <path>    # 指定映射文件
    python .dsh/scripts/team_apply.py --rollback <备份>   # 从备份精确还原

映射文件格式（JSON，键是页面名、值是团队规范名列表）：
    {"CVPR2026-Example": ["Xxx University", "Xxx University (Key Laboratory of Y)"]}

写盘规则：
    * team 一律写成单行内联列表，位置紧跟 `venue` 之后（无 venue 则紧跟 year、再退到末尾）
    * 旧的 `affiliations` 字段（内联或块序列）整个删除——已由 team 取代
    * 每个团队名都必须已在词表登记，否则中止（可用 --allow-unknown 放行，仅限临时排障）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import team_vocab as TV  # noqa: E402
from wiki_env import WS, cfg, ensure_utf8_stdio, tmp_dir, wiki_dir  # noqa: E402

ensure_utf8_stdio()


def paper_dirs() -> list:
    types = cfg("wiki_types", default={}) or {}
    subs = [sub for sub, t in types.items() if str(t) == "paper"] or ["papers"]
    return [wiki_dir(sub) for sub in subs]


def strip_affiliations(block: str) -> str:
    """删掉 affiliations 字段（内联或块序列）。"""
    lines = block.split("\n")
    out, skipping = [], False
    for line in lines:
        if re.match(r"^affiliations\s*:", line):
            skipping = not line.rstrip().endswith("]")
            continue
        if skipping:
            if re.match(r"^\s+-\s+", line):
                continue
            skipping = False
        out.append(line)
    return "\n".join(out)


def set_team(block: str, teams) -> str:
    """写入/替换 team 字段（单行内联列表，紧跟 venue 之后）。"""
    val = "team: [" + ", ".join('"%s"' % t for t in teams) + "]"
    out, skipping = [], False
    for line in block.split("\n"):
        if re.match(r"^team\s*:", line):
            skipping = True           # 旧 team 行与其块序列条目都丢弃
            continue
        if skipping:
            if re.match(r"^\s+-\s+", line):
                continue
            skipping = False
        out.append(line)
    idx = None
    for i, line in enumerate(out):
        if re.match(r"^venue\s*:", line):
            idx = i + 1
            break
    if idx is None:
        for i, line in enumerate(out):
            if re.match(r"^year\s*:", line):
                idx = i + 1
                break
    if idx is None:
        idx = len(out)
    out.insert(idx, val)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="批量写入论文 team 字段")
    ap.add_argument("--mapping", default=None, help="映射 JSON 路径（默认 .dsh/tmp/teams-apply.json）")
    ap.add_argument("--apply", action="store_true", help="实际写盘（默认只预演）")
    ap.add_argument("--rollback", default=None, help="从备份文件还原")
    ap.add_argument("--allow-unknown", action="store_true", help="放行未登记团队名（仅排障用）")
    args = ap.parse_args()

    if args.rollback:
        data = json.loads(pathlib.Path(args.rollback).read_text(encoding="utf-8"))
        pages = {p.stem: p for d in paper_dirs() for p in d.glob("*.md")}
        n = 0
        for name, text in (data.get("pages") or {}).items():
            if name in pages:
                pages[name].write_text(text, encoding="utf-8", newline="\n")
                n += 1
        print(f"[还原] {n} 页已写回（备份：{args.rollback}）")
        return 0

    try:
        TV.reload_vocab()
    except TV.VocabError as exc:
        print(exc, file=sys.stderr)
        return 1

    mapping_path = pathlib.Path(args.mapping) if args.mapping else (tmp_dir() / "teams-apply.json")
    if not mapping_path.is_file():
        print(f"找不到映射文件：{mapping_path}\n"
              "先准备 JSON：{\"页面名\": [\"团队规范名\", ...]}，或用 --mapping 指定路径。", file=sys.stderr)
        return 1
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        print("映射文件的根节点必须是对象：页面名 → 团队列表", file=sys.stderr)
        return 1

    unknown = [(p, t) for p, ts in mapping.items() for t in ts if t not in TV.TEAMS]
    if unknown and not args.allow_unknown:
        print("[中止] 映射里有未登记的团队名（先按 TEAMS.md 登记词表）：", file=sys.stderr)
        for p, t in unknown:
            print(f"   {p} -> {t}", file=sys.stderr)
        return 1

    pages = {p.stem: p for d in paper_dirs() for p in d.glob("*.md")}
    missing = [p for p in mapping if p not in pages]
    if missing:
        print(f"[中止] 映射里的页面不存在：{missing}", file=sys.stderr)
        return 1

    backup = {"applied_at": datetime.now().isoformat(timespec="seconds"), "pages": {}}
    changed = 0
    for page, teams in sorted(mapping.items()):
        path = pages[page]
        text = path.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
        if not m:
            print(f"[跳过] {page}：无 frontmatter")
            continue
        block = m.group(1)
        had_aff = bool(re.search(r"^affiliations\s*:", block, re.M))
        new_text = text[: m.start(1)] + set_team(strip_affiliations(block), teams) + text[m.end(1):]
        if new_text == text:
            continue
        changed += 1
        print(f"{'[写]' if args.apply else '[预演]'} {page}：team={len(teams)} 条"
              + ("，删除 affiliations" if had_aff else ""))
        backup["pages"][page] = text
        if args.apply:
            path.write_text(new_text, encoding="utf-8", newline="\n")

    print(f"\n{'已写盘' if args.apply else '预演完成'}：{changed} 页需要改动，{len(mapping)} 页在映射中")
    if args.apply and changed:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = tmp_dir() / f"teams-backup-{ts}.json"
        out.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"备份：{out}（可用 --rollback 还原）")
    elif not args.apply:
        print("确认无误后加 --apply 写盘。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
