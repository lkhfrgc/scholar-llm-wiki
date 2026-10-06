#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迁移验证：拿 tags 备份 → 按当前词表重新推导 → 与磁盘实际 tags 逐页比对。

用途：在批量改写 tag（`tag_apply.py --apply`）之后，独立确认磁盘内容确实等于
「原始 tags 经 `map` 映射 + `page_overrides` 修剪」的预期结果——不依赖 tag_apply 自己的报告。

同时检查三件易被忽略的事：
  1. 角色 tag（母概念/子概念）是否仍在 tags 首位（画布生成脚本依赖）；
  2. 正文里是否被误插了 `tags:` 行；
  3. 文件行尾是否被改乱（CRLF 文件不得出现裸 LF）。

用法：
    python .dsh/scripts/tag_verify_migration.py                 # 用最新的备份
    python .dsh/scripts/tag_verify_migration.py --backup <路径>
    python .dsh/scripts/tag_verify_migration.py --list          # 列出可用备份

退出码：0 = 全部一致；1 = 存在不一致。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio, tmp_dir  # noqa: E402
import tag_vocab as V  # noqa: E402

ensure_utf8_stdio()

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)


def parse_fm_tags(fm: str) -> list:
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


def wiki_root(root: Path) -> Path:
    """wiki 目录名来自配置，不写死字面量。"""
    return root / cfg("dirs", "wiki", default="wiki")


def backup_root(root: Path) -> Path:
    """备份目录：默认工作区用 wiki_env 解析结果；`--root` 指定别的库时按同一配置项拼。"""
    if root == WS:
        return tmp_dir()
    rel = Path(cfg("dirs", "tmp", default=".dsh/tmp"))
    return rel if rel.is_absolute() else (root / rel)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="独立验证 tag 迁移结果（备份 → 重新推导 → 与磁盘比对）。",
        epilog="示例: python .dsh/scripts/tag_verify_migration.py --list",
    )
    ap.add_argument("--backup", default=None, help="指定备份 JSON（默认用最新的一个）")
    ap.add_argument("--list", action="store_true", help="只列出可用备份")
    ap.add_argument("--root", default=None, help="改用别的工作区根（默认取 wiki_env 解析结果）")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结论")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    root = Path(args.root).resolve() if args.root else WS
    backups = sorted(backup_root(root).glob("tags-backup-*.json"))

    if args.list:
        for b in backups:
            n = len(json.loads(b.read_text(encoding="utf-8")).get("files", {}))
            print(f"{b.name}   条目 {n}")
        return 0

    try:
        V.require_vocab()
    except V.VocabError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if not backups:
        print("找不到任何 tags-backup-*.json，无法验证。")
        return 1
    bk_path = Path(args.backup) if args.backup else backups[-1]
    bk = json.loads(bk_path.read_text(encoding="utf-8"))["files"]
    if not args.quiet:
        print(f"使用备份: {bk_path.name}   条目 {len(bk)}")

    errors: list = []
    n_ok = 0
    for rel, old_tags in bk.items():
        p = root / rel
        if not p.exists():
            errors.append(f"{rel}: 文件不存在")
            continue
        text = p.read_bytes().decode("utf-8")
        m = FM_RE.match(text)
        if not m:
            errors.append(f"{rel}: frontmatter 丢失")
            continue
        actual = parse_fm_tags(m.group(1))
        expect = V.translate(old_tags, rel)
        if actual == expect:
            n_ok += 1
        else:
            errors.append(f"{rel}\n    期望 {expect}\n    实际 {actual}")
        roles = [t for t in actual if t in V.ROLE_TAGS]
        if roles and actual[0] not in V.ROLE_TAGS:
            errors.append(f"{rel}: 角色 tag 不在首位 -> {actual}")

    if not args.quiet:
        print(f"逐页一致: {n_ok} / {len(bk)}   不一致: {len(bk) - n_ok}")

    body_bad = [
        f.relative_to(root).as_posix()
        for f in sorted(wiki_root(root).rglob("*.md"))
        if (lambda t: re.search(r"(?m)^tags:", t[FM_RE.match(t).end():] if FM_RE.match(t) else t))(
            f.read_bytes().decode("utf-8"))
    ]
    if not args.quiet:
        print(f"正文内误插 tags 行: {len(body_bad)} {body_bad}")

    mixed = []
    for f in sorted(wiki_root(root).rglob("*.md")):
        b = f.read_bytes()
        if b"\r\n" in b and b"\n" in b.replace(b"\r\n", b""):
            mixed.append(f.relative_to(root).as_posix())
    if not args.quiet:
        print(f"行尾混用的页面: {len(mixed)} {mixed[:5]}")
    if mixed:
        errors.append(f"行尾混用: {mixed}")

    if errors:
        print(f"\n✗ {len(errors)} 项失败：")
        for e in errors[:20]:
            print("  ", e)
        return 1
    if args.quiet:
        print(f"验证通过 ✓  逐页一致 {n_ok}/{len(bk)}")
    else:
        print("\n全部验证通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
