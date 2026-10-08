#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tag 受控词表引擎（词表数据与代码分离）。

词表数据在 `.dsh/tag-vocab.json`（路径来自配置项 `files.vocab`），本文件只负责
**加载 + 校验 + 排序 + 生成文档**：

  * `canonical` —— 允许出现在 wiki 页面 frontmatter 里的规范 tag 全集（按分面组织，含中文释义）
  * `map`       —— 历史/别名 tag → 规范 tag 的映射（供 `tag_apply.py` 批量改写使用）

用法：
    python .dsh/scripts/tag_vocab.py                    # 打印词表统计与自检结果
    python .dsh/scripts/tag_vocab.py --check            # 校验词表自洽（退出码非 0 即失败）
    python .dsh/scripts/tag_vocab.py --list             # 列出当前词表全部词条（按分面分组）
    python .dsh/scripts/tag_vocab.py --emit-doc         # 生成/刷新 TAGS.md（规则文档，只写规则不列词条）
    python .dsh/scripts/tag_vocab.py --vocab <path>     # 用别的词表文件（也可用环境变量 WIKI_VOCAB）

规范要点（与 AGENTS.md「Tag 规范」一致）：
  1. 角色 tag（母概念 / 子概念）不带分面前缀，且**必须位于 tags 首位**——
     画布生成脚本与 lint 的分层检查依赖其字面值。
  2. 主题 tag 一律为 `分面/叶节点` 两级嵌套，叶节点小写 kebab-case。
  3. 只允许配置里声明的分面（默认 7 个：domain / task / modality / method / challenge / data / meta）。
  4. 不入词表的词不得出现在 frontmatter；确需新增须走 TAGS.md 的登记流程。

下游脚本 `tag_apply.py` / `tag_audit.py` / `tag_verify_migration.py` 直接
`import tag_vocab as V` 并使用 `FACETS` / `FACET_ORDER` / `ROLE_TAGS` / `CANONICAL` /
`MAP` / `PAGE_OVERRIDES`，这些模块级名字的语义保持不变。

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
    "VocabError", "KNOWN_FACETS", "KNOWN_ROLE_TAGS", "VOCAB_ENV",
    "FACETS", "FACET_ORDER", "ROLE_TAGS", "CANONICAL", "MAP", "PAGE_OVERRIDES",
    "resolve_vocab_path", "load_vocab", "require_vocab", "reload_vocab", "facet_hints",
    "all_canonical_tags", "canonical_by_name", "order_tags", "translate",
    "check", "emit_doc", "main",
]

# 固定分面与固定角色 tag：既用于自检，也用于生成文档
KNOWN_FACETS: tuple = ("domain", "task", "modality", "method", "challenge", "data", "meta")
KNOWN_ROLE_TAGS: tuple = ("母概念", "子概念")
VOCAB_ENV = "WIKI_VOCAB"
DEFAULT_VOCAB_REL = ".dsh/tag-vocab.json"


class VocabError(RuntimeError):
    """词表文件缺失、不是合法 JSON，或结构不符合预期。"""


# --------------------------------------------------------------------------
# 1. 词表定位与加载
# --------------------------------------------------------------------------
def _config_vocab_path() -> Path:
    rel = cfg("files", "vocab", default=DEFAULT_VOCAB_REL) or DEFAULT_VOCAB_REL
    p = Path(rel)
    return p if p.is_absolute() else (WS / p)


def resolve_vocab_path(explicit=None) -> Path:
    """词表文件位置：`--vocab` > 环境变量 `WIKI_VOCAB` > 配置项 `files.vocab`。

    `--vocab` 是命令行参数，相对路径按当前目录解析；环境变量按工作区根解析，
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
        f"找不到词表文件: {path}\n"
        "词表数据与引擎是分离的，缺了它 tag 相关脚本无法工作。任选一种方式补齐：\n"
        "  1) 运行 `python .dsh/scripts/setup_wiki.py` 生成默认词表；\n"
        "  2) 若仓库提供了 `templates/tag-vocab.json` 模板，复制到上面的路径；\n"
        "  3) 用 `--vocab <path>` 或环境变量 `WIKI_VOCAB` 指向已有的词表文件。"
    )


def load_vocab(path=None) -> dict:
    """读取并做**结构**校验（不做语义自检，语义交给 `check()`）。失败抛 `VocabError`。"""
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

    if not isinstance(data.get("facets"), dict) or not data["facets"]:
        raise VocabError(f"词表缺少 `facets` 段（应为 分面名 → {{desc, hint}}）: {p}")
    if not isinstance(data.get("canonical"), dict):
        raise VocabError(f"词表缺少 `canonical` 段（应为 分面 → {{叶节点: 释义}}）: {p}")
    for facet, spec in data["facets"].items():
        if not isinstance(spec, dict):
            raise VocabError(f"`facets.{facet}` 必须是对象（含 desc/hint）: {p}")

    raw_map = data.get("map") or {}
    if not isinstance(raw_map, dict):
        raise VocabError(f"`map` 段必须是对象（来源词 → 规范 tag 列表）: {p}")
    for src, targets in raw_map.items():
        if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
            raise VocabError(f"`map[\"{src}\"]` 必须是字符串列表（空列表表示删除该 tag）: {p}")

    for key in ("role_tags", "page_overrides"):
        if key in data and not isinstance(data[key], list if key == "role_tags" else dict):
            raise VocabError(f"`{key}` 段类型不对: {p}")
    return data


def _install(data: dict) -> None:
    """把词表数据装配成模块级常量（下游依赖这些名字）。"""
    global _VOCAB_DATA, FACETS, FACET_ORDER, ROLE_TAGS, CANONICAL, MAP, PAGE_OVERRIDES
    _VOCAB_DATA = data or {}

    facets = _VOCAB_DATA.get("facets") or {}
    FACETS = [
        (str(name), str((spec or {}).get("desc", "")) if isinstance(spec, dict) else str(spec))
        for name, spec in facets.items()
    ]
    FACET_ORDER = [name for name, _ in FACETS]
    ROLE_TAGS = tuple(str(t) for t in (_VOCAB_DATA.get("role_tags") or ()))

    canon = _VOCAB_DATA.get("canonical") or {}
    CANONICAL = {
        f: {str(k): str(v) for k, v in (canon.get(f) or {}).items()} for f in FACET_ORDER
    }
    MAP = {
        str(src): [str(t) for t in (targets or [])]
        for src, targets in (_VOCAB_DATA.get("map") or {}).items()
    }
    PAGE_OVERRIDES = {
        str(page): [str(t) for t in (tags or [])]
        for page, tags in (_VOCAB_DATA.get("page_overrides") or {}).items()
    }


def facet_hints() -> dict:
    """分面 → 判断问题（TAGS.md 的「判断问题」列）。"""
    out = {}
    for name, spec in (_VOCAB_DATA.get("facets") or {}).items():
        out[str(name)] = str((spec or {}).get("hint", "")) if isinstance(spec, dict) else ""
    return out


def require_vocab() -> dict:
    """确保词表已就绪；缺失/损坏时抛 `VocabError`（消息可直接打印给用户）。"""
    if _LOAD_ERROR is not None:
        raise _LOAD_ERROR
    return _VOCAB_DATA


def reload_vocab(path=None) -> dict:
    """换一个词表文件并重新装配模块级常量（CLI 的 `--vocab` 走这里）。"""
    global _LOAD_ERROR
    data = load_vocab(path)
    _LOAD_ERROR = None
    _install(data)
    return data


# 模块导入时装配一次：失败不抛异常，只记下来，等 require_vocab()/main() 报错
FACETS: list = []
FACET_ORDER: list = []
ROLE_TAGS: tuple = ()
CANONICAL: dict = {}
MAP: dict = {}
PAGE_OVERRIDES: dict = {}
_VOCAB_DATA: dict = {}
_LOAD_ERROR = None

try:
    _install(load_vocab())
except VocabError as _exc:  # pragma: no cover - 取决于运行环境
    _LOAD_ERROR = _exc
    _install({})


# --------------------------------------------------------------------------
# 2. 词表查询
# --------------------------------------------------------------------------
def all_canonical_tags() -> list:
    """返回带分面前缀的规范 tag 全集（不含角色 tag）。"""
    out: list = []
    for f in FACET_ORDER:
        out += [f"{f}/{leaf}" for leaf in CANONICAL[f]]
    return out


def canonical_by_name() -> dict:
    """规范 tag → 中文释义。"""
    out = {t: "角色标签（层级）" for t in ROLE_TAGS}
    for f, leaves in CANONICAL.items():
        for leaf, desc in leaves.items():
            out[f"{f}/{leaf}"] = desc
    return out


def order_tags(tags: list) -> list:
    """按「角色 tag 在前 → 分面顺序 → 面内字母序」稳定排序并去重。"""
    roles = [t for t in tags if t in ROLE_TAGS]
    others = [t for t in tags if t not in ROLE_TAGS]
    roles = [r for r in ROLE_TAGS if r in roles]  # 固定 母概念 → 子概念

    def key(t: str):
        facet = t.split("/", 1)[0] if "/" in t else "~"
        idx = FACET_ORDER.index(facet) if facet in FACET_ORDER else 99
        return (idx, t)

    return roles + sorted(set(others), key=key)


def translate(tags: list, page=None) -> list:
    """把一个页面的历史 tag 列表映射为规范 tag 列表（已排序去重）。

    page 为工作区相对路径（如 `wiki/papers/xxx.md`）时，会额外应用 PAGE_OVERRIDES 修剪。
    未登记的 tag 会抛 `KeyError`（调用方据此中止，绝不静默丢弃）。
    """
    out: list = []
    unknown: list = []
    known = canonical_by_name()
    for t in tags:
        if t in MAP:
            out += MAP[t]
        elif t in known:
            out.append(t)          # 已经是规范 tag（幂等）
        else:
            unknown.append(t)
    if unknown:
        raise KeyError(f"未登记的 tag: {unknown}")
    result = order_tags(out)
    if page and page in PAGE_OVERRIDES:
        drop = set(PAGE_OVERRIDES[page])
        result = [t for t in result if t not in drop]
    return result


# --------------------------------------------------------------------------
# 3. 自检
# --------------------------------------------------------------------------
def check() -> list:
    """自检：词表必须自洽。返回错误列表（空列表 = 通过）。"""
    errs: list = []

    # (1) 分面必须恰好是已知的 7 个，且顺序一致（顺序即 frontmatter 排序顺序）
    if list(FACET_ORDER) != list(KNOWN_FACETS):
        errs.append(
            "facets 必须恰好是这 7 个且顺序不变: "
            + " / ".join(KNOWN_FACETS)
            + f"（当前: {' / '.join(FACET_ORDER) or '空'}）"
        )
    # (2) 角色 tag 固定两个、不带前缀、顺序固定
    if list(ROLE_TAGS) != list(KNOWN_ROLE_TAGS):
        errs.append(
            "role_tags 必须恰好是 " + str(list(KNOWN_ROLE_TAGS))
            + f"（当前: {list(ROLE_TAGS)}）"
        )

    valid = set(canonical_by_name())
    for src, targets in MAP.items():
        for t in targets:
            if t not in valid:
                errs.append(f"MAP['{src}'] 指向未定义 tag: {t}")
    # 每个分面叶节点都应至少被一个源 tag 覆盖（否则是死词条）
    covered = {t for ts in MAP.values() for t in ts}
    for t in sorted(valid - set(ROLE_TAGS)):
        if t not in covered:
            errs.append(f"规范 tag 无任何映射来源（死词条）: {t}")
    # 分面必须都是已知分面
    for f in CANONICAL:
        if f not in FACET_ORDER:
            errs.append(f"未知分面: {f}")
    return errs


# --------------------------------------------------------------------------
# 4. 生成 TAGS.md
# --------------------------------------------------------------------------
def _desc_tail(desc: str) -> str:
    """取「分面：说明」中冒号之后的部分；没有冒号就原样返回。"""
    return desc.split("：", 1)[1] if "：" in desc else desc


def emit_doc() -> str:
    """生成 TAGS.md 的正文 —— **只写规则，不列词条**。

    词表本体是数据（`.dsh/tag-vocab.json`），它因研究领域而异、随用随改。
    把具体词条抄进规范文档有两个坏处：

    1. **规范与数据耦合**：换一套领域词表就得重写文档，改了词忘了改文档还会互相矛盾；
    2. **像自带推荐词表**：读者会把那些词当成"这个工具建议我用的 tag"，
       而实际上它们只是某个初始词表的快照，跟使用者的领域未必相关。

    所以这里只固化**不随项目变化的规则**。要查当前允许哪些词，用
    `tag_vocab.py --list`；文档与数据各归其位。
    """
    L: list = []
    hints = facet_hints()
    wiki_rel = cfg("dirs", "wiki", default="wiki")
    L.append("# Tag 规范（受控词表规则）")
    L.append("")
    L.append("> 本文件由 `.dsh/scripts/tag_vocab.py --emit-doc` 自动生成，**请勿手工编辑**。")
    L.append(">")
    L.append("> **这里只写规则，不列词条。** 词表本体是数据，在你自己的 `.dsh/tag-vocab.json` 里 ——")
    L.append("> 它随你的研究领域增删，本文件不随它变化（改了词表**不需要**重新生成本文件）。")
    L.append(">")
    L.append("> 想知道当前允许哪些词：`python .dsh/scripts/tag_vocab.py --list`")
    L.append("")
    L.append("## 一、硬规则")
    L.append("")
    L.append(f"1. **只允许 `.dsh/tag-vocab.json` 的 `canonical` 段登记过的 tag** 出现在 "
             f"`{wiki_rel}/**/*.md` 的 frontmatter `tags:` 字段中。")
    L.append("   封闭词表是防止标签膨胀的唯一机制：没有它，tag 数量会随页数线性增长，最终失去检索价值。")
    L.append("2. 角色 tag `母概念` / `子概念` **不带前缀，且必须是 `tags` 的第一项**——")
    L.append("   画布生成脚本与 lint 的分层检查依赖其字面值与位置。")
    L.append("3. 主题 tag 一律形如 `分面/叶节点`：分面只有 7 个，叶节点为小写 kebab-case 英文。")
    L.append("4. 每页主题 tag **1–8 个**（角色 tag 不计入），推荐 3–5 个；")
    L.append("   分面软上限 domain 2 / task 4 / modality 4 / method 6 / challenge 4 / data 2 / meta 2。")
    L.append("5. **禁止**用 tag 表达 `type`、年份、期刊名、论文缩写、数据集专名、模型专名——")
    L.append("   这些信息已由 frontmatter 字段或正文承载。数据集/模型专名统一归入")
    L.append("   `data/dataset` 与 `method/foundation-model`。")
    L.append("6. 排序：角色 tag → 分面顺序（" + " → ".join(FACET_ORDER) + "）→ 面内字母序。")
    L.append("7. **tags 一律写成单行内联列表** `tags: [a, b, c]`，不用 YAML 块序列——")
    L.append("   统一写法才能被画布生成脚本与审计脚本无歧义解析。")
    L.append("8. **一个 tag 只表达一个维度**：`image-classification` 这类复合词必须拆成")
    L.append("   `modality/image` + `task/classification` 两个 tag，**不得新造复合词**。")
    L.append("")
    L.append("## 二、七个分面")
    L.append("")
    L.append("**分面是固定的，叶节点是你的。** 给一页选 tag，就是逐分面问一遍自己：")
    L.append("")
    L.append("| 分面 | 收什么 | 判断问题 |")
    L.append("|---|---|---|")
    for f, desc in FACETS:
        L.append(f"| `{f}/` | {_desc_tail(desc)} | {hints.get(f, '')} |")
    L.append("")
    L.append("> 角色 tag `母概念` / `子概念` 不走分面，用于标记概念层级（见硬规则 2）。")
    L.append(">")
    L.append("> **不设第八个分面**：分面是结构，不是词表。一个词若归不进上面任何一面，")
    L.append("> 说明它不该是 tag —— 写进正文即可。")
    L.append("")
    L.append("## 三、查看与维护词表")
    L.append("")
    L.append("| 命令 | 作用 |")
    L.append("|---|---|")
    L.append("| `python .dsh/scripts/tag_vocab.py --list` | **列出当前词表全部词条**（按分面分组） |")
    L.append("| `python .dsh/scripts/tag_vocab.py --check` | 自洽性校验（`map` 指向的 tag 是否存在、有无死词条、分面是否合法） |")
    L.append("| `python .dsh/scripts/tag_vocab.py --emit-doc` | 重新生成本文件（**只有改规则时才需要**） |")
    L.append("| `python .dsh/scripts/tag_audit.py` | 全库审计：未登记 tag、超限、频次分布 |")
    L.append("| `python .dsh/scripts/tag_audit.py --unregistered` | 只列出未登记的 tag |")
    L.append("| `python .dsh/scripts/tag_apply.py` | 按 `map` 迁移历史 tag（**预演**，不写盘） |")
    L.append("| `python .dsh/scripts/tag_apply.py --apply` | 实际改写并生成备份到 `.dsh/tmp/tags-backup-*.json` |")
    L.append("| `python .dsh/scripts/tag_apply.py --rollback <备份>` | 从备份精确还原 tags |")
    L.append("| `python .dsh/scripts/tag_verify_migration.py` | 独立验证：备份 → 重新推导 → 与磁盘逐页比对 |")
    L.append("")
    L.append("> 权威来源是 `<工作区根>/.dsh/tag-vocab.json`。想换一整套领域词表，")
    # 这里刻意用行内代码而不是 markdown 链接：TAGS.md 会跟着安装进用户的知识库，
    # 而 `docs/` 不在安装范围内（只复制 .dsh/、AGENTS.md、templates/），
    # 写成链接就会在用户库里变成悬空链接。用代码路径两种场景都成立。
    L.append("> 见仓库里的 `docs/CUSTOMIZE.md` → 「换 tag 词表」一节。")
    L.append("")
    L.append("## 四、新增 tag 的流程")
    L.append("")
    L.append("1. **先想清楚它属于哪个分面**；若答不出分面，说明它不该是 tag（写进正文即可）。")
    L.append("2. **先查是否已有近义词条**：跑 `tag_vocab.py --list`，并检索 `.dsh/tag-vocab.json` 的 `map`。")
    L.append("   同义、单复数、大小写、连字符差异一律合并到已有词条。")
    L.append("3. **门槛**：该词需在 **≥3 个页面**上有实际检索价值，否则合并到最接近的现有词条。")
    L.append("4. 通过后：在 `.dsh/tag-vocab.json` 的 `canonical` 增加 `叶节点: 中文释义`，")
    L.append("   并在 `map` 登记来源词（含被合并的近义词；一条来源可映射到多个规范 tag）。")
    L.append("5. 运行 `python .dsh/scripts/tag_vocab.py --check` 确认自洽。")
    L.append("6. 运行 `python .dsh/scripts/tag_audit.py` 确认没有未登记 tag 出现在 frontmatter。")
    L.append("")
    L.append("## 五、常见误用（反面清单）")
    L.append("")
    L.append("> 下表用**示例**说明错误模式，帮助你识别同类问题；示例里的词条名不代表你的词表内容，")
    L.append("> 具体以 `.dsh/tag-vocab.json` 为准。")
    L.append("")
    L.append("| ✗ 错误写法 | ✓ 正确写法 | 理由 |")
    L.append("|---|---|---|")
    for bad, good, why in [
        ("同义/大小写并存：`dl`、`deep-learning`、`DL`", "归一到单一词条（如 `method/deep-learning`）", "同义词条必须合并，否则检索被稀释"),
        ("复合词：`image-classification`", "`modality/image` + `task/classification`", "一个 tag 只表达一个维度"),
        ("年份：`2024`", "（删除）", "年份已在 frontmatter 的 `year` / 文件名中"),
        ("模型或数据集专名：`GPT`、`ImageNet`", "`method/foundation-model`、`data/dataset`", "专名靠正文检索，不占 tag 名额"),
        ("实验手段：`ablation`", "`meta/analysis`", "实验方法归入 meta 分面"),
        ("把非综述页标成 `meta/survey`", "改挂 `meta/analysis` 或对应 `task/`", "tag 要描述页面实际是什么"),
        ("一页挂 9 个以上主题 tag", "压到 8 个以内（推荐 3–5）", "挂满等于没挂，区分度归零"),
    ]:
        L.append(f"| {bad} | {good} | {why} |")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# 5. CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Tag 受控词表的自检与文档生成（词表数据在 .dsh/tag-vocab.json）。",
        epilog="示例: python .dsh/scripts/tag_vocab.py --check",
    )
    ap.add_argument("--check", action="store_true", help="校验词表自洽；有问题时退出码 1")
    ap.add_argument("--list", action="store_true",
                    help="列出当前词表全部词条（按分面分组，带中文释义）")
    ap.add_argument("--emit-doc", action="store_true", help="重新生成 TAGS.md（只有改规则时才需要）")
    ap.add_argument("--doc", default=None, help="TAGS.md 输出路径（默认取配置项 files.tags_doc）")
    ap.add_argument("--vocab", default=None, help="词表文件路径（默认取配置项 files.vocab）")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结论")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.vocab:
            reload_vocab(args.vocab)
        require_vocab()
    except VocabError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    vocab_path = resolve_vocab_path(args.vocab)

    # `--list`：把词表本体（数据）与规范文档（TAGS.md）分开之后，
    # 这就是"当前到底允许哪些词"的查询入口。
    if args.list:
        n_all = len(all_canonical_tags())
        print(f"# 词表：{vocab_path}")
        print(f"# 分面 {len(FACET_ORDER)} ｜ 规范 tag {n_all} ｜ 含角色 tag {n_all + len(ROLE_TAGS)}"
              f" ｜ 已登记历史映射 {len(MAP)}")
        for f, desc in FACETS:
            print(f"\n[{f}/]  {_desc_tail(desc)}")
            for leaf in sorted(CANONICAL[f]):
                print(f"  {f}/{leaf:<28} {CANONICAL[f][leaf]}")
        print("\n[角色 tag]  不带前缀，且必须是 tags 的第一项")
        for r in ROLE_TAGS:
            print(f"  {r}")
        return 0

    errs = check()
    n_canon = len(all_canonical_tags())

    if errs:
        if args.quiet:
            print(f"词表自检未通过：{len(errs)} 项问题（{vocab_path}）")
        else:
            print(f"词表文件: {vocab_path}")
            print(f"分面数: {len(FACET_ORDER)}   规范 tag: {n_canon}   含角色: {n_canon + len(ROLE_TAGS)}")
            print("\n自检失败:")
            for e in errs:
                print("  ✗", e)
        return 1

    if args.quiet:
        print(f"词表自检通过 ✓  分面 {len(FACET_ORDER)}  规范 tag {n_canon}  "
              f"含角色 {n_canon + len(ROLE_TAGS)}  映射 {len(MAP)}")
    else:
        print(f"词表文件: {vocab_path}")
        print(f"分面数: {len(FACET_ORDER)}   规范 tag: {n_canon}   含角色: {n_canon + len(ROLE_TAGS)}")
        print(f"已登记历史 tag: {len(MAP)}   其中删除: {sum(1 for v in MAP.values() if not v)}")
        for f, desc in FACETS:
            print(f"  {f + '/':<12} {len(CANONICAL[f]):3d}  {desc}")
        print("\n自检通过 ✓")

    if args.emit_doc:
        out = Path(args.doc) if args.doc else (WS / cfg("files", "tags_doc", default="TAGS.md"))
        out.parent.mkdir(parents=True, exist_ok=True)
        # 显式 LF：Path.write_text 在 Windows 上会把 \n 翻成 \r\n，导致同一个生成物
        # 在不同平台上行尾不同。仓库自己靠 .gitattributes 在提交时纠正了，但用户的知识库
        # 里没有那份配置——所以生成端就要写对。
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(emit_doc())
        if not args.quiet:
            print(f"[doc] -> {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
