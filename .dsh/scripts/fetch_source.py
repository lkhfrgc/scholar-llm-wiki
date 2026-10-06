#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 arXiv / DOI 抓取论文的公式真值（LaTeX），供 ingest 使用。

为什么需要它：PDF 文本层抽取公式必然有损——上下标被拉平、分式被拆行，
而 LaTeX 数学子集字体（CMEX/CMMI/CMSY…）常常没有 ToUnicode 表，行间 Σ 会
被解成 "P"/"X"。arXiv 的 HTML 版（LaTeXML 产物）里每个 <math> 都带
`alttext`，那就是**逐字准确的 LaTeX 源码**，比任何 OCR/视觉识别都可靠。

依赖：**仅标准库**（urllib + re）——Python 3.9+ 即可运行，不需要项目 venv。
只有 `--from-pdf`（从 PDF 首页自动识别 arXiv ID / DOI）需要 PyMuPDF，
这时才要换成装了 PyMuPDF 的解释器；也可以直接手写 `--arxiv` / `--doi` 绕开它。

解释器写法对照（下文 `<venv-python>` = 装了 PyMuPDF 的那个解释器）：
    harness 自带 Python   直接写 `python`
    项目 venv             Windows      `.dsh\\venv\\Scripts\\python.exe`
                          macOS/Linux  `.dsh/venv/bin/python`

    # 需要 PyMuPDF 时先建隔离环境再装依赖
    python -m venv .dsh/venv
    # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt
    # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt

用法：
    # 自动识别（需 PyMuPDF）
    <venv-python> .dsh/scripts/fetch_source.py --from-pdf raw/papers/<paper>.pdf -o <tmp>/paper.source.md

    # 已知编号（任意 Python 3.9+，只需要标准库）
    python .dsh/scripts/fetch_source.py --arxiv 1706.03762v7 -o <tmp>/paper.source.md
    python .dsh/scripts/fetch_source.py --doi 10.1000/xyz123 -o <tmp>/paper.source.md

中间产物目录由 `.dsh/wiki.config.json` 的 `dirs.tmp` 决定（默认 `.dsh/tmp`，
即 `wiki_env.tmp_dir()`），不要在脚本或命令里写死路径。

常用选项：
    --filter display|all   默认 display：只保留「值得写进笔记」的公式（长式或含 \\frac/\\sum 等）
    --max-formulas N       上限（默认 300），超出会截断并注明
    --json PATH            另存完整 JSON（全部公式 + 元信息，ensure_ascii=False）
    --timeout SECONDS      默认 30

退出码：0 成功；1 缺依赖/环境问题；2 用法错误；
        3 首页未识别出 arXiv ID / DOI；4 连上了但一条公式都没拿到。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Tuple

# ── 路径与编码：全仓唯一来源是 wiki_env ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_env import WS, ensure_utf8_stdio, tmp_dir  # noqa: E402

ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
MATH_ALTTEXT_RE = re.compile(r"<math[^>]*?\salttext=\"([^\"]*)\"", re.S)
TITLE_RE = re.compile(r"<h1[^>]*class=\"[^\"]*ltx_title[^\"]*\"[^>]*>(.*?)</h1>", re.S)
ABSTRACT_RE = re.compile(r"<div[^>]*class=\"[^\"]*ltx_abstract[^\"]*\"[^>]*>(.*?)(?:<div|</section)", re.S)

DISPLAY_MARKERS = (
    "\\frac", "\\sum", "\\int", "\\prod", "\\sqrt", "\\min", "\\max", "\\log",
    "\\exp", "\\begin{", "\\left", "\\partial", "\\nabla", "\\arg",
    "\\operatorname", "\\mathcal{L}",
)

USER_AGENT = "scholar-llm-wiki/1.0 (+local knowledge base ingest; contact: vault owner)"

PYMUPDF_HINT = (
    "错误：未安装 PyMuPDF —— `--from-pdf` 需要它（`--arxiv` / `--doi` 只用标准库，可直接用）。\n"
    "安装：\n"
    "  python -m venv .dsh/venv\n"
    "  # Windows:     .dsh\\venv\\Scripts\\python.exe -m pip install -r .dsh/requirements.txt\n"
    "  # macOS/Linux: .dsh/venv/bin/python -m pip install -r .dsh/requirements.txt"
)


def _rel(path: Path) -> str:
    """把工作区内路径显示成相对形式，避免帮助文本里出现机器专属的绝对路径。"""
    try:
        return path.relative_to(WS).as_posix()
    except ValueError:
        return path.as_posix()


def fetch(url: str, timeout: float = 30.0, accept: str | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_math(html_text: str) -> List[str]:
    out: List[str] = []
    for raw in MATH_ALTTEXT_RE.findall(html_text):
        latex = html.unescape(raw).strip()
        # alttext 里可能含换行（如 \begin{subarray} 内的 \\ 换行），
        # 折叠成空格以保持一条公式一行，便于 Markdown 列表与后续引用
        latex = re.sub(r"\s*\n\s*", " ", latex)
        if latex:
            out.append(latex)
    return out


def dedupe(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def is_display(latex: str) -> bool:
    if len(latex) >= 40:
        return True
    return any(marker in latex for marker in DISPLAY_MARKERS) and len(latex) >= 12


def _load_fitz():
    """延迟导入 PyMuPDF；缺失时打印安装指引并以退出码 1 结束。

    延迟到调用点是为了让 `--help` 与 `--arxiv/--doi` 路径在没装 PyMuPDF 的
    解释器上也能正常工作。
    """
    try:
        # PyMuPDF >= 1.24 改用 `pymupdf` 作为导入名；旧别名 `fitz` 仍可用，
        # 但导入时会打弃用横幅，所以优先新名。
        import pymupdf as fitz  # type: ignore
        return fitz
    except ImportError:
        pass
    try:
        import fitz  # type: ignore # PyMuPDF（旧别名）
        return fitz
    except ImportError:
        print(PYMUPDF_HINT, file=sys.stderr)
        raise SystemExit(1)


def detect_in_pdf(pdf_path: str) -> Tuple[str | None, str | None]:
    """从 PDF 前两页识别 arXiv ID / DOI（需要 PyMuPDF）。"""
    fitz = _load_fitz()
    doc = fitz.open(pdf_path)
    head = "".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
    doc.close()
    arxiv = ARXIV_RE.search(head)
    doi = DOI_RE.search(head)
    arxiv_id = None
    if arxiv:
        arxiv_id = arxiv.group(1) + (arxiv.group(2) or "")
    return arxiv_id, (doi.group(1) if doi else None)


def try_arxiv(arxiv_id: str, timeout: float) -> Tuple[str | None, str | None, List[str]]:
    """返回 (实际 URL, HTML, 公式列表)。依次尝试 arXiv 原生 HTML、无版本号、ar5iv。"""
    base = re.sub(r"v\d+$", "", arxiv_id)
    candidates = []
    if arxiv_id != base:
        candidates.append(f"https://arxiv.org/html/{arxiv_id}")
    candidates.append(f"https://arxiv.org/html/{base}")
    candidates.append(f"https://ar5iv.labs.arxiv.org/html/{base}")

    errors = []
    for url in candidates:
        try:
            page = fetch(url, timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url} → {exc}")
            continue
        formulas = dedupe(extract_math(page))
        if formulas:
            return url, page, formulas
        errors.append(f"{url} → 页面里没有 <math alttext>")
    print("[警告] arXiv 取源失败：\n  " + "\n  ".join(errors), file=sys.stderr)
    return None, None, []


def try_doi(doi: str, timeout: float) -> Tuple[str | None, str | None, List[str], str]:
    url = f"https://doi.org/{doi}"
    try:
        page = fetch(url, timeout, accept="text/html,application/xhtml+xml")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[警告] DOI 解析失败：{url} → {exc}", file=sys.stderr)
        return None, None, [], ""
    formulas = dedupe(extract_math(page))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = strip_tags(title_match.group(1)) if title_match else ""
    return url, page, formulas, title


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="抓取 arXiv/DOI 论文的 LaTeX 公式真值（PDF 公式抽取的可信替代来源）",
        epilog=f"中间产物目录（来自配置）：{_rel(tmp_dir())}",
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-pdf", help="从 PDF 首页自动识别 arXiv ID / DOI（需 PyMuPDF）")
    src.add_argument("--arxiv", help="arXiv ID，如 1706.03762 或 1706.03762v7")
    src.add_argument("--doi", help="DOI，如 10.1000/xyz123")
    ap.add_argument("-o", "--output", default=None, help="输出 Markdown 路径（缺省打印到 stdout）")
    ap.add_argument("--json", dest="json_path", default=None, help="另存完整 JSON")
    ap.add_argument("--filter", choices=["display", "all"], default="display",
                    help="display（默认）只保留值得写进笔记的公式；all 保留全部")
    ap.add_argument("--max-formulas", type=int, default=300, help="公式条数上限（默认 300）")
    ap.add_argument("--timeout", type=float, default=30.0, help="单次请求超时秒数（默认 30）")
    args = ap.parse_args(argv)

    arxiv_id = args.arxiv
    doi = args.doi
    if args.from_pdf:
        arxiv_id, doi = detect_in_pdf(args.from_pdf)
        if not arxiv_id and not doi:
            print(f"错误：{args.from_pdf} 首页未找到 arXiv ID 或 DOI；请手写 --arxiv/--doi。",
                  file=sys.stderr)
            return 3

    url = page = None
    formulas: List[str] = []
    title = abstract = ""

    if arxiv_id:
        url, page, formulas = try_arxiv(arxiv_id, args.timeout)
        if page:
            tm = TITLE_RE.search(page)
            title = strip_tags(tm.group(1)) if tm else ""
            am = ABSTRACT_RE.search(page)
            abstract = strip_tags(am.group(1))[:1500] if am else ""
    if not formulas and doi:
        url, page, formulas, title = try_doi(doi, args.timeout)

    if not formulas:
        print(
            "错误：没有取到任何公式。可选项：① 换 DOI/arXiv 编号重试；"
            "② 走视觉路径（官方 LibreOffice Kit 渲染页图 + crop_equations.py 裁剪核对）。",
            file=sys.stderr,
        )
        return 4

    total = len(formulas)
    kept = formulas if args.filter == "all" else [f for f in formulas if is_display(f)]
    truncated = len(kept) > args.max_formulas
    kept = kept[: args.max_formulas]

    lines = ["# 公式与元信息（PDF 抽取的可信替代来源）", ""]
    lines.append(f"- 源文件：{args.from_pdf or '(未指定 PDF)'}")
    if arxiv_id:
        lines.append(f"- arXiv：{arxiv_id}")
    if doi:
        lines.append(f"- DOI：{doi}")
    if url:
        lines.append(f"- 抓取地址：{url}")
    lines.append(f"- 公式总数：{total}；本表收录：{len(kept)}"
                 + ("（已按 --filter display 过滤）" if args.filter == "display" else "")
                 + ("（已截断，见 --max-formulas）" if truncated else ""))
    lines.append("")
    if title:
        lines.append("## 标题")
        lines.append("")
        lines.append(title)
        lines.append("")
    if abstract:
        lines.append("## 摘要（HTML 提取，可能有缺漏，以 PDF 为准）")
        lines.append("")
        lines.append(abstract)
        lines.append("")
    lines.append("## 公式表（LaTeX，来自 MathML alttext，按原文出现顺序）")
    lines.append("")
    for i, latex in enumerate(kept, 1):
        lines.append(f"{i}. ${latex}$")
    lines.append("")
    lines.append("> 用法：这是**公式真值**，可直接写进 wiki 页面；"
                 "PDF 文本路径提取出的公式若与此处不一致，以此表为准。")

    output = "\n".join(lines)
    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[完成] {out_path.resolve()}（{len(kept)}/{total} 条公式，{len(output)} 字符）",
              file=sys.stderr)
    else:
        print(output)

    if args.json_path:
        payload = {
            "source_pdf": args.from_pdf,
            "arxiv": arxiv_id,
            "doi": doi,
            "url": url,
            "title": title,
            "abstract": abstract,
            "formula_count": total,
            "formulas_all": formulas,
            "formulas_display": kept,
        }
        p = Path(args.json_path)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[完成] JSON 已写入 {p.resolve()}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
