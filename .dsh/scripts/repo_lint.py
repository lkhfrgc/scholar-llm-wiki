#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""repo_lint —— 提交前的「泄露与格式」自检。

知识库是要长期版本化的东西，很容易在某个深夜把本机路径、用户名或凭据
顺手写进配置、脚本或笔记里。这个脚本把这类事故变成一条退出码。

检查项：
  1. 绝对路径     盘符路径、POSIX 家目录、UNC 网络路径   <!-- repo-lint:ignore -->
  2. 用户目录     `Users\<具体用户名>`（`%USERPROFILE%`、`$HOME`、`~` 不算）
  3. 邮箱地址
  4. 疑似凭据     常见 token 前缀、私钥 PEM 头
  5. UTF-8 BOM    BOM 会让 frontmatter 首行变成 `\ufeff---`，整个页面被判为「无 frontmatter」
  6. JSON 可解析
  7. Python 可编译

命中行若带 `repo-lint:ignore` 标记则豁免（文档需要展示"路径的形状"时用）。

默认跳过 `.git/`、`.dsh/venv/`、`.dsh/tmp/`、`__pycache__/` 与二进制文件。

用法：
    python .dsh/scripts/repo_lint.py                 # 扫工作区
    python .dsh/scripts/repo_lint.py --root <目录>    # 扫指定目录
    python .dsh/scripts/repo_lint.py --json out.json  # 机器可读
    python .dsh/scripts/repo_lint.py --quiet          # 只输出一行

退出码：0 = 干净；1 = 发现问题；2 = 用法错误。
"""
from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, ensure_utf8_stdio  # noqa: E402

SKIP_DIRS = {".git", "venv", "__pycache__", "node_modules", ".obsidian", ".idea", ".vscode"}
SKIP_REL_PREFIX = (".dsh/tmp", ".dsh/venv")
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz", ".7z", ".tar",
    ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyd", ".woff", ".woff2", ".ttf",
    ".mp3", ".mp4", ".wav", ".xlsx", ".docx", ".pptx", ".canvas",
}

PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("drive-path", "盘符绝对路径", re.compile(r"\b[A-Za-z]:[\\/](?![/\\])")),
    ("posix-home", "POSIX 家目录绝对路径", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")),
    ("unc-path", "UNC 网络路径", re.compile(r"\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9$._-]+")),
    ("win-user", "Windows 用户名", re.compile(r"(?i)\busers[\\/]([A-Za-z0-9._-]+)")),
    ("email", "邮箱地址", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("token", "疑似凭据", re.compile(
        r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}"
        r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b")),
    ("pem", "私钥 PEM 头", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# 这些"用户名"是文档里的通用占位/系统账户，不算泄露
BENIGN_USERS = {
    "your-name", "username", "user", "name", "me", "you", "example", "public",
    "shared", "all users", "default", "administrator", "admin", "runner",
    "your_user", "youruser", "<user>", "$user", "%username%", "...",
}


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if rel.startswith(SKIP_REL_PREFIX):
            continue
        yield p, rel


def scan_text(rel: str, text: str, findings: list[dict]) -> None:
    """逐条正则扫描；命中行若带 `repo-lint:ignore` 标记则放行。

    文档有时必须展示"路径的形状"（例如本脚本自己的说明），
    这类行加上 `repo-lint:ignore`（HTML 注释或行内注释都行）即可豁免，
    避免为了绕过扫描而把说明写歪。
    """
    lines = text.splitlines()
    for pid, label, rx in PATTERNS:
        for m in rx.finditer(text):
            hit = m.group(0)
            if pid == "win-user" and m.group(1).lower() in BENIGN_USERS:
                continue
            lineno = text.count("\n", 0, m.start()) + 1
            if 1 <= lineno <= len(lines) and "repo-lint:ignore" in lines[lineno - 1]:
                continue
            findings.append({"file": rel, "line": lineno, "kind": pid, "label": label, "match": hit})


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description="知识库仓库的泄露与格式自检")
    ap.add_argument("--root", default=None, help="要扫描的目录（默认：工作区根）")
    ap.add_argument("--json", dest="json_out", default=None, help="把结果写入 JSON 文件")
    ap.add_argument("--quiet", action="store_true", help="只输出一行总结")
    ap.add_argument("--max-hits", type=int, default=200, help="最多报告多少条命中")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else WS
    if not root.is_dir():
        print(f"错误：目录不存在 {root}", file=sys.stderr)
        return 2

    findings: list[dict] = []
    checked = 0
    for p, rel in iter_files(root):
        if p.suffix.lower() in BINARY_EXT:
            continue
        checked += 1
        try:
            raw = p.read_bytes()
        except OSError as exc:
            findings.append({"file": rel, "line": 0, "kind": "io", "label": "读取失败", "match": str(exc)})
            continue

        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append({"file": rel, "line": 1, "kind": "bom", "label": "UTF-8 BOM", "match": "\\ufeff"})

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue  # 非文本，跳过内容规则

        scan_text(rel, text, findings)

        if p.suffix == ".json":
            try:
                json.loads(text)
            except Exception as exc:
                findings.append({"file": rel, "line": 0, "kind": "json", "label": "JSON 解析失败", "match": str(exc)[:120]})

        if p.suffix == ".py":
            pyc_dir = Path(__file__).resolve().parent.parent / "tmp"
            try:
                pyc_dir.mkdir(parents=True, exist_ok=True)
                py_compile.compile(str(p), doraise=True, cfile=str(pyc_dir / "_repo_lint.pyc"))
            except Exception as exc:  # PyCompileError / OSError / ValueError(null byte) …
                findings.append({"file": rel, "line": 0, "kind": "python", "label": "Python 编译失败",
                                 "match": str(exc).splitlines()[0][:160]})

    # 合成报告
    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1

    report = {"root": str(root), "files_scanned": checked, "total": len(findings), "by_kind": by_kind,
              "findings": findings[: args.max_hits]}

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.quiet:
        print(f"repo_lint: 扫描 {checked} 个文件，发现 {len(findings)} 处问题")
    else:
        print(f"扫描目录：{root}")
        print(f"文本文件：{checked}    命中：{len(findings)}")
        if findings:
            print()
            for f in findings[: args.max_hits]:
                loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
                print(f"  ✗ [{f['kind']}] {loc}  {f['label']}: {f['match']}")
            if len(findings) > args.max_hits:
                print(f"  … 另有 {len(findings) - args.max_hits} 条未显示")
        else:
            print("\n✓ 未发现绝对路径、用户名、凭据、BOM 或格式问题")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
