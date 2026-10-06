#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiki_env —— Scholar LLM Wiki 的共享环境解析层（仅标准库，零第三方依赖）。

**这是全仓唯一允许"找路径"的地方。** 其余脚本一律通过本模块拿工作区根、
库根前缀、目录与配置，因此仓库内不得出现任何绝对路径、盘符或用户名。

解析规则
--------
1. 工作区根（workspace root）= 含 `.dsh/` 的目录，由本文件的位置上溯两级推出：
   `<WS>/.dsh/scripts/wiki_env.py` → `<WS>`。
   可用环境变量 `WIKI_WORKSPACE` 覆盖（便于把脚本装在别处、操作另一个库）。
2. 配置 = `<WS>/.dsh/wiki.config.json`，可用环境变量 `WIKI_CONFIG` 指定别的文件。
   缺失时使用内置 `DEFAULTS`，脚本不会因此崩溃。
3. Obsidian 库根前缀（vault prefix）= 从 `<WS>` 逐级向上找 `.obsidian/`，
   返回 `<WS>` 相对库根的 POSIX 路径 + `/`（工作区本身就是库根时返回 `""`）。
   **写进 Obsidian 文件（尤其 `.canvas`）的路径必须带这个前缀**；
   `[[双链]]` 不受影响（Obsidian 按 basename 解析）。

命令行自省
----------
    python .dsh/scripts/wiki_env.py            # 打印解析结果（JSON）
    python .dsh/scripts/wiki_env.py --paths     # 只打印常用目录
    python .dsh/scripts/wiki_env.py --json      # 完整配置 + 解析结果

技能/脚本若不确定路径，先跑这个命令，不要猜。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 允许 `python wiki_env.py` 直接运行（默认 __file__ 已是绝对路径，无需 sys.path 处理）
__all__ = [
    "WS", "CONFIG", "CONFIG_PATH", "DEFAULTS",
    "cfg", "load_config", "vault_prefix", "vault_rel",
    "wiki_dir", "raw_dir", "inbox_dir", "tmp_dir", "archive_dir", "wiki_subdir",
    "script_path", "python_bin", "venv_python", "ensure_utf8_stdio",
    "describe", "main",
]

# --------------------------------------------------------------------------
# 0. 控制台编码兜底（Windows 默认 GBK 会吞掉 ✓ / ✗ / 中文）
# --------------------------------------------------------------------------
def ensure_utf8_stdio() -> None:
    """把 stdout/stderr 切到 UTF-8，避免 Windows GBK 控制台报 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - 某些宿主 stdout 不可重配置
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


# --------------------------------------------------------------------------
# 1. 内置默认配置（与 .dsh/wiki.config.json 的键一一对应）
# --------------------------------------------------------------------------
DEFAULTS: dict = {
    "version": 1,
    "wiki_name": "科研 Wiki",
    "language": "zh-CN",
    "vault_prefix": "auto",
    "dirs": {
        "wiki": "wiki",
        "raw": "raw",
        "inbox": "raw/research",
        "tmp": ".dsh/tmp",
        "archive": {
            "papers": "raw/papers",
            "book": "raw/book",
            "courses": "raw/courses",
            "clips": "raw/clips",
            "articles": "raw/articles",
            "assets": "raw/assets",
        },
        "my_research": "我的研究",
        "weekly": "周报",
    },
    "files": {
        "index": "index.md",
        "log": "log.md",
        "tags_doc": "TAGS.md",
        "vocab": ".dsh/tag-vocab.json",
    },
    # wiki 子目录 → frontmatter 的 type 值（lint 检查 1 / ingest 步骤 3 依赖）
    "wiki_types": {
        "papers": "paper",
        "concepts": "concept",
        "connections": "connection",
        "questions": "question",
        "syntheses": "synthesis",
    },
    "canvas": {
        "overview": "wiki/概念全景图.canvas",
        "family_prefix": "wiki/概念地图-",
        "title": "概念全景图",
    },
    # 周报/速报的领域分区；留空则不生成领域子目录
    "domains": [],
    "python": {
        "venv": ".dsh/venv",
        "requirements": ".dsh/requirements.txt",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：override 覆盖 base，dict 逐层合并，其余类型直接替换。"""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------
# 2. 工作区根 / 配置定位
# --------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
SCRIPT_DIR = _HERE.parent                      # <WS>/.dsh/scripts
_DEFAULT_WS = _HERE.parents[2]                 # <WS>

CONFIG_ENV = "WIKI_CONFIG"
WORKSPACE_ENV = "WIKI_WORKSPACE"
DEFAULT_CONFIG_REL = ".dsh/wiki.config.json"


def _resolve_workspace() -> Path:
    env = os.environ.get(WORKSPACE_ENV)
    if env:
        p = Path(env).expanduser()
        try:
            return p.resolve()
        except OSError:  # pragma: no cover
            return p
    return _DEFAULT_WS


WS: Path = _resolve_workspace()


def _resolve_config_path(ws: Path) -> Path:
    env = os.environ.get(CONFIG_ENV)
    if env:
        p = Path(env).expanduser()
        return p if p.is_absolute() else (ws / p)
    return ws / DEFAULT_CONFIG_REL


CONFIG_PATH: Path = _resolve_config_path(WS)


def load_config(path: Path | None = None) -> dict:
    """读取配置并与 DEFAULTS 深合并。文件缺失/损坏时返回 DEFAULTS（不抛异常）。"""
    p = path or CONFIG_PATH
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("配置根节点必须是 JSON 对象")
    except FileNotFoundError:
        raw = {}
    except Exception as exc:  # pragma: no cover - 损坏配置要让用户看见
        print(f"[wiki_env] 警告：无法解析 {p}（{exc}），改用内置默认配置", file=sys.stderr)
        raw = {}
    return _deep_merge(DEFAULTS, raw)


CONFIG: dict = load_config()


def cfg(*keys: str, default=None):
    """按路径取配置值：`cfg("dirs", "wiki")`；缺失时返回 default。"""
    cur = CONFIG
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# --------------------------------------------------------------------------
# 3. 路径工具
# --------------------------------------------------------------------------
def _p(rel: str) -> Path:
    """把配置里的相对路径绑到工作区根；已是绝对路径则原样返回。"""
    q = Path(rel)
    return q if q.is_absolute() else (WS / q)


def vault_prefix(ws: Path | None = None) -> str:
    """返回「库根相对前缀」，如 `notes/`；工作区本身即库根时返回 `""`。

    配置项 `vault_prefix` 为 `"auto"`（默认）时自动探测；显式给字符串则直接采用
    （末尾自动补 `/`，空串表示"工作区就是库根"）。
    """
    explicit = cfg("vault_prefix", default="auto")
    if explicit != "auto":
        s = str(explicit).replace("\\", "/").strip("/")
        return f"{s}/" if s else ""

    start = ws or WS
    p = start
    while True:
        if (p / ".obsidian").is_dir():
            if p == start:
                return ""
            return start.relative_to(p).as_posix().strip("/") + "/"
        parent = p.parent
        if parent == p:            # 到达文件系统根，未找到 .obsidian
            return ""
        p = parent


def vault_rel(path: Path | str, ws: Path | None = None) -> str:
    """把工作区内路径转成可直接写进 Obsidian 文件的「库根相对路径」。"""
    base = ws or WS
    q = Path(path)
    rel = q.relative_to(base).as_posix() if q.is_absolute() else q.as_posix()
    return vault_prefix(base) + rel.lstrip("/")


def wiki_dir(sub: str | None = None) -> Path:
    root = _p(cfg("dirs", "wiki", default="wiki"))
    return (root / sub) if sub else root


def wiki_subdir(sub: str) -> Path:
    """便捷别名：wiki_subdir("concepts")。"""
    return wiki_dir(sub)


def raw_dir(sub: str | None = None) -> Path:
    root = _p(cfg("dirs", "raw", default="raw"))
    return (root / sub) if sub else root


def inbox_dir() -> Path:
    return _p(cfg("dirs", "inbox", default="raw/research"))


def tmp_dir() -> Path:
    return _p(cfg("dirs", "tmp", default=".dsh/tmp"))


def archive_dir(kind: str) -> Path:
    """归档目标：archive_dir("papers") → <WS>/raw/papers。"""
    table = cfg("dirs", "archive", default={}) or {}
    rel = table.get(kind)
    if not rel:
        # 未登记的类型退回 raw/<kind>，保证脚本不会崩
        rel = f"{cfg('dirs', 'raw', default='raw')}/{kind}"
    return _p(rel)


def script_path(name: str) -> Path:
    """同目录脚本的绝对路径：script_path("tag_audit.py")。"""
    return SCRIPT_DIR / name


# --------------------------------------------------------------------------
# 4. 解释器解析（跨平台；不写死任何盘符）
# --------------------------------------------------------------------------
def python_bin(prefer_venv: bool = False) -> str:
    """返回应当用来跑脚本的解释器路径字符串。

    prefer_venv=True 时优先用项目 venv（Windows: Scripts/python.exe，
    其它平台: bin/python），不存在则回退当前解释器 `sys.executable`。
    """
    if prefer_venv:
        v = venv_python()
        if v:
            return str(v)
    return sys.executable or "python3"


def venv_python() -> Path | None:
    """探测项目 venv 里的 python；不存在返回 None。"""
    root = _p(cfg("python", "venv", default=".dsh/venv"))
    for cand in (root / "Scripts" / "python.exe", root / "bin" / "python", root / "bin" / "python3"):
        if cand.exists():
            return cand
    return None


# --------------------------------------------------------------------------
# 5. 自省输出
# --------------------------------------------------------------------------
def describe() -> dict:
    return {
        "workspace": str(WS),
        "config_path": str(CONFIG_PATH),
        "config_found": CONFIG_PATH.exists(),
        "vault_prefix": vault_prefix(),
        "python": sys.executable,
        "venv_python": str(venv_python()) if venv_python() else None,
        "paths": {
            "wiki": str(wiki_dir()),
            "raw": str(raw_dir()),
            "inbox": str(inbox_dir()),
            "tmp": str(tmp_dir()),
            "index": str(WS / cfg("files", "index", default="index.md")),
            "log": str(WS / cfg("files", "log", default="log.md")),
            "tags_doc": str(WS / cfg("files", "tags_doc", default="TAGS.md")),
            "vocab": str(WS / cfg("files", "vocab", default=".dsh/tag-vocab.json")),
        },
        "wiki_types": cfg("wiki_types", default={}),
        "canvas": cfg("canvas", default={}),
        "domains": cfg("domains", default=[]),
    }


USAGE = """\
wiki_env —— Scholar LLM Wiki 的共享环境解析层（全仓唯一允许"找路径"的地方）

用法：
  python .dsh/scripts/wiki_env.py            打印工作区根、库根前缀与完整配置（JSON）
  python .dsh/scripts/wiki_env.py --paths    只打印常用目录（wiki / raw / inbox / …）
  python .dsh/scripts/wiki_env.py --json     打印完整解析结果（含解释器与各路径绝对值）
  python .dsh/scripts/wiki_env.py --help     本帮助

被其它脚本 import 时可用：
  WS, CONFIG, cfg(*keys, default), vault_prefix(), vault_rel(p),
  wiki_dir(sub), raw_dir(sub), inbox_dir(), tmp_dir(), archive_dir(kind),
  script_path(name), python_bin(prefer_venv=False), venv_python(), ensure_utf8_stdio()

环境变量：
  WIKI_WORKSPACE   覆盖工作区根（默认由本文件位置上溯两级推出）
  WIKI_CONFIG      覆盖配置文件位置（默认 <工作区根>/.dsh/wiki.config.json）
"""


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(USAGE, end="")
        return 0
    info = describe()
    if "--paths" in args:
        for k, v in info["paths"].items():
            print(f"{k:<10} {v}")
        return 0
    payload = info if "--json" in args else {
        "workspace": info["workspace"],
        "vault_prefix": info["vault_prefix"],
        "config": CONFIG,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
