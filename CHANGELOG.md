# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增

- **Team 子系统（论文来源团队）**：论文页 frontmatter 新增 `team` 字段（**列表**，多单位合作全记，
  按署名上标顺序排列），回答"这篇论文来自哪个团队"。数据在 `.dsh/team-vocab.json`
  （`teams`: 规范名 → `{base, type, note}`；`aliases`: 来源写法 → 规范名），引擎 `team_vocab.py`
  （`--list` / `--check` / `--emit-doc` / `--resolve`）、`team_apply.py`
  （映射 → 预演 → `--apply` → `--rollback`，写盘时顺手删除旧的 `affiliations` 字段）、
  `team_audit.py`（缺 `team` / 未登记团队 / 残留 `affiliations` / 归一化重名 / 结构，退出码说话）。
  **规范与数据分家**：`TEAMS.md` 只写规则、不列团队，由 `--emit-doc` 生成。
- **两级粒度**：机构级 `University of X`（或企业名）与实验室/课题组级
  `University of X (Key Laboratory of Y)` 共存 —— 实验室条目的 `base` 指向其上级机构，
  `--check` 保证上级机构也被登记；这样既能按实验室精确定位，也能按机构聚合。
- **团队词表出厂为空（冷启动）**：与 tag 一样是封闭词表，但团队是**事实字段**——
  **没有「≥3 个页面」门槛**，唯一的纪律是「同一个团队只能有一个规范名」（靠 `aliases` 归并
  `Meta AI` / `FAIR` / `Facebook AI Research` 这类写法）。首次摄入时由 agent 从论文**首页署名块**
  （编号行，或 IEEE 格式的首页脚注）判定，并先登记再写页面。

### 变更

- `AGENTS.md`：新增「Team 规范」一节；目录树加入 `TEAMS.md`；内容分类表的论文页一行补 `team` 要求；
  工具链速查加入 4 条团队命令。
- `ingest` 技能：论文页模板加 `team:` 字段；步骤 3 前置「先定 team」8 步
  （含 IEEE 脚注读法、别名查询、新团队登记流程、`待确认` 规则）。
- `lint` 技能：**九项 → 十项检查**，新增「检查 10：Team 规范」；检查 1 要求论文页必须有 `team`。
- `check_paper_template.py`：新增判定项 9「缺来源团队」。
- `setup_wiki.py` / `selfcheck.py`：安装与体检纳入 `team-vocab.json` 与 `TEAMS.md`
  （`selfcheck` 的子脚本自检加入 `team_vocab.py --check`）。
- `.dsh/wiki.config.json`：新增 `files.teams_doc` / `files.team_vocab`。
- CI：新增 `team_vocab.py --check` 步骤；安装后体检加入 `team_audit.py`。
- 文档：README / MANUAL / ARCHITECTURE / CUSTOMIZE / INSTALL / CONTRIBUTING 同步补齐
  （ARCHITECTURE 增加 team 子系统结构图，CUSTOMIZE 增加「换团队词表」一节）。

## [1.0.0] — 2026-10-06

首个公开发布版：从作者自用的知识库工作流中抽出的工具包，**面向科研与文献整理**
（论文、书籍、课件、网页长文 → 结构化、高度互链的 Obsidian 知识库）。

> 命名说明：项目名 **Scholar LLM Wiki** 指这个工具包；**LLM Wiki** 指 Andrej Karpathy
> 那份方法论（[`llm-wiki.md`](https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw)），
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
- **tag 子系统**：`tag_vocab.py`（引擎 + `--list` / `--check` / `--emit-doc`）、
  `tag_apply.py`（幂等迁移，字节级最小改动，支持回滚）、`tag_audit.py`（审计，退出码说话）、
  `tag_verify_migration.py`（独立复核）。
  **规范与数据分家**：`TAGS.md` 只承载**不随项目变化的规则**（七个分面、硬规则、新增流程、
  反面清单），具体词条一律留在 `.dsh/tag-vocab.json`，用 `--list` 现查。
  这样换一套领域词表不必重写规范文档，读者也不会把某个初始词表误当成"工具自带的推荐词表"。
- **词表出厂为空（冷启动）**：`.dsh/tag-vocab.json` 只给七个分面的骨架，**不含任何具体词条**
  ——tag 是最贴着研究领域的东西，预设一套既会误导别的领域的使用者，也会让人无意识接受
  一套不属于自己的分类。词表随第一次 `/ingest` 长出来：**冷启动阶段免于「≥3 个页面」门槛**
  （第一轮摄入不可能攒够页面），但必须在同一次摄入收尾前登记进 `canonical` 与 `map`。
  `tag_audit.py` 认得出冷启动状态，会把未登记 tag 报成「**待登记**」而非「违规」，
  并给出登记路径；某个分面一旦有条目即恢复常规门槛。
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

基础方法论来自 **Andrej Karpathy 的 [`llm-wiki.md`](https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw)**：
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

[1.0.0]: https://github.com/lkhfrgc/scholar-llm-wiki/releases/tag/v1.0.0
