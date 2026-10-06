#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_wiki —— 一键初始化知识库骨架（幂等，绝不覆盖已有内容）。

做五件事：
  1. 按 `.dsh/wiki.config.json` 建目录骨架（wiki/ 五个子目录、raw/ 收件箱与归档区）
  2. 从 `templates/` 生成缺失的 `index.md` / `log.md`（已存在则跳过，原样保留）
  3. 用词表引擎生成 `TAGS.md`（`.dsh/tag-vocab.json` 缺失时从模板复制一份）
  4. 生成初始画布（总图），让一装完 `gen_canvas.py --check` 就是绿的
  5. 可选：创建项目 venv 并安装 `PyMuPDF`（PDF 正文抽取才需要）

用法：
    python .dsh/scripts/setup_wiki.py                 # 初始化（幂等，可反复跑）
    python .dsh/scripts/setup_wiki.py --dry-run       # 只报告将要做什么
    python .dsh/scripts/setup_wiki.py --venv          # 顺带建 venv 并装 requirements
    python .dsh/scripts/setup_wiki.py --force         # 覆盖 index.md / log.md（危险）

退出码：0 = 完成（含"本来就是好的"）；1 = 有步骤失败；2 = 用法错误。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import (  # noqa: E402
    CONFIG_PATH,
    WS,
    archive_dir,
    cfg,
    ensure_utf8_stdio,
    script_path,
    tmp_dir,
    wiki_dir,
)

# --------------------------------------------------------------------------
# 内置兜底模板：即使没有 templates/ 目录（用户只拷了 .dsh/）也能初始化
# --------------------------------------------------------------------------
FALLBACK_INDEX = """# Wiki Index

> 本文件是知识库的唯一总目录，由 AI 在每次 ingest / query 后维护。
> 小节名固定为下面五个，不要新增段落。

## Papers

## Concepts

## Connections

## Questions

## Syntheses
"""

FALLBACK_LOG = """# 操作日志

> **Append-only：只能在文件顶部追加，绝不覆盖或删除已有记录。**
> 操作类型只允许 `ingest` / `query` / `lint` 三种。
"""


def _templates_dir() -> Path:
    """模板目录：优先用工作区根的 templates/，其次用仓库内的 templates/。"""
    for cand in (WS / "templates", Path(__file__).resolve().parents[2] / "templates"):
        if cand.is_dir():
            return cand
    return WS / "templates"


class Report:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.created: list[str] = []
        self.skipped: list[str] = []
        self.failed: list[str] = []

    def _rel(self, p: Path) -> str:
        try:
            return p.relative_to(WS).as_posix()
        except ValueError:
            return str(p)

    def mkdir(self, p: Path) -> None:
        rel = self._rel(p) + "/"
        if p.is_dir():
            self.skipped.append(rel)
            return
        if not self.dry_run:
            p.mkdir(parents=True, exist_ok=True)
        self.created.append(rel)

    def write(self, p: Path, text: str, force: bool = False) -> None:
        rel = self._rel(p)
        if p.exists() and not force:
            self.skipped.append(rel)
            return
        if not self.dry_run:
            p.parent.mkdir(parents=True, exist_ok=True)
            # 统一 LF：Obsidian 与 git 对 LF 最友好；newline= 参数在 3.9 不存在，故手写
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        self.created.append(rel)

    def copy(self, src: Path, dst: Path, force: bool = False) -> None:
        rel = self._rel(dst)
        if dst.exists() and not force:
            self.skipped.append(rel)
            return
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        self.created.append(rel)

    def fail(self, what: str) -> None:
        self.failed.append(what)


def _read_template(tpl: Path, name: str, fallback: str) -> str:
    p = tpl / name
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            pass
    return fallback


def build_skeleton(rep: Report) -> None:
    """按配置建目录骨架。wiki 子目录取自 wiki_types 的键，保证与 type 校验一致。"""
    rep.mkdir(wiki_dir())
    for sub in cfg("wiki_types", default={}) or ["papers", "concepts", "connections", "questions", "syntheses"]:
        rep.mkdir(wiki_dir(sub))

    rep.mkdir(WS / cfg("dirs", "raw", default="raw"))
    rep.mkdir(Path(WS / cfg("dirs", "inbox", default="raw/research")))
    for kind in (cfg("dirs", "archive", default={}) or {}):
        rep.mkdir(archive_dir(kind))

    rep.mkdir(tmp_dir())

    # 以下目录属于可选结构，配置里留空则跳过
    for key in ("my_research", "weekly"):
        rel = cfg("dirs", key, default="")
        if rel:
            rep.mkdir(Path(WS / rel))

    # 周报领域子目录（仅在配置了 domains 时创建）
    weekly = cfg("dirs", "weekly", default="")
    if weekly:
        for dom in cfg("domains", default=[]) or []:
            rep.mkdir(Path(WS / weekly / dom))


def build_root_files(rep: Report, tpl: Path, force: bool = False) -> None:
    index_name = cfg("files", "index", default="index.md")
    log_name = cfg("files", "log", default="log.md")
    rep.write(WS / index_name, _read_template(tpl, "index.md", FALLBACK_INDEX), force=force)
    rep.write(WS / log_name, _read_template(tpl, "log.md", FALLBACK_LOG), force=force)

    # .gitkeep 让空目录能被 git 记录（Obsidian/git 用户都需要）
    for d in [wiki_dir(), *(wiki_dir(s) for s in (cfg("wiki_types", default={}) or {}))]:
        if d.is_dir() and not any(d.iterdir()):
            rep.write(d / ".gitkeep", "", force=False)


def build_vocab(rep: Report, force: bool = False) -> None:
    """确保 .dsh/tag-vocab.json 存在，并在 TAGS.md 缺失时生成它。

    已经存在的 `TAGS.md` 一律保留——它可能是用户按自己的词表生成的。
    需要主动刷新时用 `tag_vocab.py --emit-doc`（或用本脚本的 `--force`）。
    """
    vocab = WS / cfg("files", "vocab", default=".dsh/tag-vocab.json")
    if not vocab.exists():
        shipped = Path(__file__).resolve().parents[1] / "tag-vocab.json"
        if shipped.is_file():
            rep.copy(shipped, vocab)
        else:
            rep.fail(f"词表缺失且找不到模板：{vocab}")
            return

    tags_doc = WS / cfg("files", "tags_doc", default="TAGS.md")
    if tags_doc.exists() and not force:
        rep.skipped.append(cfg("files", "tags_doc", default="TAGS.md"))
        return

    tags_engine = script_path("tag_vocab.py")
    if not tags_engine.is_file():
        rep.fail("找不到 .dsh/scripts/tag_vocab.py，跳过 TAGS.md 生成")
        return
    if rep.dry_run:
        rep.created.append(cfg("files", "tags_doc", default="TAGS.md"))
        return
    proc = subprocess.run(
        [sys.executable, str(tags_engine), "--emit-doc"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        rep.fail("tag_vocab.py --emit-doc 失败：\n" + (proc.stdout or "") + (proc.stderr or ""))
    else:
        rep.created.append(cfg("files", "tags_doc", default="TAGS.md"))


def build_canvas(rep: Report, force: bool = False) -> None:
    """首次安装时生成总图画布，让 `gen_canvas.py --check` 一装完就是绿的。

    已有画布则跳过（除非 `--force`）：本脚本只负责"补齐缺失"，
    主动重生成画布是 `gen_canvas.py` 的职责，不该由安装器代劳。
    """
    overview = WS / cfg("canvas", "overview", default="wiki/概念全景图.canvas")
    if overview.exists() and not force:
        rep.skipped.append(cfg("canvas", "overview", default="wiki/概念全景图.canvas"))
        return

    gen = script_path("gen_canvas.py")
    if not gen.is_file():
        rep.fail("找不到 .dsh/scripts/gen_canvas.py，跳过画布生成")
        return
    if rep.dry_run:
        rep.created.append(cfg("canvas", "overview", default="wiki/概念全景图.canvas"))
        return
    proc = subprocess.run(
        [sys.executable, str(gen)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        rep.fail("gen_canvas.py 失败：\n" + (proc.stdout or "") + (proc.stderr or ""))
    else:
        rep.created.append(cfg("canvas", "overview", default="wiki/概念全景图.canvas"))


def build_venv(rep: Report) -> None:
    """创建项目 venv 并安装 requirements（只给需要 PyMuPDF 的用户）。"""
    venv_dir = WS / cfg("python", "venv", default=".dsh/venv")
    req = WS / cfg("python", "requirements", default=".dsh/requirements.txt")
    if rep.dry_run:
        rep.created.append(venv_dir.relative_to(WS).as_posix() + "/")
        return
    if not venv_dir.exists():
        proc = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            rep.fail("创建 venv 失败：" + (proc.stderr or ""))
            return
        rep.created.append(venv_dir.relative_to(WS).as_posix() + "/")

    from wiki_env import venv_python  # 延迟导入：venv 可能刚刚才建好
    py = venv_python()
    if not py:
        rep.fail("venv 已创建但找不到其中的解释器")
        return
    if req.is_file():
        proc = subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            rep.fail("pip install 失败：" + (proc.stderr or "")[-800:])
        else:
            rep.created.append("venv 依赖已安装")


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="初始化 LLM Wiki 知识库骨架（幂等：已存在的文件一律跳过）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="只报告将要创建的内容，不写盘")
    ap.add_argument("--force", action="store_true",
                    help="覆盖 index.md / log.md / TAGS.md / 画布（已有内容会丢，慎用）")
    ap.add_argument("--venv", action="store_true", help="创建 .dsh/venv 并安装 requirements.txt")
    ap.add_argument("--quiet", action="store_true", help="只输出一行总结")
    ap.add_argument("--json", dest="json_out", default=None, help="把结果写入 JSON 文件")
    args = ap.parse_args(argv)

    rep = Report(dry_run=args.dry_run)
    tpl = _templates_dir()

    if not CONFIG_PATH.is_file():
        rep.fail(f"找不到配置文件 {CONFIG_PATH}（应从工具包复制整个 .dsh/ 目录）")

    build_skeleton(rep)
    build_root_files(rep, tpl, force=args.force)
    build_vocab(rep, force=args.force)
    build_canvas(rep, force=args.force)
    if args.venv:
        build_venv(rep)

    summary = {
        "workspace": str(WS),
        "dry_run": args.dry_run,
        "created": rep.created,
        "skipped": rep.skipped,
        "failed": rep.failed,
    }

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.quiet:
        print(f"setup_wiki: 写入 {len(rep.created)} 项 / 保持原样 {len(rep.skipped)} 项 / 失败 {len(rep.failed)} 项")
    else:
        head = "（预演，未写盘）" if args.dry_run else ""
        print(f"工作区：{WS}{head}")
        if rep.created:
            print(f"\n✓ 新建/更新 {len(rep.created)} 项：")
            for x in rep.created:
                print(f"  + {x}")
        if rep.skipped:
            print(f"\n· 已存在，跳过 {len(rep.skipped)} 项")
        if rep.failed:
            print(f"\n✗ 失败 {len(rep.failed)} 项：")
            for x in rep.failed:
                print(f"  ! {x}")
        else:
            print("\n下一步：")
            print("  1. python .dsh/scripts/selfcheck.py          # 体检：环境、依赖、骨架")
            print("  2. 把待摄入资料放进收件箱，然后让 agent 执行 /ingest")
            print("  3. 目录名 / 领域 / tag 词表都在 .dsh/wiki.config.json 与 .dsh/tag-vocab.json 里改")

    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
