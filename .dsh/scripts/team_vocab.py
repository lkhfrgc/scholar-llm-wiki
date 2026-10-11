#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文团队受控词表引擎（词表数据与代码分离）。

词表数据在 `.dsh/team-vocab.json`（路径来自配置项 `files.team_vocab`），本文件只负责
**加载 + 校验 + 生成文档**：

  * `teams`   —— 允许写进论文页 frontmatter `team:` 的规范名全集（含上级机构 base、类型与中文说明）
  * `aliases` —— 来源写法 → 规范名的归并表（供 `team_audit.py` 提示、`team_apply.py` 改写）

用法：
    python .dsh/scripts/team_vocab.py                    # 词表统计与自检结果
    python .dsh/scripts/team_vocab.py --check            # 校验词表自洽（退出码非 0 即失败）
    python .dsh/scripts/team_vocab.py --list             # 列出当前词表全部团队（按类型分组）
    python .dsh/scripts/team_vocab.py --emit-doc         # 生成/刷新 TEAMS.md（规则文档，只写规则不列团队）
    python .dsh/scripts/team_vocab.py --resolve "<写法>" # 查一个写法对应的规范名
    python .dsh/scripts/team_vocab.py --vocab <path>     # 用别的词表文件（也可用环境变量 WIKI_TEAM_VOCAB）

规范要点（与 AGENTS.md「Team 规范」一致）：
  1. 团队是**事实字段**：论文确实来自该团队就登记，不受 tag 那种「≥3 个页面」门槛约束；
     但**同一团队只能有一个规范名**，写法差异一律进 `aliases`。
  2. 两级粒度：机构级 `University of X` / 企业名；实验室级 `University of X (Key Laboratory of Y)`
     —— 一级机构在前、实验室在后，且上级机构必须同时登记（`base` 字段）。
  3. frontmatter 一律单行内联列表 `team: ["A", "B"]`，多单位合作**全记**。
  4. 不入词表的团队名不得出现在 frontmatter；确需新增须走 TEAMS.md 的登记流程。

下游脚本 `team_audit.py` / `team_apply.py` 直接 `import team_vocab as V` 并使用
`TEAMS` / `ALIASES` / `check()` / `resolve()` 等模块级名字，语义保持不变。

被 `import` 时只读取词表文件（无写操作）；词表缺失不会让 import 崩，而是在
`require_vocab()` / `main()` 里给出可操作的提示并以退出码 1 结束。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

__all__ = [
    "VocabError", "KNOWN_KINDS", "VOCAB_ENV", "TEAMS", "ALIASES",
    "resolve_vocab_path", "load_vocab", "require_vocab", "reload_vocab",
    "check", "resolve", "is_empty", "eval_list", "emit_doc", "main",
]

KNOWN_KINDS: tuple = ("机构", "实验室")
VOCAB_ENV = "WIKI_TEAM_VOCAB"
DEFAULT_VOCAB_REL = ".dsh/team-vocab.json"

# 由 _install() 装配；import 时若词表缺失，这两个名字仍存在但为空
TEAMS: dict = {}
ALIASES: dict = {}


class VocabError(RuntimeError):
    """词表文件缺失、不是合法 JSON，或结构不符合预期。"""


# --------------------------------------------------------------------------
# 1. 词表定位与加载
# --------------------------------------------------------------------------
def _config_vocab_path() -> Path:
    rel = cfg("files", "team_vocab", default=DEFAULT_VOCAB_REL) or DEFAULT_VOCAB_REL
    p = Path(rel)
    return p if p.is_absolute() else (WS / p)


def resolve_vocab_path(explicit=None) -> Path:
    """词表文件位置：`--vocab` > 环境变量 `WIKI_TEAM_VOCAB` > 配置项 `files.team_vocab`。

    `--vocab` 的相对路径按当前目录解析；环境变量按工作区根解析，
    这样把脚本装在别处、操作另一个库时也能从任意目录调用。
    """
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_absolute() else (Path.cwd() / p)
    env = os.environ.get(VOCAB_ENV)
    if env:
        p = Path(env).expanduser()
        return p if p.is_absolute() else (WS / p)
    return _config_vocab_path()


def _missing_vocab_message(path: Path) -> str:
    return (
        f"找不到团队词表文件: {path}\n"
        "词表数据与引擎是分离的，缺了它团队相关脚本无法工作。任选一种方式补齐：\n"
        "  1) 运行 `python .dsh/scripts/setup_wiki.py` 生成默认空词表；\n"
        "  2) 手工新建该文件，最小内容为 {\"teams\": {}, \"aliases\": {}}；\n"
        "  3) 用 `--vocab <path>` 或环境变量 `WIKI_TEAM_VOCAB` 指向已有的词表文件。"
    )


def load_vocab(path=None) -> dict:
    """读取并做**结构**校验（语义自检交给 `check()`）。失败抛 `VocabError`。"""
    p = resolve_vocab_path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise VocabError(_missing_vocab_message(p)) from exc
    except OSError as exc:
        raise VocabError(f"无法读取词表文件 {p}：{exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VocabError(
            f"词表文件不是合法 JSON: {p}（第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}）"
        ) from exc
    if not isinstance(data, dict):
        raise VocabError(f"词表文件根节点必须是 JSON 对象: {p}")

    teams = data.get("teams")
    if not isinstance(teams, dict):
        raise VocabError(f"词表缺少 `teams` 段（应为 规范名 → {{base, type, note}}）: {p}")
    for name, spec in teams.items():
        if not isinstance(spec, dict):
            raise VocabError(f"`teams[\"{name}\"]` 必须是对象（含 base/type/note）: {p}")
        kind = spec.get("type")
        if kind not in KNOWN_KINDS:
            raise VocabError(f"`teams[\"{name}\"].type` 必须是 {' / '.join(KNOWN_KINDS)} 之一: {p}")
        if not isinstance(spec.get("base", ""), str):
            raise VocabError(f"`teams[\"{name}\"].base` 必须是字符串（机构级留空串）: {p}")

    aliases = data.get("aliases") or {}
    if not isinstance(aliases, dict):
        raise VocabError(f"`aliases` 段必须是对象（来源写法 → 规范名）: {p}")
    for src, target in aliases.items():
        if not isinstance(target, str):
            raise VocabError(f"`aliases[\"{src}\"]` 必须是字符串（规范名）: {p}")
    return data


def _install(data: dict) -> None:
    """把词表数据装配成模块级常量（下游依赖这些名字）。"""
    global TEAMS, ALIASES
    TEAMS = {
        str(name): {
            "base": str(spec.get("base") or ""),
            "type": str(spec.get("type") or "机构"),
            "note": str(spec.get("note") or ""),
        }
        for name, spec in (data.get("teams") or {}).items()
    }
    ALIASES = {str(k): str(v) for k, v in (data.get("aliases") or {}).items()}


try:
    _install(load_vocab())
except VocabError:
    pass  # 推迟到 require_vocab() / main() 里报错，保证 import 不崩


def require_vocab() -> dict:
    """确保词表已加载；缺失就带着可操作提示抛错。"""
    if not TEAMS and not resolve_vocab_path().exists():
        raise VocabError(_missing_vocab_message(resolve_vocab_path()))
    return {"teams": TEAMS, "aliases": ALIASES}


def reload_vocab(path=None) -> dict:
    """重新读盘并装配（写盘后的同进程复算用）。"""
    data = load_vocab(path)
    _install(data)
    return data


# --------------------------------------------------------------------------
# 2. 查询
# --------------------------------------------------------------------------
def resolve(name: str) -> str:
    """写法 → 规范名：命中别名返回规范名；已是规范名原样返回；否则返回空串。"""
    if name in TEAMS:
        return name
    return ALIASES.get(name, "")


def is_empty() -> bool:
    """出厂空词表判定（冷启动阶段放宽门槛用）。"""
    return not TEAMS


def eval_list(text: str) -> list:
    """把 frontmatter 里 `team: ["A", "B"]` 的列表内容解析成 Python 列表。

    团队名本身可能含逗号（如 "Institute of Automation, Chinese Academy of Sciences"），
    所以按 JSON 解析，**不能按逗号切分**。
    """
    t = text.strip()
    if not t:
        return []
    if not t.startswith("["):
        t = "[" + t + "]"
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


# --------------------------------------------------------------------------
# 3. 自检
# --------------------------------------------------------------------------
def check() -> list:
    """返回问题列表（空列表 = 自洽）。"""
    problems: list = []
    for name, spec in TEAMS.items():
        kind, base = spec["type"], spec["base"]
        if kind == "实验室":
            if not base:
                problems.append(f"实验室级条目缺 base（上级机构）：{name}")
            elif base not in TEAMS:
                problems.append(f"上级机构未登记为独立条目：{base}（被 {name} 引用）")
        elif base:
            problems.append(f"机构级条目的 base 应为空串：{name} → {base}")
        if not spec["note"]:
            problems.append(f"缺中文说明 note：{name}")
    for alias, target in ALIASES.items():
        if alias in TEAMS:
            problems.append(f"别名与规范名同名（应删掉别名）：{alias}")
        if target not in TEAMS:
            problems.append(f"别名指向未登记的规范名：{alias} → {target}")
    # 归一化后同名（去掉括号实验室部分与虚词）→ 疑似同一团队的两种写法
    def norm_key(name: str) -> str:
        base = name
        if "(" in name and name.rstrip().endswith(")"):
            head, _, tail = name.rpartition("(")
            if any(k in tail for k in ("Laborator", "Lab", "Center", "Centre", "Institute", "Key", "Research")):
                base = head
        keep = []
        for tok in base.lower().replace("-", " ").replace(",", " ").split():
            if tok not in ("the", "of", "and", "for", "in", "at"):
                keep.append(tok)
        return " ".join(keep)

    buckets: dict = {}
    for name in TEAMS:
        buckets.setdefault(norm_key(name), []).append(name)
    for key, names in buckets.items():
        if len(names) > 1:
            labs = [n for n in names if TEAMS[n]["type"] == "实验室"]
            parents = {TEAMS[n]["base"] for n in labs}
            rest = [n for n in names if n not in parents]
            if len(rest) > 1:
                problems.append("归一化后同名（疑似同一团队两种写法）：" + "、".join(rest))
    return problems


# --------------------------------------------------------------------------
# 4. 生成规则文档 TEAMS.md
# --------------------------------------------------------------------------
def emit_doc() -> str:
    """生成 TEAMS.md 内容：**只写规则，不列团队**（团队本体在词表数据文件里）。"""
    doc_rel = cfg("files", "team_vocab", default=DEFAULT_VOCAB_REL)
    doc_path = cfg("files", "teams_doc", default="TEAMS.md")
    n_lab = sum(1 for v in TEAMS.values() if v["type"] == "实验室")
    state = "**当前词表是空的**（`teams` 里一条都没有）—— 这是出厂状态，不是出错。" if is_empty() else \
        f"当前词表已有 **{len(TEAMS)}** 条规范名（机构级 {len(TEAMS) - n_lab} 条、实验室/课题组级 {n_lab} 条）。"
    return f"""# 论文团队规范（受控词表规则）

> 本文件由 `.dsh/scripts/team_vocab.py --emit-doc` 自动生成，**请勿手工编辑**。
>
> **这里只写规则，不列团队。** 词表本体是数据，在你自己的 `{doc_rel}` 里 ——
> 它随你摄入的论文增删，本文件不随它变化（改了词表**不需要**重新生成本文件）。
>
> 想知道当前允许哪些团队：`python .dsh/scripts/team_vocab.py --list`

## 一、硬规则

1. **只允许 `{doc_rel}` 的 `teams` 段登记过的规范名**出现在论文页 frontmatter 的 `team:` 字段里。
   封闭词表是防止团队名漂移的唯一机制：没有它，同一个团队会写成 `Meta AI`、`FAIR`、
   `Facebook AI Research` 三种样子，按团队检索就废了。
2. **多单位合作全记**：`team` 是**列表**，按论文署名的上标编号 / 出现顺序排列，
   不要只记第一单位。实测同一篇论文最多可以来自 8 个单位。
3. **两级粒度**：
   - 机构级：`University of X`、`Microsoft Corporation`、`Shanghai AI Laboratory`；
   - 实验室级：`University of X (Key Laboratory of Y)` —— **一级机构在前，实验室/课题组在后**，
     且上级机构必须同时登记为一条机构级条目（`base` 字段），`--check` 会校验。
   - 只到院系的署名（`School of` / `College of` / `Department of` / `Faculty of`）**不算团队**，
     折叠为一级机构；邮箱、城市、邮编、基金号、`Authorized licensed use limited to:` 水印一律不收录。
4. **写法**：一律单行内联列表 `team: ["A", "B"]`（禁用 YAML 块序列），位置紧跟 `venue` 之后。
   统一写法才能被审计脚本与模板校验脚本无歧义解析。
5. **别名一律归并**：同一团队的不同写法（缩写、中英文、大小写、`University of` 的省略）
   必须登记进 `aliases` 指向同一个规范名，**不得**在 `teams` 里并存两条。
6. 论文页**必须**有非空 `team`；确实无法确认（双盲审稿、PDF 缺失且公开渠道查不到）时写
   `team: ["待确认"]`，并在日志里说明原因，**不要臆造**。

## 二、冷启动：第一次使用时看这里

{state}

出厂只给「机构 / 实验室两级粒度 + 多单位合作全记」这个骨架，**不给任何具体团队**。
理由：团队名是最贴着你研究领域的东西，预设一套（比如塞满某些大厂与大庙）既会误导别的领域的使用者，
也会让人错过自己领域里真正该追踪的组。

**冷启动阶段的放宽规则**（仅当词表为空时适用）：

- **首篇论文取词即可**，不需要凑够若干页 —— 团队是**事实字段**，本来就不同于 tag 的检索词门槛；
- **但纪律不放松**：取用的团队必须在**同一次 ingest 的收尾**登记进 `{doc_rel}` 的
  `teams`（附 `base` / `type` / `note`）与 `aliases`（登记你遇到的来源写法），
  让 `team_audit.py` 的退出码回到 0。是「先立规矩再用」，不是「先用乱再补票」。

## 三、怎么定一篇论文的 team

1. 读**论文首页**的署名块：AAAI / CVPR 等格式在作者名下方带编号
   （`1Xxx University, 2Key Laboratory of …`）；IEEE 期刊 / 会议格式在**首页脚注**
   （`A. Author is with the School of …, Xxx University`）。
2. 每个机构对照词表取规范名；有实验室/课题组就写成 `机构 (实验室)`。
3. 多单位全部收录，按上标编号顺序排列。
4. 拿不准某种写法时先查：

   | 命令 | 作用 |
   |---|---|
   | `python .dsh/scripts/team_vocab.py --resolve "<来源写法>"` | 写法 → 规范名（未登记会明确告知） |
   | `python .dsh/scripts/team_vocab.py --list` | 列出当前全部团队（按类型分组） |

5. 未登记的新团队：先在 `{doc_rel}` 登记 `teams` 与 `aliases`，
   再运行 `--check`（自洽）与 `--emit-doc`（刷新本文件），然后才写页面。

## 四、查看与维护词表

| 命令 | 作用 |
|---|---|
| `python .dsh/scripts/team_vocab.py --list` | **列出当前词表全部团队**（按类型分组，附上级机构与说明） |
| `python .dsh/scripts/team_vocab.py --check` | 自洽性校验（base 是否存在、别名是否指向已登记名、有无归一化重名） |
| `python .dsh/scripts/team_vocab.py --emit-doc` | 重新生成本文件（**只有改规则时才需要**） |
| `python .dsh/scripts/team_vocab.py --resolve "<写法>"` | 查一个来源写法的规范名 |
| `python .dsh/scripts/team_audit.py` | 全库审计：缺 `team`、未登记团队、残留 `affiliations`、结构问题 |
| `python .dsh/scripts/team_audit.py --stats` | 附带每团队论文数排行 |
| `python .dsh/scripts/team_apply.py` | 按映射文件批量写入 `team`（**预演**，不写盘） |
| `python .dsh/scripts/team_apply.py --apply` | 实际写盘并备份到 `.dsh/tmp/teams-backup-*.json` |
| `python .dsh/scripts/team_apply.py --rollback <备份>` | 从备份精确还原 |

> 权威来源是 `<工作区根>/{doc_rel}`。想换一整套团队词表（例如把团队表换成"实验室/课题组"级别），
> 见仓库里的 `docs/CUSTOMIZE.md`。

## 五、常见误用（反面清单）

> 下表用**示例**说明错误模式，示例里的团队名不代表你的词表内容，具体以 `{doc_rel}` 为准。

| ✗ 错误写法 | ✓ 正确写法 | 理由 |
|---|---|---|
| 同一团队两种写法：`Meta AI`、`FAIR`、`Facebook AI Research` | 归一到一条规范名，其余进 `aliases` | 别名并存会让按团队检索漏掉一半 |
| 只记第一单位 | 多单位全部列出 | 「这篇是谁做的」本身就是检索维度 |
| `School of Computer Science, Xxx University` | `Xxx University` | 院系不是团队，是机构的下级 |
| `Xxx University (Key Laboratory of Y)` 但 `Xxx University` 未登记 | 两条都登记，实验室条目的 `base` 指向机构条目 | 没有机构条目，按机构聚合时会漏 |
| 把邮箱、基金号、`Authorized licensed use…` 水印当团队 | （删除） | 它们不是署名单位 |
| 双盲投稿硬猜单位 | `team: ["待确认"]` + 日志说明 | 事实字段宁可留白，不可臆造 |
"""


# --------------------------------------------------------------------------
# 5. 命令行
# --------------------------------------------------------------------------
def _grouped() -> dict:
    out: dict = {kind: [] for kind in KNOWN_KINDS}
    for name, spec in sorted(TEAMS.items()):
        out.setdefault(spec["type"], []).append(name)
    return out


def _cmd_main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="论文团队受控词表引擎")
    ap.add_argument("--check", action="store_true", help="校验词表自洽（退出码非 0 = 有错）")
    ap.add_argument("--list", action="store_true", help="列出当前词表全部团队（按类型分组）")
    ap.add_argument("--emit-doc", action="store_true", help="生成/刷新 TEAMS.md（规则文档）")
    ap.add_argument("--resolve", default=None, metavar="写法", help="写法 → 规范名")
    ap.add_argument("--vocab", default=None, help="用别的词表文件（默认取配置 files.team_vocab）")
    ap.add_argument("--json", action="store_true", help="配合 --list 输出 JSON")
    args = ap.parse_args(argv)

    try:
        reload_vocab(args.vocab)
    except VocabError as exc:
        print(exc, file=sys.stderr)
        return 1

    n_lab = sum(1 for v in TEAMS.values() if v["type"] == "实验室")

    if args.resolve is not None:
        hit = resolve(args.resolve)
        if hit:
            print(hit)
            return 0
        print(f"未登记：{args.resolve}", file=sys.stderr)
        print("→ 若是已有团队的新写法，登记进 aliases；若是新团队，先在 teams 里登记。", file=sys.stderr)
        return 1

    if args.check:
        problems = check()
        for p in problems:
            print("  ✗ " + p)
        if problems:
            print(f"词表校验未通过：{len(problems)} 个问题")
            return 1
        print(f"词表自洽 ✓  规范名 {len(TEAMS)} 条（机构级 {len(TEAMS) - n_lab} / 实验室级 {n_lab}）"
              f" · 别名 {len(ALIASES)} 条")
        if is_empty():
            print("提示：词表是出厂空骨架，第一次摄入时按 TEAMS.md「二、冷启动」登记团队。")
        return 0

    if args.list:
        if args.json:
            print(json.dumps({"teams": TEAMS, "aliases": ALIASES}, ensure_ascii=False, indent=2))
            return 0
        if is_empty():
            print("（词表为空 —— 出厂骨架。第一次摄入时会登记进 " + str(resolve_vocab_path()) + "）")
            return 0
        for kind, names in _grouped().items():
            if not names:
                continue
            print(f"## {kind}（{len(names)} 条）")
            for name in names:
                spec = TEAMS[name]
                extra = f"  ← base: {spec['base']}" if spec["base"] else ""
                print(f"  - {name}{extra}" + (f"   # {spec['note']}" if spec["note"] else ""))
        if ALIASES:
            print(f"## 别名（{len(ALIASES)} 条）")
            for alias, target in sorted(ALIASES.items()):
                print(f"  - {alias}  →  {target}")
        return 0

    if args.emit_doc:
        rel = cfg("files", "teams_doc", default="TEAMS.md")
        out = Path(rel)
        out = out if out.is_absolute() else WS / out
        out.parent.mkdir(parents=True, exist_ok=True)
        text = emit_doc()
        if not text.endswith("\n"):
            text += "\n"
        # 显式 LF：Path.write_text 在 Windows 上会把 \n 翻成 \r\n；而 newline= 参数在 3.9 不存在，
        # 所以与 TAGS.md / 画布生成器一致，手写 open(..., newline="\n")。
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"[完成] 已写出 {out}（规则文档；团队本体仍在 {resolve_vocab_path()}）")
        return 0

    # 默认：统计 + 自检摘要
    problems = check()
    n_lab = sum(1 for v in TEAMS.values() if v["type"] == "实验室")
    print(f"团队词表：{resolve_vocab_path()}")
    print(f"  规范名 {len(TEAMS)} 条（机构级 {len(TEAMS) - n_lab} / 实验室级 {n_lab}）· 别名 {len(ALIASES)} 条")
    if is_empty():
        print("  （出厂空骨架：第一次摄入时按 TEAMS.md「二、冷启动」登记团队）")
    if problems:
        for p in problems:
            print("  ✗ " + p)
        print(f"自检未通过：{len(problems)} 个问题（跑 --check 看全部）")
        return 1
    print("  自检 ✓")
    return 0


def main(argv=None) -> int:
    return _cmd_main(argv)


if __name__ == "__main__":
    sys.exit(main())

