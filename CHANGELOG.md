# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] — 2026-10-06

首个公开发布版：从作者自用的知识库工作流中抽出的工具包，**面向科研与文献整理**
（论文、书籍、课件、网页长文 → 结构化、高度互链的 Obsidian 知识库）。

> 命名说明：项目名 **ScholarWiki Kit** 指这个工具包；**LLM Wiki** 指 Andrej Karpathy
> 那份方法论（[`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)），
> 两者不是一个东西，别混。用户自己知识库的名字由 `.dsh/wiki.config.json` 的 `wiki_name` 决定
> （默认 `科研 Wiki`）。

### 新增

- **架构契约** `AGENTS.md`：目录权限边界（`raw/` 不可变）、五类页面与 `type` 对应、
  命名规则、双链要求、tag 受控词表规范、母/子概念分层、Canvas 同步、Skills 调度指引。
- **三个技能**：`ingest`（9 步摄入流水线）、`query`（带双链引用的检索综合）、
  `lint`（九项健康巡检，默认只读）。
- **环境层** `wiki_env.py`：全仓唯一允许"找路径"的模块 —— 工作区根推导、
  Obsidian 库根前缀自动探测、配置深合并、跨平台解释器解析、路径自省 CLI。
- **配置化**：`.dsh/wiki.config.json` 描述全部目录名/文件名/领域/画布命名；
  `.dsh/tag-vocab.json` 承载 tag 词表数据。仓库内零绝对路径、零机器信息。
- **tag 子系统**：`tag_vocab.py`（引擎 + `--check` / `--emit-doc`）、
  `tag_apply.py`（幂等迁移，字节级最小改动，支持回滚）、`tag_audit.py`（审计，退出码说话）、
  `tag_verify_migration.py`（独立复核）。
- **概念地图** `gen_canvas.py`：总图 + 单族图，结构指纹驱动 `--check`，
  卡片一律 `text` 节点 + 双链（不用 `file` 节点）。
- **PDF 三件套**：`fetch_source.py`（arXiv/DOI → LaTeX 公式真值，仅标准库）、
  `extract_pdf.py`（PyMuPDF 全文抽取 + 上下标重建 + 公式块 bbox）、
  `crop_equations.py`（Pillow 按 bbox 裁公式小图）。
- **校验与运维**：`check_paper_template.py`（论文页 8 项模板判定 + 死链检查）、
  `selfcheck.py`（环境/依赖/骨架体检）、`setup_wiki.py`（幂等初始化）、
  `repo_lint.py`（提交前的绝对路径/用户名/凭据/BOM 泄露扫描）。
- **文档**：
  - `README.md` —— 含「运行环境」说明（**最佳体验 = Obsidian + DSH**，附缺一不可的降级对照）
    与一句话安装提示词；
  - `docs/MANUAL.md` —— **用户手册**：从「这东西是干什么的」到「出问题怎么修」，
    含五个真实使用场景、三个技能的详细用法、目录说明书、Tag 系统通俗版、
    概念分层与 Canvas 用法、FAQ、分诊表、术语表、进阶用法；
  - `docs/INSTALL.md`、`docs/CUSTOMIZE.md`、`docs/ARCHITECTURE.md`。
- **提交前自检** `repo_lint.py`：绝对路径 / 用户名 / 邮箱 / 凭据 / UTF-8 BOM /
  JSON 与 Python 可解析 / **Markdown 本地链接失效**（围栏代码块、行内代码、
  HTML 与 Obsidian 注释里的示例链接会被屏蔽，避免假死链淹没真问题）。

### 方法论出处

基础方法论来自 **Andrej Karpathy 的 [`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**：
让 LLM 增量维护一个持久的、可复利增长的 wiki，而不是每次提问都从原始文档重新检索。

具体对应关系（三层架构 → `raw/`/`wiki/`/`AGENTS.md`；Ingest/Query/Lint → 三个同名技能；
`index.md`/`log.md` 的语义；「Obsidian 是 IDE，LLM 是程序员，wiki 是代码库」）
以及本仓库在其之上补的工程约束（tag 受控词表、概念分层与 Canvas、以退出码说话的校验、
PDF 公式流水线、零硬编码），见 README 的[「方法论出处」](README.md#方法论出处)一节。

### 设计取舍

- **词表与引擎分离**：词表放 JSON 才能被审计、被 diff、被迁移。
- **可选项优雅退化**：缺 PyMuPDF / Pillow / LibreOffice Kit 时打印可复制的修复命令，
  而不是抛 traceback。
- **审计用退出码说话**：所有校验脚本 `0 = 通过`，可直接接 CI。
- **假死链必须屏蔽**：文档、模板、注释里到处是「链接的写法」而不是「链接本身」。
  不屏蔽这些，一次检查就报几十条假问题，真问题反而被淹没。

[1.0.0]: https://github.com/lkhfrgc/scholar-wiki-kit/releases/tag/v1.0.0
