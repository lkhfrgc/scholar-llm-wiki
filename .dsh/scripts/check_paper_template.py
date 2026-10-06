#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查论文讲解页是否符合 ingest 论文模板，并可做全库死链检查。

用法：
    python .dsh/scripts/check_paper_template.py                  # 汇总 + 列出不合规页面
    python .dsh/scripts/check_paper_template.py --links          # 额外做全库死链检查
    python .dsh/scripts/check_paper_template.py --json out.json  # 机器可读结果（`-` 表示写到 stdout）
    python .dsh/scripts/check_paper_template.py --quiet          # 只输出一行结论

论文目录由 `.dsh/wiki.config.json` 的 `wiki_types`（子目录名 → type 值）推出，改目录名无需改脚本。

判定项（缺任一项即视为不合规）：
  1. 有 `## 我的批注` 小节
  2. `## 方法` 下有 `### 0. 全局视图`
  3. 有「下标命名约定」表
  4. 每个 `$$...$$` 公式块附近有 `#### 公式 (N)` 标题（公式数 > 0 时，公式块数与公式数应匹配）
  5. 有「符号 / 含义 / 形状」表，且张数 >= 公式块数
  6. 有「**人话**」讲解，处数 >= 公式块数
  7. 『模块名称解释』出现次数 >= 1
  8. 有 `## 关联连接` 与 `## 原始来源`

退出码：0 = 全部合规；1 = 有不符（页面不合规，或 `--links` 发现死链）；2 = 用法错误。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# 同目录的共享路径层：本仓库内唯一允许"找路径"的地方，禁止再写绝对路径
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, cfg, ensure_utf8_stdio, wiki_dir  # noqa: E402


def _wiki_subdir_for(type_name, fallback):
    """按 `wiki_types`（wiki 子目录名 → frontmatter 的 type 值）反查子目录。

    配置里改了目录名（例如 papers → 论文）本脚本无需改动；
    表里没有对应 type 时回退到 `fallback`，保证脚本不会因为缺键直接崩。
    """
    for sub, t in (cfg("wiki_types", default={}) or {}).items():
        if t == type_name:
            return wiki_dir(sub)
    return wiki_dir(fallback)


PAP = _wiki_subdir_for("paper", "papers")

# 判定项在内部用中文键（直接进人类可读输出），JSON 里换成稳定的英文键
METRIC_KEYS = {
    "批注": "annotation",
    "全局视图": "global_view",
    "命名约定": "naming_convention",
    "公式块": "formula_headers",
    "符号表": "symbol_tables",
    "人话": "plain_words",
    "模块解释": "module_notes",
    "公式数": "formula_blocks",
    "关联连接": "related_links",
    "原始来源": "sources",
}

# --------------------------------------------------------------------------
# 死链检查：链接是否存在，按 Obsidian 规则——**basename 全局唯一**判定
# --------------------------------------------------------------------------
LINK_RE = re.compile(r"\[\[([^\[\]\|\\#]+)")
FENCE_RE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$")
UNCLOSED_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# 注释：HTML 注释与 Obsidian 注释里的 [[]] 都不是真实引用。
# Obsidian 注释要求开头的 `%%` 前面不是数字或反斜杠，避免把正文里的 `50%%` / `\%` 误当注释。
HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
OPEN_HTML_COMMENT_RE = re.compile(r"<!--")
OBSIDIAN_COMMENT_RE = re.compile(r"(?s)(?<![\d\\])%%.*?%%")

# 文档占位符：模板/说明里的示例名不是真实引用
PLACEHOLDER_NAMES = {
    "页面名称", "页面名", "概念名称", "母页名称", "子页名称",
    "EntityName", "ConceptName", "摘要-source-slug", "index.md",
}


def read_text(path):
    """读取文本：显式 UTF-8，并容忍 BOM（`utf-8-sig`）。

    BOM 会让 frontmatter 的首行变成 `\\ufeff---`，YAML 解析直接失败；
    编辑器差异不该让同一份内容被误判，所以统一按 utf-8-sig 读。
    """
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def md_names(d):
    """目录下的 .md 文件名；目录不存在时返回空列表（空库照样能跑，不抛栈）。"""
    try:
        return sorted(fn for fn in os.listdir(d) if fn.endswith(".md"))
    except OSError:
        return []


def mask_code(text):
    """把「不是正文引用」的部分替换成等长空白（长度不变，偏移不变）。

    屏蔽四类：

    1. **HTML 注释** `<!-- … -->` —— `index.md` 模板里被注释掉的示例条目
    2. **Obsidian 注释** `%% … %%` —— 用户临时注释掉条目时同样不是引用
       （要求开场 `%%` 前面不是数字或反斜杠，避免误伤 `50%%` / `\\%`）
    3. **围栏代码块**（含未闭合的：从开始处一直屏蔽到文件末尾）
    4. **行内代码** `` `[[示例]]` ``

    ⚠️ 顺序很重要：**先屏蔽注释再屏蔽围栏**。反过来的话，注释里的 ``` 会被当成
    未闭合围栏，把后面的正文整段吃掉，真正的死链就漏报了。
    等长替换保证行号与字符偏移不变。
    """
    def blank(m):
        return " " * (m.end() - m.start())

    out = HTML_COMMENT_RE.sub(blank, text)
    m = OPEN_HTML_COMMENT_RE.search(out)   # 未闭合的 HTML 注释：屏蔽到文件末尾
    if m:
        out = out[:m.start()] + " " * (len(out) - m.start())
    out = OBSIDIAN_COMMENT_RE.sub(blank, out)
    out = FENCE_RE.sub(blank, out)
    m = UNCLOSED_FENCE_RE.search(out)      # 未闭合的围栏：从其开始处屏蔽到文件末尾
    if m:
        out = out[:m.start()] + " " * (len(out) - m.start())
    return INLINE_CODE_RE.sub(blank, out)


def check(path):
    t = read_text(path)
    n_formula = len(re.findall(r"\$\$", t)) // 2
    r = {
        "批注": bool(re.search(r"(?m)^##\s*我的批注", t)),
        "全局视图": bool(re.search(r"(?m)^###\s*0\.\s*全局视图", t)),
        "命名约定": "下标命名约定" in t,
        "公式块": len(re.findall(r"(?m)^####\s*公式", t)),
        "符号表": len(re.findall(r"\|\s*符号\s*\|\s*含义\s*\|\s*形状\s*\|", t)),
        "人话": len(re.findall(r"\*\*人话\*\*", t)),
        "模块解释": len(re.findall(r"模块名称解释", t)),
        "公式数": n_formula,
        "关联连接": bool(re.search(r"(?m)^##\s*关联连接", t)),
        "原始来源": bool(re.search(r"(?m)^##\s*原始来源", t)),
    }
    bad = []
    if not r["批注"]:
        bad.append("缺我的批注")
    if not r["全局视图"]:
        bad.append("缺全局视图")
    if not r["命名约定"]:
        bad.append("缺下标命名约定")
    if n_formula > 0:
        if r["公式块"] == 0:
            bad.append("有公式但无公式块")
        elif r["公式块"] < n_formula * 0.6:
            bad.append("公式块偏少(%d/%d)" % (r["公式块"], n_formula))
        if r["符号表"] < r["公式块"]:
            bad.append("符号表不足(%d/%d)" % (r["符号表"], r["公式块"]))
        if r["人话"] < r["公式块"]:
            bad.append("人话不足(%d/%d)" % (r["人话"], r["公式块"]))
    if r["模块解释"] < 1:
        bad.append("缺模块名称解释")
    if not r["关联连接"]:
        bad.append("缺关联连接")
    if not r["原始来源"]:
        bad.append("缺原始来源")
    return r, bad


def build_name_index(root):
    """建立链接目标索引：**basename 全局唯一**（Obsidian 按文件名解析，与目录无关）。

    索引覆盖整个工作区，因此工作区根的笔记、`我的研究/` 之类目录、以及
    `.canvas` / `.pdf` 附件都是合法目标；只索引 `wiki/` 会把它们全判成死链。
    跳过点目录（`.dsh`、`.obsidian`、`.git`…）与 `node_modules`，
    否则备份/缓存里的同名文件会把死链"救活"。
    """
    names = set()
    for root_dir, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for fn in filenames:
            names.add(fn)                      # 附件：[[图.canvas]]
            if fn.endswith(".md"):
                names.add(fn[:-3])             # 常规页面：[[页面名]]
    return names


def link_sources():
    """死链检查的扫描源：`wiki/` 全部页面 + 工作区根的 index.md。

    * `log.md`（`files.log`）是 append-only 的历史记录，其中的 `[[页面]]` 反映当时状态，
      删页/改名后必然"死链"，据此报错只会淹没真问题 → 不参与判定
    * AGENTS.md / docs / templates 等说明性文件里的链接是格式示例，不是真实引用 → 不扫描
    * 文件内部被 HTML 注释 / Obsidian 注释 / 代码块包住的行由 `mask_code()` 屏蔽，
      因此"注释掉的条目"和"写在围栏里的模板"都不会变成假死链
    """
    log_name = Path(cfg("files", "log", default="log.md")).name
    index_path = WS / cfg("files", "index", default="index.md")
    srcs = []
    for root_dir, dirnames, filenames in os.walk(wiki_dir()):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        srcs += [Path(root_dir) / fn for fn in sorted(filenames) if fn.endswith(".md")]
    if index_path.is_file():
        srcs.append(index_path)
    return sorted((p for p in srcs if p.name != log_name), key=lambda p: str(p))


def check_links():
    """返回 [(来源页名, 死链目标), ...]；同一目标多次出现按多次计。"""
    names = build_name_index(WS)
    dead = []
    for src in link_sources():
        text = mask_code(read_text(src))
        for m in LINK_RE.finditer(text):
            g = m.group(1).strip()
            if not g or "/" in g or g in PLACEHOLDER_NAMES:  # 路径型引用 / 占位符
                continue
            if g not in names:
                dead.append((src.stem, g))
    return dead


def write_json_file(path, payload):
    """写 JSON：UTF-8、LF、ensure_ascii=False（中文可读、diff 稳定）。`-` 表示写 stdout。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path == "-":
        sys.stdout.write(text)
        return
    p = Path(path)
    if str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_parser():
    p = argparse.ArgumentParser(
        prog="python .dsh/scripts/check_paper_template.py",
        description="检查论文讲解页是否符合 ingest 论文模板（8 项判定），可选做全库死链检查。",
        epilog="退出码：0 = 全部合规；1 = 有不符（页面不合规，或 --links 发现死链）；2 = 用法错误。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--links", action="store_true", help="额外做全库死链检查（按 basename 全局唯一判定）")
    p.add_argument("--json", metavar="PATH", help="把机器可读结果写到 PATH；写 `-` 表示输出到 stdout")
    p.add_argument("--quiet", action="store_true", help="只输出一行结论（配合 --json - 时结论走 stderr）")
    return p


def main(argv=None):
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    # 机器可读结果直接进 stdout 时，人类可读摘要改走 stderr，避免污染管道
    out = sys.stderr if args.json == "-" else sys.stdout

    rows = []
    for fn in md_names(PAP):
        r, bad = check(os.path.join(PAP, fn))
        rows.append((fn[:-3], r, bad))
    ok = [x for x in rows if not x[2]]

    if args.quiet:
        line = "论文页 %d ｜ 合规 %d ｜ 不合规 %d" % (len(rows), len(ok), len(rows) - len(ok))
    else:
        print("论文页总数 %d ｜ 合规 %d ｜ 不合规 %d" % (len(rows), len(ok), len(rows) - len(ok)), file=out)
        if rows:
            print("合规率 %.0f%%" % (100.0 * len(ok) / len(rows)), file=out)
        print("\n=== 不合规页面 ===", file=out)
        for name, r, bad in rows:
            if bad:
                print("  %-40s 公式%2d 块%2d 表%2d 人话%2d 模块%d ｜ %s" % (
                    name, r["公式数"], r["公式块"], r["符号表"], r["人话"], r["模块解释"], "、".join(bad)), file=out)
        line = None

    dead = []
    if args.links:
        dead = check_links()
        if args.quiet:
            line += " ｜ 死链 %d" % len(dead)
        else:
            print("\n=== 死链检查（全库，按 basename 判定）===", file=out)
            for src, target in dead:
                print("  %s → [[%s]]" % (src, target), file=out)
            print("死链合计 %d" % len(dead), file=out)

    if line is not None:
        print(line, file=out)

    if args.json:
        write_json_file(args.json, {
            "papers": {
                "total": len(rows),
                "compliant": len(ok),
                "violations": [
                    {"page": name, "problems": bad, "metrics": {METRIC_KEYS[k]: v for k, v in r.items()}}
                    for name, r, bad in rows if bad
                ],
            },
            "dead_links": {
                "scanned": bool(args.links),
                "count": len(dead),
                "items": [{"source": s, "target": t} for s, t in dead],
            },
        })

    return 1 if (len(rows) - len(ok) > 0 or dead) else 0


if __name__ == "__main__":
    sys.exit(main())
