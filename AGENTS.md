# 语言设定与核心角色 (Global Rules)

- **语言指令**：无论输入何种语言，你需要使用**简体中文**进行回复和知识库的编写，对于部分专有概念、名词可以使用英文辅助解释。（可用 `.dsh/wiki.config.json` 的 `language` 字段改为其它语言，改了以后本文件的相关表述需同步调整。）
- **角色定义**：你正在维护一个 **LLM Wiki**（方法论来自 Andrej Karpathy 的 [`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：让 LLM 增量维护一个持久的、可复利增长的 wiki，而不是每次提问都从原始文档重新检索），你的任务是将碎片化的信息编译成结构化、高度相互链接的 Obsidian 知识库。

> ⚠️ **目录名可变，配置是唯一权威**：本文件写的 `wiki/`、`raw/`、`index.md` 等都是**默认值**，全部由 `.dsh/wiki.config.json` 定义。任何时刻不确定路径，先跑：
>
> ```bash
> python .dsh/scripts/wiki_env.py --paths
> ```
>
> 该命令输出工作区根、库根前缀与所有实际路径。**不要猜路径，也不要凭记忆写死**。

## 目录架构

```
<工作区根>/
├── AGENTS.md                  # 本文件：Agent 指令与目录契约
├── TAGS.md                    # Tag 规范：只写规则不列词条（生成物，勿手改）
├── index.md                   # 所有页面的目录（AI 维护）
├── log.md                     # 操作日志（AI 维护，append-only）
├── 我的研究/                   # 存放你自己的研究内容（AI 不主动改写）
├── 周报/                       # 领域速报（非 raw 层，可改可删可重排）
│   └── <域>/                   # 每域一个子目录，域列表见配置的 domains
├── raw/                       # 原始资料（人类维护，不可变）
│   ├── research/              # 待处理收件箱（放入待摄入的资料）
│   ├── papers/                # 论文 PDF/markdown
│   ├── book/                  # 书籍
│   ├── courses/               # 课件、课程笔记
│   ├── clips/                 # 网页剪藏（短剪藏）
│   ├── articles/              # 网页长文/博客
│   └── assets/                # 图片附件
└── wiki/                      # AI 生成并维护的知识库
    ├── concepts/              # 概念页面（一个概念一个文件）
    ├── papers/                # 论文讲解页面（一篇论文一个文件）
    ├── connections/           # 跨概念连接（idea 产生的地方）
    ├── questions/             # 开放研究问题（未来方向的种子）
    └── syntheses/             # 综合论述
```

# 核心目录与权限边界 (Immutability & Architecture)

你必须严格遵守以下文件操作权限，这是不可逾越的底线：

- `raw/` (不可变层 - Immutable)：
  - 这里存放用户的原始素材。**绝对禁止修改文件内容**——它是事实的唯一真相来源。
  - **唯一例外**：摄入完成后，允许将文件从 `raw/research/` 移动到 `raw/` 下的分类子目录（papers/book/courses/clips/articles/assets）以完成归档。移动不改变文件内容，不算"修改"。
- `wiki/` (编译输出层 - You Own This)：
  - 这是你的专属工作区。你需要在此处创建、更新、提炼知识并解决矛盾。

## Wiki 核心文件契约 (The Wiki Schema)

当你在 `wiki/` 中工作时（尤其是执行写入操作后），必须维护以下基石：

1. **`index.md` (总目录)**：
   每次向 wiki 新增知识页后，必须同步更新此文件，将本次新增或修改的页面按分类加入目录，每一条都在所属类别的小节的顶部。
   格式要求： `[[页面名称]] — 一句话描述`。
    范例：
    ```markdown
    # Wiki Index

    ## Papers
    - [[CVPR2020-DConv-Net]] — 该论文解决什么问题、一句话结论。

    ## Concepts
    - [[母页名称]] — 该概念族的定义与边界（只列母页，子页缩进其下）。

    ## Connections
    - [[连接-主题]] — 两个概念之间尚未被记录的关系。

    ## Questions
    - [[q-rate-reduction-as-energy]] — 该开放问题的现状与切入路径。

    ## Syntheses
    - [[synthesis-slug]] — 该页面回答的复杂问题。
    ```
2. **`log.md` (操作日志)**：
   只能追加写入（Append-only）。每次操作后在文件顶部追加记录：`## [YYYY-MM-DD] <动作> | <操作简述>`。
   操作类型： ingest, query, lint
   范例：
   ```markdown
   ## [2026-04-11] ingest | 引入 DSH 技能体系核心概念
   - **变更**: 新增 [[DSH技能体系]], [[摘要-dsh-skills-docs]]; 更新 [[index.md]]
   - **冲突**: 无 (或: 冲突 [[RAG架构]], 已标注)

   ## [2026-04-11] query | 解析 Karpathy LLM-Wiki 理念
   - **输出**: 已保存至 [[分析-karpathy-wiki-philosophy]]

   ## [2026-04-11] lint | 周度健康检查
   - **结果**: 修复 2 处死链，发现 1 个孤儿页面 [[UnlinkedPage]]
   ```
3. **内容分类**：
   `wiki/` 下分五类，**一页只属于一类**；分类由「页面回答什么」决定，不由来源决定——同一篇论文可能同时产出 `paper` / `concept` / `connection` 三类页面，各写各的目录，再用 `[[双链]]` 互相连接。

   | 目录 | `type` | `index.md` 段 | 收录内容 | 结构要求 |
   |---|---|---|---|---|
   | `wiki/papers/` | `paper` | `## Papers` | **论文讲解页面**：一篇论文一个文件——讲清核心贡献、方法拆解、实验与结论、局限 | 走 ingest 论文模板（`### 0. 全局视图` + 模块化方法，每个公式配「符号表 + 人话」）；由 `check_paper_template.py` 校验 |
   | `wiki/concepts/` | `concept` | `## Concepts` | 一个概念一页：定义、数学形式、与上下游概念的关系 | 母页/子页分层写法见「概念分层」；index 只列母页 |
   | `wiki/connections/` | `connection` | `## Connections` | **relates-to**：两个（或多个）概念之间尚未被记录的连接、类比、张力 | 命名 `连接-主题.md`；判据是能说清"连接的性质"；不是 is-a / part-of 的关系一律放这里 |
   | `wiki/questions/` | `question` | `## Questions` | 开放研究问题：现状、为何未解、可能的切入路径 | 命名 `q-简短描述.md`；`updated` / `sources` / `## 关联连接` 三件套缺一不可 |
   | `wiki/syntheses/` | `synthesis` | `## Syntheses` | 综合论述：回答一个跨多页的复杂问题 | 命名 `synthesis-简短描述.md`；通常由 `query` 技能产出 |

   - **五段固定**：`index.md` 的分类段就是上表这五段（lint 检查 1 按此解析），**不要新增 `Sources` / `Entities` 之类段落**；新页面插到所属段的**顶部**。
   - **`type` 必须与所在目录一致**（含 `synthesis`，见下「页面格式」）；把新页面注册进 `index.md` 是收尾动作，不做就等于没收尾。
   - **wiki/ 之外的目录都不是知识页**，不写 frontmatter、不进 `index.md`：
     - `我的研究/` —— **用户自己的**研究内容（方案、调研、改进意见、spec/tasks）；AI 不主动改写，只在被要求时协助；它同时是合法的 `[[双链]]` 目标；
     - `周报/` —— 领域速报，按 `周报/<域>/<域>速报-<年>-W<周>.md` 组织，非 raw 层、可改可删可重排；
     - `raw/` —— 不可变原始层（见上文权限边界），只读、只归档。
4. **强制双向链接**：
   每一个 wiki 页面必须包含 `## 关联连接` 区域，使用 Obsidian 双链 `[[页面名称]]` 链接到其他相关概念。绝不能产生孤岛页面。
5. **矛盾处理原则**：
   如果新摄入的知识与旧知识冲突，不要静默覆盖。在页面中新建 `## 知识冲突` 区块，将两种说法都保留并做对比。
6. **风格说明**：
	- 面向具有扎实数学/计算机背景的读者
	- 详细真实、有事实依据，不要降格简化
	- 使用正确的数学符号与公式；存疑时，保留数学公式本身，而非仅保留文字描述
	- 明确标记来源之间的真实矛盾，而非粉饰抹平
	- 中英文混用没问题 — 用对概念最清晰的表达方式

## 约定规范

### 页面格式

所有 wiki 页面使用 YAML frontmatter：

```yaml
---
title: "页面标题"
type: concept | paper | connection | question | synthesis
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: ["raw/filename.md"]
questions: [1, 3]  # 该页面关联的核心问题编号
tags: [domain/llm, task/reasoning, method/transformer]
---
```

### Tag 规范（受控词表）

**唯一权威来源 = `.dsh/tag-vocab.json`**（词条数据；查当前词条用 `python .dsh/scripts/tag_vocab.py --list`）。
[`TAGS.md`](TAGS.md) 是**规则文档**——只写规范、**不列词条**（同样由脚本生成，请勿手改）。

- **两级嵌套 + 7 个分面**：主题 tag 一律写作 `分面/叶节点`。分面只有七个——
  `domain`（领域与平台）、`task`（任务）、`modality`（模态）、`method`（方法/机制）、
  `challenge`（问题/障碍）、`data`（数据集/基准/仿真）、`meta`（综述/路线图/实验分析）。
  分面的中文释义与"判断问题"写在 `.dsh/tag-vocab.json` 的 `facets` 里，可自定义。
- **角色 tag 是唯一例外**：`母概念` / `子概念` 不带前缀，且**必须是 `tags` 的第一项**——
  `gen_canvas.py` 与 lint 检查 7 依赖其字面值与位置，不得改名、不得加前缀。
- **封闭词表**：只允许 `.dsh/tag-vocab.json` 的 `canonical` 里登记过的词条，**禁止临场造词**
  （查当前词条：`python .dsh/scripts/tag_vocab.py --list`）。未登记 tag 会被
  `tag_audit.py` 判为违规并给出非 0 退出码 —— **冷启动阶段除外**，见下面的例外条款。
  注意：**出厂时词表是空的**，只有七个分面，没有任何具体词条。
- **数量**：每页主题 tag 1–8 个（推荐 3–5）；分面软上限
  domain 2 / task 4 / modality 4 / method 6 / challenge 4 / data 2 / meta 2。
- **一个 tag 只表达一个维度**：`image-classification` 应拆成 `modality/image` + `task/classification`，
  `cross-modal-fusion` 应拆成 `modality/multimodal` + `method/feature-fusion`，**不得新造复合词**。
- **tag 不承载 `type` / 年份 / 期刊名 / 数据集专名 / 模型专名**：这些已由 frontmatter
  字段或正文承载；数据集专名统一 `data/dataset`，模型专名统一 `method/foundation-model`。
- **写法与顺序**：一律单行内联 `tags: [a, b, c]`（禁用 YAML 块序列）；
  顺序 = 角色 tag → 分面顺序（domain → task → modality → method → challenge → data → meta）→ 面内字母序。
- **新增 tag 的门槛**：该词须在 **≥3 个页面**上有实际检索价值，且能回答"它属于哪个分面"
  （答不出分面 = 它不该是 tag，写进正文即可）。否则合并到最接近的现有词条。
- **⚡ 冷启动例外（首次摄入必读）**：`canonical` 为空、或对应分面为空时，**取消 ≥3 页门槛**
  ——第一轮摄入不可能已经攒够 3 个页面，直接取词即可，只要说得清它属于哪个分面。
  但**纪律不放松**：必须在**同一次 ingest 的收尾**把这些词登记进 `canonical`
  （`叶节点: 中文释义`）与 `map`（来源词），让 `tag_audit.py` 的退出码回到 0。
  是「先立规矩再用」，不是「先用乱再补票」。某个分面一旦有条目，该分面即恢复常规门槛。
- **改动流程**（缺一不可）：
  1. 在 `.dsh/tag-vocab.json` 的 `canonical` 加 `叶节点: 中文释义`，在 `map` 登记来源词
     （一条来源可映射到多个规范 tag，用于合并近义词、单复数、大小写差异）；
  2. `python .dsh/scripts/tag_vocab.py --check` —— 词表自洽；
  3. （仅当改了**分面或规则**）`python .dsh/scripts/tag_vocab.py --emit-doc` —— 重新生成 `TAGS.md`；
     单纯增删词条**不用**刷新它，因为 `TAGS.md` 只写规则、不列词条；
  4. `python .dsh/scripts/tag_apply.py`（预演）→ `--apply`（写盘，自动备份到 `.dsh/tmp/tags-backup-*.json`）；
  5. `python .dsh/scripts/tag_audit.py` —— 复核，退出码必须为 0。

  > 迁移映射 `map` 是**幂等**的：对已是规范 tag 的页面重复执行不会产生变化；
  > 若需重跑历史映射（例如修正了 `map`），先用 `tag_apply.py --rollback <备份>` 还原再 `--apply`。

### 链接

- 使用 Obsidian 维基链接：`[[概念名称]]`
- 每个概念页面应链接到相关的概念和论文
- 每篇论文页面应链接到它所贡献的概念
- Obsidian 中反向链接是隐式的；正向链接必须显式写出

### 命名规则

- 概念页面（concepts）：中文命名（如 `率降维.md`、`均衡传播.md`），简洁准确反映概念核心含义，专有名词/缩写可保留英文
- 论文讲解页面（papers）：`来源年份-简短标题.md`（如 `CVPR2020-DConv-Net.md`）
- 问题页面（questions）：`q-简短描述.md`（如 `q-rate-reduction-as-energy.md`）
- 连接页面（connections）：中文命名，格式为 `连接-主题.md`（如 `连接-频域滤波与交叉注意力.md`）
- 综合页面（syntheses）：`synthesis-简短描述.md`（如 `synthesis-扩散模型综述.md`；早期遗留页可能无前缀，新页面一律带前缀）

### 概念分层：母概念 / 子概念

概念页超过一定数量后扁平列表会失去可读性。本库用「**母页（MOC）+ 子页**」两级结构组织概念，并保证该结构在 **Obsidian 关系图谱中可见**。

**判定与粒度**
- 一个概念页统领 **≥3 个**概念页时可升级为**母页**；每族建议 5–12 个子页，母页导读 ≤15 行。
- 关系判据是 **is-a / part-of**（"X 是不是 Y 的一种？"）。答不出的关系属于 `connections/`（relates-to），不要写进层级。
- **允许一页多父**（DAG 而非树）；一页可同时是某族的母页与另一族的子页。

**写法（三处必须同时存在）**
1. frontmatter：母页 `tags` 首项加 `母概念`；子页首项加 `子概念`。
2. **母页正文**必须有 `## 子概念` 段，逐条 `- [[子页]] — 一句话`（可分组；**一条 bullet 只放一个子页**，便于脚本与图谱解析）；母页还应有 `## 这一族的地图`（≤15 行导读）。
3. **子页正文**在 frontmatter 之后必须有定位行：`> **母概念**：[[母页]]`（多父写作 `[[母页A]]、[[母页B]]`）。

> ⚠️ **层级链接必须写在正文里**：Obsidian 核心关系图谱的边**只来自正文的 `[[链接]]`**，frontmatter 中的纯文本字段不进图谱。母页的 `## 子概念` 段与子页的定位行不是装饰，它们就是图谱结构本身。

**索引与图谱查看**
- `index.md` 的 Concepts 段只列**母页**（带一句话描述），子页作为**缩进子条目**折叠其下；多父子页只在"主父"下出现一次。
- 图谱：Display 勾选 **Tags**；Groups 用 `tag:#母概念`（骨架）与 `tag:#子概念`（叶子）着色；Filters 用 `-path:wiki/papers -path:wiki/connections` 只看概念骨架。
- 分层一致性由 lint 技能的「检查 7」负责校验（tag ↔ 子概念段 ↔ 定位行三处互证、无环、无孤儿声明）。

### Obsidian 库根与文件引用

- **库根** = 含 `.obsidian/` 的那个目录，可能是工作区根，也可能是它的上级。`wiki_env.py` 会自动向上探测并算出「库根相对前缀」。
- **凡是写进 Obsidian 文件内的路径，必须是"库根相对路径"**（带前缀，如 `my-vault/wiki/concepts/示例概念.md`）。
  - 判断方法：`python .dsh/scripts/wiki_env.py --paths` 看 `vault_prefix` 一行。
  - wiki 正文里的 `[[双链]]` 不受影响（Obsidian 按文件名解析，与库根无关）；但 **`.canvas` 的路径解析依赖库根**——漏掉前缀会让画布显示"未找到引用的文件"。
- 生成脚本必须**自动探测库根**再计算前缀，禁止硬编码；写 JSON 时用 `ensure_ascii=False` 保持中文可读。

### Canvas 概念地图与同步（强制）

- 每个母页对应一张 `wiki/概念地图-<母页名>.canvas`，全库另有一张总图 `wiki/概念全景图.canvas`；两者一律由 **`.dsh/scripts/gen_canvas.py` 生成**，禁止手工编辑坐标或卡片。文件名前缀见 `.dsh/wiki.config.json` 的 `canvas` 段。
- **族结构发生变化时必须重新生成对应画布**（这是硬性收尾动作）。触发条件包括：新增/删除母页或子页；修改母页 `## 子概念` 段的分组或条目；修改子页文首的母概念定位行（多父关系变化）；母页改名。
- 命令：
  - `python .dsh/scripts/gen_canvas.py` —— 重新生成全部画布（总图 + 每个母页一张族图）
  - `python .dsh/scripts/gen_canvas.py --check` —— 只校验；**退出码非 0 表示有画布缺失或过期**
- 每张画布标题卡内写有 **结构指纹**（8 位十六进制，由母页名 + 子页集合 + 各子页父页列表算出）。lint 的「检查 8：Canvas 同步」用它比对当前 wiki 结构，指纹失配即报 STALE。
- 画布卡片一律使用 **`text` 节点 + `[[页面名]]`**（文本链接，点击可跳转）；**禁止使用 `file` 节点**——`file` 节点会把笔记正文嵌入画布渲染，卡片一多开销极大。

# 环境与依赖

- 绝大多数脚本**只用标准库**，用 harness 自带 Python 跑 `python .dsh/scripts/<name>.py` 即可。
- 只有 PDF 正文抽取（`extract_pdf.py`）需要 PyMuPDF，装在**项目内虚拟环境**里，**不要往系统 Python 装包**：

  ```bash
  python -m venv .dsh/venv
  # Windows:      .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
  # macOS/Linux:  .dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt
  ```

- 环境是否就绪，一条命令看清：

  ```bash
  python .dsh/scripts/selfcheck.py
  ```

- 中间产物一律写进 `.dsh/tmp/`（配置项 `dirs.tmp`）。**不要用 `/tmp/`**——在 Windows 上它解析到当前盘符根目录。

# Skills 调度指引

本项目配置了三个 Skills，封装了知识库的核心操作。当用户请求匹配以下场景时，**必须优先用 `skill` 工具加载对应 Skill**，而非手动逐步执行下方"操作流程"中描述的步骤。Skill 内部已包含完整的执行流程与模板，与 AGENTS.md 规范保持一致。

> ⚠️ **工具名与调用形式（易错点）**：当前宿主是 DSH，加载技能的工具叫 `skill`，**接收一个 `name` 参数，没有 `arguments` 参数**：
>
> ```
> skill({ name: "ingest" })
> ```
>
> 不要写成 `run_skill(...)`——该工具在当前宿主不存在。需要传达给 Skill 的指令（如"处理 raw/research/ 里所有文件"）由本轮的对话上下文承载，不通过参数传递。

## 可用 Skills 与触发条件

### ingest — 资料摄入

**调用**：`skill({ name: "ingest" })`

**触发条件**（满足任一即自动调用）：
- 用户输入 `/ingest` 或 `/ingest <文件路径>`
- 用户说"摄入"、"导入"、"收入"、"把这篇加入知识库"、"处理 raw/research/ 里的文件"
- 用户提供新资料并表达将其纳入知识库的意图

### query — 知识库检索

**调用**：`skill({ name: "query" })`

**触发条件**（满足任一即自动调用）：
- 用户输入 `/query <问题>`
- 用户询问"wiki 里有没有关于 X 的内容"、"帮我查一下 Y"、"我的笔记里关于 Z 是怎么说的"
- 用户的问题明显需要从知识库中检索答案，而非纯通用知识问题

**无需调用的例外**：纯通用知识问题（如"今天星期几"、"Python 怎么读取文件"、"太阳系有几颗行星"），直接回答即可，不必走 Skill 流水线。

### lint — 知识库健康检查

**调用**：`skill({ name: "lint" })`

**触发条件**（满足任一即自动调用）：
- 用户输入 `/lint`
- 用户说"检查知识库"、"跑一下 lint"、"wiki 健康状况怎么样"、"帮我检查一下 wiki"

## 调度优先级（冲突时）

当用户的请求同时匹配多个 Skill 时，按以下规则判断：

| 用户意图 | 优先 Skill | 判断依据 |
|---|---|---|
| 提供新文件/资料，要求处理 | `ingest` | 关键词：摄入、导入、加入知识库、处理 raw/ |
| 提出需要从 wiki 查找答案的问题 | `query` | 关键词：查一下、有没有、怎么说、wiki 里 |
| 要求检查 wiki 本身的状态 | `lint` | 关键词：检查、健康、lint、scan |

若用户在一次请求中表达了多个意图（如"把这篇论文摄入，然后帮我查一下相关概念"），按顺序依次调用对应 Skill。

## 何时不调用 Skills

以下情况直接处理，**不要**调用 Skills：
- 读取、编辑 AGENTS.md 或 Skill 文件本身
- 简单的文件浏览（如"看看 wiki/index.md 写了什么"）
- 关于项目目录结构或配置的通用问题
- 用户明确要求"不要用 skill，手动做"

# 工具链速查

| 命令 | 作用 | 退出码 |
|---|---|---|
| `python .dsh/scripts/wiki_env.py --paths` | 自省：工作区根、库根前缀、所有目录 | 0 |
| `python .dsh/scripts/setup_wiki.py` | 初始化/补齐目录骨架（幂等） | 非 0 = 有步骤失败 |
| `python .dsh/scripts/selfcheck.py` | 环境、依赖、骨架体检 | 非 0 = 必需项失败 |
| `python .dsh/scripts/tag_vocab.py --check` | 词表自洽性 | 非 0 = 词表有错 |
| `python .dsh/scripts/tag_vocab.py --list` | 列出当前词表全部词条（按分面分组） | 0 |
| `python .dsh/scripts/tag_vocab.py --emit-doc` | 重新生成 `TAGS.md` 规则文档（改规则时才需要） | 0 |
| `python .dsh/scripts/tag_audit.py` | 全库 tag 审计 | 非 0 = 有未登记 tag |
| `python .dsh/scripts/tag_apply.py [--apply]` | 按 `map` 迁移历史 tag | 0 |
| `python .dsh/scripts/gen_canvas.py [--check]` | 生成/校验概念地图画布 | `--check` 非 0 = 过期或缺失 |
| `python .dsh/scripts/check_paper_template.py` | 论文页模板合规校验 | 非 0 = 有不合规页 |
| `python .dsh/scripts/extract_pdf.py` | PDF 正文抽取（需 PyMuPDF） | 非 0 = 失败 |
| `python .dsh/scripts/fetch_source.py` | arXiv/DOI → LaTeX 公式真值（仅标准库） | 非 0 = 失败 |
| `python .dsh/scripts/crop_equations.py` | 按 bbox 裁剪公式小图（需 Pillow） | 非 0 = 失败 |
