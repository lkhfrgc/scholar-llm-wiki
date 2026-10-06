# ScholarWiki Kit 用户手册

> 面向使用者，不是面向开发者。从「这东西到底是干什么的」讲到「出问题怎么修」。
> 想了解内部实现请看 [`ARCHITECTURE.md`](ARCHITECTURE.md)，想改配置请看 [`CUSTOMIZE.md`](CUSTOMIZE.md)。

---

## 目录

- [0. 三分钟看懂它是什么](#0-三分钟看懂它是什么)
- [1. 它帮你解决的三个真实问题](#1-它帮你解决的三个真实问题)
- [2. 运行环境](#2-运行环境)
- [3. 安装](#3-安装)
- [4. 五分钟跑通第一遍](#4-五分钟跑通第一遍)
- [5. 日常使用：三个技能](#5-日常使用三个技能)
- [6. 目录说明书](#6-目录说明书)
- [7. 页面长什么样](#7-页面长什么样)
- [8. Tag 系统（通俗版）](#8-tag-系统通俗版)
- [9. 概念分层与概念地图](#9-概念分层与概念地图)
- [10. 配置速查](#10-配置速查)
- [11. 命令行速查](#11-命令行速查)
- [12. 常见问题 FAQ](#12-常见问题-faq)
- [13. 出问题了怎么排查](#13-出问题了怎么排查)
- [14. 术语表](#14-术语表)
- [15. 进阶用法](#15-进阶用法)

---

## 0. 三分钟看懂它是什么

### 一句话

**你负责投料，AI 负责编译，Obsidian 负责呈现。**

**它面向的是科研与文献整理**——论文、书籍、课件、网页长文、文献综述。
不是通用笔记应用：这里没有待办、日记、看板、周计划。它是**文献进、知识出**的编译器，
下面[第 1 章](#1-它帮你解决的三个真实问题)的三个场景就是它被设计出来要解决的问题。
（场景与功能的逐条对应见 [README 的「它面向什么」一节](../README.md#它面向什么科研与文献整理)。）

### 这套方法从哪来

前面这句话不是本工具原创的。**基础方法论来自 Andrej Karpathy 的
[`llm-wiki.md`](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**——
一份刻意写得抽象的 "idea file"，讲的是同一件事：

> 不要每次提问都从原始文档里重新检索（那是 RAG 的做法，知识不会积累）。
> 让 LLM **增量地建立并维护一个持久的 wiki**：新资料进来就读懂、提炼、
> 整合进已有页面，更新交叉引用，标出新旧说法矛盾的地方。
> **wiki 是一个会复利增长的产物**，不是每次重新推导的临时答案。

他还给了一个很好记的比喻：**「Obsidian 是 IDE，LLM 是程序员，wiki 是代码库。」**

原文档里的三层架构（不可变的原始素材 / LLM 拥有的 wiki / 给 LLM 的 schema）
和三个操作（Ingest / Query / Lint），在本工具包里分别落成了 `raw/`、`wiki/`、
`AGENTS.md` 和同名的三个技能。完整的对应关系与「本仓库额外加了什么」见
[README 的「方法论出处」一节](../README.md#方法论出处)。

### 一个比喻

普通笔记软件里，你是**唯一**的作者兼编辑：写、分类、加链接、整理目录，全靠你自己。
坚持三个月的人不多，因为它反人性——人擅长产生想法，不擅长维护结构。

这个工具把角色拆开了：

| 角色 | 谁来做 | 做什么 |
|---|---|---|
| 投料工 | **你** | 把论文 PDF、网页剪藏、课程笔记丢进一个文件夹 |
| 编译者 | **AI（DSH）** | 读懂内容，按固定规范写成结构化页面，自动加双链、打标签、更新目录 |
| 呈现层 | **Obsidian** | 把 `[[双链]]` 变成关系图谱，把概念族变成可视化的概念地图 |
| 质检员 | **AI + 脚本** | 定期巡检：死链、孤岛页面、没登记的标签、过期的分类 |

你唯一需要养成的习惯是：**看到有用的东西，丢进 `raw/research/`，然后说一句 `/ingest`。**

### 为什么不能随便让 AI 写笔记

如果你直接对 AI 说「帮我整理这篇论文」，你会得到一篇不错的总结——但它是一次性的。
每次整理的结果长得都不一样，链接名不一致，标签随机，目录没人维护。三个月后你得到
三十篇互不相干的文档，而不是一个知识库。

这个工具做的事，本质上是**给 AI 立规矩**：

- 页面必须分五类，每类的结构固定（论文页必须讲清公式里每个符号是什么）；
- 每个页面必须有「关联连接」区，不许产生孤岛；
- 标签必须从一张封闭词表里挑，不许自己造词；
- 每次写完必须更新总目录和日志，必须归档源文件，结构变了必须重画概念地图。

规矩写在 `AGENTS.md` 里，AI 每次干活前都会读。**这就是「知识库」和「一堆 AI 生成的文档」的区别。**

---

## 1. 它帮你解决的三个真实问题

**场景 A：你攒了 30 篇论文 PDF，一篇都没读透。**
把 PDF 全丢进 `raw/research/`，说 `/ingest`。AI 会一篇篇处理：抽取正文和公式、
写成带「符号表 + 人话解读」的论文讲解页、把里面出现的关键概念单独建页、
找出概念之间的联系、最后把 PDF 归档到 `raw/papers/`。你回来时，
`wiki/` 里已经有了一套互相链接的页面，`index.md` 是总目录。

**场景 B：你记得「好像在哪篇里看过这个技巧」，但想不起是哪篇。**
问 `/query 那个用频域方法做跨模态对齐的思路是什么`。AI 会**先读你的知识库**再回答，
每个结论后面挂 `[[双链]]` 指向来源页面。它被明令禁止凭记忆回答——
「你的库里没有」也是一个合法答案。

**场景 C：三个月后，知识库开始长歪。**
页面改名了但链接没改，新页面忘了登记进目录，标签越打越随意。说 `/lint`，
它会跑九项检查，给你一份红/黄/蓝三色的体检报告，告诉你哪里坏了、怎么修。

---

## 2. 运行环境

**最佳体验 = Obsidian + DSH（DeepSeek Harness）。** 详细对照表见 [README 的运行环境一节](../README.md#运行环境装之前先看这一段)，这里只讲结论：

| 组件 | 作用 | 缺了会怎样 |
|---|---|---|
| **DSH** | 技能宿主：把 `/ingest`、`/query`、`/lint` 变成真的能触发的工作流，并自动加载 `AGENTS.md` | 脚本照常能跑，但三个技能不会自动触发，你得手动指挥每一步 |
| **Obsidian** | 渲染 `[[双链]]`、关系图谱、`.canvas` 概念地图、tag 面板 | 文件仍是标准 Markdown，但知识网络的「网」看不见了 |
| **Python ≥ 3.9** | 跑 13 个脚本 | 脚本不可用，只剩规范文本 |

**可选（只服务 PDF 公式提取）**：PyMuPDF、Pillow、DSH 的 LibreOffice Kit。
没有它们也能摄入 PDF，只是公式核对会退化成整页看图。

> 💡 **为什么强调 DSH + Obsidian 的组合**：这套工具的价值有一半在「自动化的工作流」，
> 另一半在「看得见的知识网络」。单用 DSH，你得到一堆结构良好的文件；
> 单用 Obsidian，你得到一个人工维护的空壳。两者合起来才是完整体验。

---

## 3. 安装

### 最快的方式

复制 [README 里的「一句话安装」提示词](../README.md#-一句话安装)发给你的 DSH，它会自己克隆、
复制、初始化、自检，然后把体检报告贴给你。

### 手工安装

```bash
git clone https://github.com/YOUR-NAME/scholar-wiki-kit /tmp/scholar-wiki-kit
cd /path/to/your-vault

# 只复制这三样
cp -r /tmp/scholar-wiki-kit/.dsh /tmp/scholar-wiki-kit/templates .
cp /tmp/scholar-wiki-kit/AGENTS.md .

python .dsh/scripts/setup_wiki.py     # 建目录骨架、生成 index/log/TAGS/初始画布
python .dsh/scripts/selfcheck.py      # 体检
```

`setup_wiki.py` 是**幂等**的：反复跑只会补缺失项，已有的内容一律不动。

### 装完立即验证

```bash
python .dsh/scripts/wiki_env.py --paths     # 路径解析对不对
python .dsh/scripts/selfcheck.py            # 必需项必须全 ✓（退出码 0）
python .dsh/scripts/tag_vocab.py --check    # 词表自洽（退出码 0）
python .dsh/scripts/gen_canvas.py --check   # 画布状态（退出码 0）
```

四个都是退出码 0，说明装好了。

### 在 Obsidian 里打开

如果你的知识库还不是 Obsidian 库（没有 `.obsidian/` 目录）：

1. Obsidian → 「打开文件夹作为库」→ 选中你的知识库根目录；
2. 建议开两个设置：**设置 → 文件与链接 → 使用 Wiki 链接**（本工具全程用 `[[双链]]`）；
3. 打开 `index.md` 当入口，把它固定在标签页。

### 卸载

删掉 `.dsh/`、`AGENTS.md`、`templates/`、`TAGS.md` 即可。
`wiki/`、`raw/`、`index.md`、`log.md` 都是你自己的内容，与本工具无关。

---

## 4. 五分钟跑通第一遍

第一次别拿重要资料试，找一篇公开论文或者一篇你随手存的博客文章就行。

**第 1 步 · 投料**

把文件复制到 `raw/research/`：

```
raw/research/Attention-Is-All-You-Need.pdf
```

**第 2 步 · 让 AI 摄入**

在 DSH 里说：

```
/ingest
```

（或者用自然语言：「把 raw/research 里的资料摄入知识库」。）

**第 3 步 · 回答它的确认**

它会先列出收件箱里的文件让你确认，比如：

> 收件箱里有 1 个文件：
> - `raw/research/Attention-Is-All-You-Need.pdf`
> 确认开始处理吗？

你说「开始」即可。之后你会看到它依次做完这些事：

1. 读 PDF —— 先试从 arXiv/DOI 拿 LaTeX 公式真值，再抽正文；
2. 写论文讲解页 `wiki/papers/NeurIPS2017-Attention-Is-All-You-Need.md`；
3. 建概念页，比如 `wiki/concepts/自注意力.md`、`wiki/concepts/位置编码.md`；
4. 如果发现两个已有概念之间有关系，建 `wiki/connections/连接-xxx.md`；
5. 给每个页面挑 tag；
6. 更新 `index.md`（总目录）和 `log.md`（操作日志）；
7. 把 PDF 从 `raw/research/` **移动**到 `raw/papers/`（只移动，不改内容）；
8. 重生成概念地图画布。

**第 4 步 · 验收**

到 Obsidian 里看：

- `index.md` 的 `## Papers` 段有没有新条目；
- `wiki/papers/` 里有没有那个文件，开头有没有 `## 我的批注`、`## 方法`、`### 0. 全局视图`；
- `wiki/concepts/` 里有没有新概念页，每个页面末尾有没有 `## 关联连接`；
- `log.md` 最上面有没有一条 `## [日期] ingest | ...`；
- `raw/research/` 是不是空了，`raw/papers/` 里有没有那个 PDF。

**第 5 步 · 提问**

```
/query 为什么注意力机制要除以根号 d_k
```

答案应该引用 `[[...]]` 指向你刚生成的页面，末尾还有「参考页面」列表。

跑通这一遍，你就掌握了这个工具 90% 的用法。

---

## 5. 日常使用：三个技能

### 5.1 `/ingest` —— 摄入资料

**什么时候用**：任何「我该把这份资料收进知识库」的时刻。

**怎么触发**（任一即可）：

- 输入 `/ingest` —— 扫描整个收件箱；
- 输入 `/ingest raw/research/某篇.pdf` —— 只处理指定的文件；
- 说人话：「摄入」「导入」「收入」「把这篇加入知识库」「处理 raw/research 里的文件」。

**支持什么格式**：

| 格式 | 处理方式 |
|---|---|
| `.md` | 完整读取 |
| `.pdf` | 三步走：① 从 arXiv/DOI 取 LaTeX 公式真值 → ② 抽正文并定位公式位置 → ③ 需要时只渲染公式区域看图核对（**不会**整页渲染，整页又慢又费钱） |
| 扫描版 PDF | 没有文本层，直接走第 ③ 步渲染读图 |
| 其它 | 完整读取；实在读不动就只记录文件名、页数等元信息 |

**它做完会向你汇报**：新增了哪些页面、更新了哪些页面、有没有冲突、画布是否重新生成。

**你需要在什么时候介入**：

- **开头确认**：`/ingest` 会先列清单让你确认；
- **发现知识冲突时**：如果新资料和已有页面说法矛盾，它会**停下来**，把两种说法都摆给你看，
  让你选：A) 并存标注（推荐，学术争议用这个）B) 新覆盖旧 C) 保留旧说 D) 跳过这个概念。
  它不会静默覆盖，这是硬规矩。

**两条铁律**：

- `raw/` 下的文件**内容绝对不许改**，唯一允许的操作是「摄入完成后移动到分类目录」；
- 新增/更新页面后必须更新 `index.md` 和 `log.md`，不做就等于没做完。

---

### 5.2 `/query` —— 提问

**什么时候用**：任何「我的库里有相关内容吗」的问题。

**怎么触发**：

- `/query <问题>`；
- 「wiki 里有没有关于 X 的内容」「帮我查一下 Y」「关于 Z 我的笔记里是怎么说的」。

**它怎么保证不瞎编**（这是它最重要的设计）：

1. **先读 `index.md`** 定位相关页面，再深读 2–5 个页面；
2. 综合答案，每个结论后面挂 `[[双链]]` 指向来源；
3. 末尾给「参考页面」列表；
4. **禁止凭模型记忆回答**——如果库里确实没有，它会明说「本地知识库中未找到相关内容」，
   然后才（在你认可的前提下）给通用知识回答，且这种情况下**不写日志**。

**如果你问的是纯常识问题**（今天星期几、Python 怎么读文件），它会直接回答，不走检索流程。

**新洞见会自动提议保存**：如果这次回答综合了两个以上页面、或者发现了一个新的概念连接、
或者识别出一个值得追踪的开放问题，它会问你：

> 这次回答综合了 [[A]] 和 [[B]] 的内容，形成了一个新的综合分析。是否需要我保存到对应目录？

你说「要」，它才会写成 `wiki/syntheses/`、`wiki/connections/` 或 `wiki/questions/` 页面。
**它不会未经同意往你的库里写东西。**

**矛盾它会明说**：如果两个页面对同一件事说法不同，它会在回答里指出矛盾，引用双方来源，
并提醒你去检查相关页面的 `## 知识冲突` 区块。

---

### 5.3 `/lint` —— 全库体检

**什么时候用**：每周一次，或者感觉知识库「有点乱」的时候。

**怎么触发**：`/lint`、`/scan`、「检查知识库」「跑一下 lint」「wiki 健康状况怎么样」。

**九项检查（人话版）**：

| # | 检查 | 它在找什么 |
|---|---|---|
| 1 | 索引一致性 | `index.md` 里登记了但文件不存在（幽灵条目）；文件存在但没登记（未注册页面）；frontmatter 字段缺失；`type` 与所在目录不匹配；页面缺 `## 关联连接` |
| 2 | 死链与孤儿页 | 链接指向不存在的页面；没有任何页面引用它的「孤岛页」 |
| 3 | 缺失概念 | 正文里频繁讨论、却没有独立页面的概念 |
| 4 | 过时论断 | 半年没更新、且引用的资料都很旧的页面 |
| 5 | 问题覆盖 | 每个核心研究问题被多少页面标注，哪些是空白 |
| 6 | 空白领域 | 综合上面的结论，给出「下一步该补什么」的建议 |
| 7 | 分层一致性 | 母页/子页的声明在三处（tag、正文、索引）对不对得上，有没有环 |
| 8 | Canvas 同步 | 概念地图和当前结构是否一致（用结构指纹比对） |
| 9 | Tag 合规 | 有没有页面用了词表外的标签 |

**报告怎么读**：

- ❌ **红灯**：必须处理。死链、幽灵条目、真孤岛。
- ⚠️ **黄灯**：建议处理。缺必需小节、字段不全、命名不一致。
- 🔵 **提示**：优化建议。建议新建的概念页、可能需要复核的旧页面。

**它默认只读**。报告给你之后会问「是否需要我执行自动修复」，
而且只允许修两类：更新 `index.md`、修明确是拼写错误的死链。
建新页面、判断论断是否过时、改页面内容——这些只报告，不动手。

**跑完你该做什么**：按红灯 → 黄灯 → 蓝灯的顺序处理。多数时候点个头让它修索引就行。

---

## 6. 目录说明书

```
你的知识库/
├── AGENTS.md          ← AI 的工作规范（别删，每次对话都会读）
├── TAGS.md            ← 标签词表（脚本生成，别手改）
├── index.md           ← 总目录（AI 维护，你可以看，但别跟它抢着改）
├── log.md             ← 操作日志（只追加，AI 维护）
├── .dsh/              ← 工具本体（配置 + 技能 + 脚本）
├── templates/         ← 骨架模板（安装时用，之后可删）
│
├── raw/               ← 【不可变层】你的原始素材，AI 只读不改
│   ├── research/      ←   ⭐ 收件箱：往里丢东西就对了
│   ├── papers/        ←   论文归档（摄入后自动移进来）
│   ├── book/          ←   书籍（注意是单数 book）
│   ├── courses/       ←   课件、课程笔记
│   ├── clips/         ←   网页短剪藏
│   ├── articles/      ←   网页长文、博客
│   └── assets/        ←   图片附件
│
├── wiki/              ← 【编译输出层】AI 的地盘
│   ├── papers/        ←   论文讲解页，一篇一个文件
│   ├── concepts/      ←   概念页，一个概念一个文件
│   ├── connections/   ←   跨概念连接（idea 产生的地方）
│   ├── questions/     ←   开放研究问题
│   ├── syntheses/     ←   综合论述
│   ├── 概念全景图.canvas        ← 全库概念地图（自动生成）
│   └── 概念地图-<母页名>.canvas  ← 单族地图（自动生成）
│
├── 我的研究/           ← 【你的地盘】方案、调研、改进意见；AI 不主动改
└── 周报/               ← 领域速报（可选功能，见配置的 domains）
```

**谁能改什么**：

| 位置 | 谁维护 | 你能做什么 |
|---|---|---|
| `raw/**` | **你** | 随便放、随便删、随便改名。**AI 不许改内容** |
| `wiki/**` | **AI** | 可以读、可以在 Obsidian 里加你自己的批注（每页都有 `## 我的批注` 留白）。**手改结构要谨慎**，改了要让 AI 知道 |
| `index.md` / `log.md` | **AI** | 看就行。要手工加条目也不是不行，但格式要对 |
| `我的研究/**` | **你** | AI 只在被要求时协助，并且它是合法的双链目标 |
| `.dsh/**` | 工具 | 配置文件随便改；脚本改坏了跑 `selfcheck.py` |

---

## 7. 页面长什么样

### 论文讲解页 `wiki/papers/`

文件名格式：`来源年份-简短标题.md`，比如 `NeurIPS2017-Attention-Is-All-You-Need.md`。

```markdown
---
title: "Attention Is All You Need"
type: paper
authors: [Vaswani, Shazeer, ...]
year: 2017
venue: NeurIPS
sources: ["raw/papers/attention.pdf"]
tags: [domain/llm, task/generation, method/transformer, method/attention]
---

## 我的批注
（留白，给你自己写）

## 核心贡献
（一段话：解决什么问题、核心主张是什么）

## 方法
### 0. 全局视图
一句话概括 + 数据流图 + 下标命名约定
### 1. 模块一：xxx（公式 1–3）
模块名称解释：…… 模块作用：……
#### 公式 (1)：……
$$ ... $$
| 符号 | 含义 | 形状 |
**人话**：……

## 关键结果
## 局限性与开放问题
### 问题与解答（Q1/Q2/Q3）
### 局限性分析
## 关联连接
## 原始来源
```

**为什么要这么啰嗦**：因为「读懂了」和「能讲出来」是两回事。要求每个公式配符号表和
「人话」解读，是为了三个月后的你能直接照着复习，不用重新推一遍。
这套结构由 `check_paper_template.py` 强制校验，AI 想偷懒会被脚本拦下。

### 概念页 `wiki/concepts/`

```markdown
---
title: "自注意力"
type: concept
created: 2026-10-06
updated: 2026-10-06
sources: ["raw/papers/attention.pdf"]
tags: [子概念, method/attention, method/transformer]
---

> **母概念**：[[注意力机制]]      ← 只有子页需要这一行

## 定义
## 核心思想（含核心公式）
## 关联连接        ← 必须有，否则算孤岛页
## 开放问题
```

### 连接页 `wiki/connections/连接-主题.md`

用来记录两个概念之间**尚未被记录的关系**。判据是「能说清这个连接的性质」——
是类比？依赖？对立？还是统一框架？说不清的就别建。

### 问题页 `wiki/questions/q-简短描述.md`

开放研究问题。三件套缺一不可：`updated` 字段、`sources` 字段、`## 关联连接` 段。

### 综合页 `wiki/syntheses/synthesis-简短描述.md`

回答一个跨多页的复杂问题。通常是 `/query` 之后你同意保存的产物。

### frontmatter 字段表

| 字段 | 含义 | 必填 |
|---|---|---|
| `title` | 页面标题 | ✅ |
| `type` | `paper` / `concept` / `connection` / `question` / `synthesis`，**必须与所在目录一致** | ✅ |
| `created` / `updated` | 创建 / 最后更新日期 | ✅ |
| `sources` | 来源文件路径列表，如 `["raw/papers/xxx.pdf"]` | ✅（纯综述页可省） |
| `tags` | 单行内联，如 `[子概念, method/attention]`。**禁用 YAML 块序列写法** | ✅ |
| `questions` | 关联的核心问题编号 | 可选 |
| `authors` / `year` / `venue` | 论文页专用 | 论文页 ✅ |

---

## 8. Tag 系统（通俗版）

### 为什么不能让 AI 自由打标签

不设限制的话，每整理一篇论文就会冒出几个新标签：`注意力`、`attention`、`Attention机制`、
`自注意力`、`self-attention`……半年后你有 600 个标签，每个只用过一次。
**标签就彻底失去检索价值了。**

所以本工具用**封闭词表**：AI 只能从 `TAGS.md` 里列出的词条中挑，挑不到就得先申请新增。

### 七个分面 = 七个问题

每个标签长这样：`分面/叶节点`，比如 `method/attention`。分面只有七个：

| 分面 | 回答的问题 | 例子 |
|---|---|---|
| `domain` | 这一页服务于哪个领域/平台？ | `domain/llm`、`domain/robotics` |
| `task` | 这一页的输出是什么？ | `task/detection`、`task/generation` |
| `modality` | 输入数据是什么形态？ | `modality/image`、`modality/text` |
| `method` | 用了什么架构或机制？ | `method/transformer`、`method/diffusion` |
| `challenge` | 是什么让任务变难？ | `challenge/efficiency`、`challenge/hallucination` |
| `data` | 涉及哪个数据集/基准？ | `data/dataset`、`data/benchmark` |
| `meta` | 这是综述、路线图还是实验分析？ | `meta/survey`、`meta/analysis` |

**给一个页面选标签，就是逐分面问自己七个问题**，答得上就挂，答不上就不挂。
每页 1–8 个，推荐 3–5 个。

### 三条容易踩的规矩

1. **一个 tag 只表达一个维度**。不要写 `image-classification`，
   要拆成 `modality/image` + `task/classification`。
2. **别用标签表达 type、年份、期刊名、数据集专名、模型专名**——这些有专门的字段。
   数据集专名统一用 `data/dataset`，模型专名统一用 `method/foundation-model`。
3. **角色标签必须放第一位**：`母概念` / `子概念` 不带前缀，且必须是 `tags` 的第一个。
   概念地图和分层检查都靠它认字面值。

### 想加一个新标签

门槛：**这个词得在 ≥3 个页面上有检索价值，而且你能说清它属于哪个分面**。
答不出分面，说明它不该是标签，写进正文就行。通过了就走这五步：

```bash
# 1. 在 .dsh/tag-vocab.json 里加词条：canonical 加「叶节点: 中文释义」，map 登记来源词
# 2. 校验词表自洽
python .dsh/scripts/tag_vocab.py --check

# 3. 刷新给人看的 TAGS.md
python .dsh/scripts/tag_vocab.py --emit-doc

# 4. 如果有页面用了旧写法，批量迁移（先预演，再写盘，会自动备份）
python .dsh/scripts/tag_apply.py
python .dsh/scripts/tag_apply.py --apply

# 5. 复核，退出码必须是 0
python .dsh/scripts/tag_audit.py
```

改错了可以回滚：

```bash
python .dsh/scripts/tag_apply.py --rollback .dsh/tmp/tags-backup-<时间戳>.json
```

### 页面用了词表外的标签怎么办

跑一下审计就知道：

```bash
python .dsh/scripts/tag_audit.py               # 完整报告
python .dsh/scripts/tag_audit.py --unregistered  # 只看未登记的
```

报出来的每个词，无非三种处理：**①** 它是已有词条的近义/大小写/单复数变体 → 登记进 `map`；
**②** 它确实有独立价值 → 按上面的流程加进 `canonical`；**③** 两个都不是 → 删掉它。
**不要直接手改页面的 tags 字段**，那样下次还会漂。

---

## 9. 概念分层与概念地图

### 母页 / 子页是什么

概念页多了以后，平铺一个列表看不过来。所以支持两级结构：

- **母页**：统领 ≥3 个概念页时，可以升级成「母页」（也就是 MOC，Map of Content）；
- **子页**：挂在母页下的概念页。一页可以同时是某族的母页、另一族的子页（允许多父）。

举例：`注意力机制` 是母页，`自注意力`、`交叉注意力` 是子页。

**判定标准是 is-a / part-of**：「X 是不是 Y 的一种？」答不上来的关系不属于分层，
应该建 `connections/` 页面（relates-to）。

### 三处必须同时写（缺一不可）

| 位置 | 写什么 |
|---|---|
| 母页 frontmatter | `tags` 第一项加 `母概念` |
| 母页正文 | 必须有 `## 子概念` 段，逐条 `- [[子页]] — 一句话` |
| 子页正文 | frontmatter 之后加定位行 `> **母概念**：[[母页]]` |

> ⚠️ **为什么不能只在 frontmatter 里写**：Obsidian 关系图谱的连线**只来自正文里的 `[[链接]]`**。
> frontmatter 里的文字不进图谱。所以母页的「子概念」段和子页的定位行不是装饰，
> **它们就是图谱的结构本身**。

### 概念地图（Canvas）怎么看

每个母页会自动生成一张 `wiki/概念地图-<母页名>.canvas`，全库另有一张总图
`wiki/概念全景图.canvas`。在 Obsidian 里双击打开，你会看到母页在中心、子页按分组排列的卡片图。

- 卡片都是**文本链接**，点一下能跳到对应笔记；
- 卡片**不会嵌入笔记正文**（否则卡片一多就卡）；
- 标题卡里有一串 8 位十六进制码，那是**结构指纹**——用来判断地图有没有过期。

### 什么时候要重新生成

只要族结构变了就必须重生成，否则地图会显示旧结构（错误分组、缺子页、指向已改名页面）：

- 新增/删除母页或子页；
- 改了母页 `## 子概念` 段的分组或条目；
- 改了子页文首的母概念定位行（多父关系变化）；
- 母页改名。

```bash
python .dsh/scripts/gen_canvas.py           # 重新生成
python .dsh/scripts/gen_canvas.py --check   # 校验；非 0 = 有缺失或过期
```

**你一般不用手动跑**——`/ingest` 的收尾步骤里就有这一步。手工改了 wiki 结构才需要自己跑。

---

## 10. 配置速查

**唯一配置源：`.dsh/wiki.config.json`**，改完保存即生效，没有第二步。

| 我想… | 改哪里 | 改完做什么 |
|---|---|---|
| 改知识库名字 | `wiki_name` | 重跑 `gen_canvas.py` 刷新画布标题 |
| 改界面语言 | `language` | 同步改 `AGENTS.md` 顶部的语言设定 |
| 改目录名（`wiki/` → `知识库/`） | `dirs.*` | 同步改 `wiki_types` 的键，再跑 `setup_wiki.py` |
| 改根目录文件名 | `files.*` | 跑 `setup_wiki.py` |
| 改五类页面的目录/type 对应 | `wiki_types` | 跑 `setup_wiki.py`，再跑 `check_paper_template.py` 验证 |
| 改概念地图文件名 | `canvas.*` | 重跑 `gen_canvas.py` |
| 开启领域速报 | `domains` 填领域列表 | 跑 `setup_wiki.py` 建子目录 |
| 换 venv 位置 | `python.*` | — |

**改完一定要跑一次**：

```bash
python .dsh/scripts/wiki_env.py --paths     # 看解析结果对不对
python .dsh/scripts/setup_wiki.py           # 补齐新目录
python .dsh/scripts/selfcheck.py            # 确认没坏
```

**库根前缀**：如果你的知识库嵌在一个更大的 Obsidian 库里（`我的库/知识库/`），
`vault_prefix` 保持 `"auto"` 就行，脚本会自动算出 `知识库/` 这个前缀。
写进 `.canvas` 的路径会自动带上它。改目录结构后如果画布显示「未找到引用的文件」，
八成就是这里的问题——手工跑一次 `wiki_env.py --paths` 看 `vault_prefix` 一行。

---

## 11. 命令行速查

```bash
# —— 环境与骨架 ——
python .dsh/scripts/wiki_env.py --paths        # 自省：工作区根 / 库根前缀 / 所有路径
python .dsh/scripts/setup_wiki.py              # 初始化/补齐骨架（幂等，绝不覆盖已有内容）
python .dsh/scripts/setup_wiki.py --venv        # 顺带建 venv 并装 PyMuPDF
python .dsh/scripts/selfcheck.py               # 体检：环境 / 依赖 / 骨架 / 子脚本

# —— Tag 词表 ——
python .dsh/scripts/tag_vocab.py --check       # 词表自洽
python .dsh/scripts/tag_vocab.py --emit-doc    # 刷新 TAGS.md
python .dsh/scripts/tag_audit.py               # 全库审计
python .dsh/scripts/tag_audit.py --unregistered # 只看未登记的
python .dsh/scripts/tag_apply.py [--apply]     # 批量迁移标签（预演 / 写盘）
python .dsh/scripts/tag_verify_migration.py    # 独立复核迁移结果

# —— 结构与画布 ——
python .dsh/scripts/gen_canvas.py [--check]    # 生成 / 校验概念地图
python .dsh/scripts/check_paper_template.py    # 论文页模板合规校验
python .dsh/scripts/check_paper_template.py --links  # 顺带查全库死链

# —— PDF 素材（可选依赖）——
python .dsh/scripts/fetch_source.py --arxiv 1706.03762v7   # arXiv/DOI → LaTeX 公式真值
python .dsh/scripts/extract_pdf.py paper.pdf --math -o out.txt
python .dsh/scripts/crop_equations.py --manifest m.json --equations e.json --out-dir crops/

# —— 提交前自查 ——
python .dsh/scripts/repo_lint.py               # 绝对路径 / 用户名 / 凭据 / BOM
```

**退出码是有意义的**：`0 = 通过，非 0 = 有问题`。可以直接接进 CI 或 git hook：

```bash
python .dsh/scripts/tag_audit.py && python .dsh/scripts/gen_canvas.py --check && \
python .dsh/scripts/check_paper_template.py --links && python .dsh/scripts/repo_lint.py
```

---

## 12. 常见问题 FAQ

**Q：我必须用 DSH 和 Obsidian 吗？**
A：脚本层不需要——13 个脚本是纯 Python，任何环境都能跑。但三个技能靠 DSH 触发、
双链和图谱靠 Obsidian 渲染。**强烈建议两者都用**，否则你只用到这个工具的一小半。
换 harness 是可行的，但要手工把技能搬到对应目录并替换工具名（见 README）。

**Q：我能把整个知识库放到 GitHub 上吗？**
A：可以，而且强烈推荐。`.dsh/tmp/`、`.dsh/venv/` 已被忽略。推之前跑一次
`repo_lint.py`，它会拦住本机路径、用户名、凭据和 BOM。注意 `raw/` 里可能有版权材料，
建议把 `raw/` 加进 `.gitignore`。

**Q：`raw/` 里的东西会被 AI 改吗？**
A：不会。这是硬规矩，写在 `AGENTS.md` 里。唯一允许的操作是摄入完成后**移动**文件
（从收件箱到分类目录），移动不改变内容。

**Q：AI 会不打招呼就往我库里写东西吗？**
A：`/ingest` 干的就是写库的事，但它开始前会列清单让你确认。
`/query` 只会**提议**保存新洞见，你同意才写。`/lint` 默认只读。

**Q：标签词表太大了/太小了，怎么办？**
A：随包的是一套通用种子词表（120 个词条）。换领域就按
[`CUSTOMIZE.md`](CUSTOMIZE.md) 的步骤改 `.dsh/tag-vocab.json` 的 `canonical` 和 `map`。
改完跑 `--check` 确认自洽。

**Q：我手改了 `wiki/` 里的页面，会破坏什么吗？**
A：不会破坏，但要记得：结构变了（加了母页/子页）要重跑 `gen_canvas.py`；
标签写了词表外的词，下次 `/lint` 会报出来。加你的**个人批注**是最安全的——
每页都有 `## 我的批注` 段落是专门留给你的。

**Q：为什么每个页面都必须有 `## 关联连接`？**
A：因为它是「不是孤岛」的唯一证明。没有它，页面在关系图谱里就是一个孤立点，
你永远想不起来去看它。`/lint` 会专门检查这一条。

**Q：摄入一篇论文要多久？**
A：取决于篇幅和是否需要渲染公式。纯文本的 arXiv 论文通常几分钟。
扫描版 PDF 会慢一些（要渲染读图）。你可以中途打断，已完成的页面不会丢。

**Q：我的知识库已经有几百个页面了，还能装吗？**
A：能。`setup_wiki.py` 只补缺失项，不动已有内容。但建议装完后跑一次 `/lint`
看看已有页面的 `tags` 和 `## 关联连接` 是否合规，AI 会给你一份清单。

**Q：`.canvas` 打开显示「未找到引用的文件」？**
A：库根前缀不对。跑 `python .dsh/scripts/wiki_env.py --paths` 看 `vault_prefix` 一行，
然后在 `.dsh/wiki.config.json` 里把它从 `"auto"` 改成显式值（比如 `"知识库"`，
空串表示工作区本身就是库根），再重跑 `gen_canvas.py`。

**Q：`/ingest` 说找不到 venv / 缺 PyMuPDF？**
A：只有 PDF 正文抽取需要它。按提示建 venv：

```bash
python -m venv .dsh/venv
# Windows:      .dsh\venv\Scripts\python.exe -m pip install -r .dsh/requirements.txt
# macOS/Linux:  .dsh/venv/bin/python       -m pip install -r .dsh/requirements.txt
```

或者 `python .dsh/scripts/setup_wiki.py --venv` 一步到位。**别装进系统 Python。**

**Q：DSH 里看不到 `/ingest` 这个技能？**
A：确认 `.dsh/skills/ingest/SKILL.md` 存在且文件开头有 `name` 和 `description` 的
frontmatter。装完之后**开一个新会话**，DSH 才会重新扫描技能目录。

**Q：技能会在我没说完话的时候就动手吗？**
A：`ingest` 和 `lint` 都会先确认。`query` 是只读+提议模式。你要更谨慎的话，
可以说「先别动，只告诉我你打算做什么」。

**Q：`log.md` 我能自己写吗？**
A：能，但格式要对。操作类型只允许 `ingest` / `query` / `lint` 三种，
新条目必须在**文件顶部**、独占一行、以空行结尾。`log.md` 是 append-only 的，
AI 不会覆盖或删除已有记录。

**Q：怎么备份？**
A：整个知识库就是一个文件夹 + 一堆纯文本。`git init` 然后定期 commit 是最省事的方案，
Obsidian 的 Git 插件可以自动做。也可以用任何同步网盘。

**Q：能同时维护多个知识库吗？**
A：可以。每个库都装一份 `.dsh/`，各自独立。脚本靠自身位置推断工作区，
互不干扰。也可以在别处装一份工具包，用 `WIKI_WORKSPACE` 环境变量指向目标库。

**Q：我能加第四个技能吗？**
A：能。在 `.dsh/skills/<名字>/SKILL.md` 写一份 Markdown，
frontmatter 里 `name` + `description`（description 决定它什么时候被自动选中），
然后在 `AGENTS.md` 的「Skills 调度指引」里登记一段。细节见
[`CUSTOMIZE.md`](CUSTOMIZE.md#5-加第四个技能)。

**Q：这东西会不会把我的心血锁死？**
A：不会。产出全是标准 Markdown + 标准 `.canvas`，没有一个字节是私有格式。
哪天不用了，删掉 `.dsh/` 和 `AGENTS.md` 就行，知识内容原样留着。

---

## 13. 出问题了怎么排查

**万能第一步**：

```bash
python .dsh/scripts/wiki_env.py --paths    # 路径对不对
python .dsh/scripts/selfcheck.py           # 环境有没有坏
```

### 分诊表

| 症状 | 最可能的原因 | 怎么办 |
|---|---|---|
| `python` 命令找不到 | Python 没装或不在 PATH | 装 Python ≥3.9；或让 DSH 用自带解释器 |
| 脚本报「工作区根不对」 | 脚本被挪了位置，或从别处调用 | 用 `WIKI_WORKSPACE` 环境变量显式指定 |
| `selfcheck` 一堆 ✗「骨架缺失」 | 还没初始化 | `python .dsh/scripts/setup_wiki.py` |
| `selfcheck` 报 `MISSING 概念全景图.canvas` | 画布没生成 | `python .dsh/scripts/setup_wiki.py`，或 `gen_canvas.py` |
| 技能不触发 | 技能文件缺失，或会话没刷新 | 检查 `.dsh/skills/*/SKILL.md`；开个新会话 |
| `/ingest` 说读不了 PDF | 缺 PyMuPDF | 建 venv 装依赖（见 FAQ） |
| 摄入后 `index.md` 没更新 | AI 漏了收尾动作 | 跑 `/lint`，检查 1 会报「未注册页面」 |
| `tag_audit` 报一堆未登记 | 页面用了词表外的词 | 见「[Tag 系统](#页面用了词表外的标签怎么办)」的处理流程 |
| `gen_canvas --check` 报 STALE | 族结构变了没重生成 | `python .dsh/scripts/gen_canvas.py` |
| `check_paper_template --links` 报死链 | 链接目标不存在或改了名 | 看报告里的 `来源 → 目标`，改用文件的实际名字 |
| Canvas 显示「未找到引用的文件」 | 库根前缀算错 | 见 FAQ 对应条目 |
| 中文在 Windows 控制台乱码 | 控制台编码 | 脚本内部已切 UTF-8；仍有问题就 `chcp 65001` |
| 整个知识库看起来乱了 | 正常的熵增 | `/lint`，按红→黄→蓝处理 |

### 硬核排障

如果脚本本身有问题（不是你的知识库的问题）：

```bash
python .dsh/scripts/selfcheck.py --json .dsh/tmp/report.json   # 机器可读报告
python .dsh/scripts/repo_lint.py                               # 脚本有没有被改坏
```

开 issue 时请附：`selfcheck.py` 输出、`wiki_env.py --json` 输出（**先自行抹掉绝对路径**）、
你的操作系统与 Python 版本。

---

## 14. 术语表

| 词 | 什么意思 |
|---|---|
| **工作区根** | 装了 `.dsh/` 的那个目录。所有路径都相对它计算 |
| **库根 / vault** | Obsidian 库的根目录，也就是有 `.obsidian/` 的那一层。可能是工作区根，也可能在它上面 |
| **库根前缀** | 从库根到工作区的相对路径，如 `知识库/`。写进 `.canvas` 的路径必须带它 |
| **收件箱** | `raw/research/`，你丢资料的地方，也是 ingest 的唯一入口 |
| **不可变层** | `raw/`。AI 只读、只归档，不改内容 |
| **编译输出层** | `wiki/`。AI 的工作区 |
| **收尾动作** | 更新 `index.md`、追加 `log.md`、重生成 Canvas。不做等于没做完 |
| **母页 / 子页** | 概念的两级结构（MOC / 叶子）。一页可多父 |
| **结构指纹** | 8 位十六进制码，由族结构算出，写在画布标题卡里，用来检测画布是否过期 |
| **受控词表** | 封闭的标签集合。AI 只能从里面挑，不能造 |
| **分面** | 标签的前缀，只有七个：domain / task / modality / method / challenge / data / meta |
| **角色标签** | `母概念` / `子概念`，不带前缀，必须放在 `tags` 第一位 |
| **死链** | 链接指向一个不存在的页面 |
| **孤岛页** | 没有任何页面引用它的页面（关系图谱里是孤立点） |
| **幂等** | 同一个命令跑多少次结果都一样。`setup_wiki.py` 就是幂等的 |
| **假死链** | 看起来是死链、其实不是：文档里的占位符、代码块里的示例、被注释掉的条目、历史日志里的旧引用 |

---

## 15. 进阶用法

### 15.1 用 git 管版本

```bash
cd 你的知识库
git init -b main
printf 'raw/\n.dsh/venv/\n.dsh/tmp/\n__pycache__/\n' >> .gitignore
git add -A && git commit -m "init: 知识库"
```

`raw/` 建议忽略（可能有版权材料和大文件）。想让 Obsidian 自动 commit，
装社区插件 **Obsidian Git** 即可。

推 GitHub 之前先跑 `python .dsh/scripts/repo_lint.py`——它会拦住本机路径、
用户名、邮箱和凭据。

### 15.2 接进 CI

本仓库自带 `.github/workflows/ci.yml`，逻辑可以直接抄到你的知识库仓库：

```yaml
- run: python .dsh/scripts/tag_audit.py
- run: python .dsh/scripts/gen_canvas.py --check
- run: python .dsh/scripts/check_paper_template.py --links
- run: python .dsh/scripts/repo_lint.py
```

四个都返回 0 才算过。这样「AI 忘了更新索引」这类问题会在 push 时被抓住。

### 15.3 同时维护多个知识库

每个库装一份 `.dsh/`，各自独立。如果不想重复安装，也可以在别处放一份工具包，
用环境变量指向目标库：

```bash
export WIKI_WORKSPACE=/path/to/vault-a     # Windows: $env:WIKI_WORKSPACE="..."
python /path/to/scholar-wiki-kit/.dsh/scripts/tag_audit.py
```

### 15.4 定制 PDF 流水线

`fetch_source.py` 能从 arXiv/DOI 直接拿 LaTeX 公式真值（免费、零损失）：

```bash
python .dsh/scripts/fetch_source.py --arxiv 2104.14294v2 -o .dsh/tmp/source.md
python .dsh/scripts/fetch_source.py --doi 10.1109/TGRS.2025.1234567 --filter all
```

`extract_pdf.py` 的几个有用选项：`--pages 1-5`（只抽前几页）、`--meta-only`（只看元信息）、
`--json`（结构化输出）。

### 15.5 换一个 harness

脚本层完全可移植（零绝对路径、跨平台）。要换宿主：

1. 把 `.dsh/skills/*/SKILL.md` 复制到目标 harness 的技能目录（如 Claude Code 是 `.claude/skills/`）；
2. 把 `AGENTS.md` 复制成它认识的指令文件（如 `CLAUDE.md`）；
3. 把技能正文里的 DSH 工具名换成目标的：`skill` → 对应机制、`grep`/`glob`/`read` → 目标的检索工具、
   `read_image` → 目标的读图工具、`office-docx` 那段 LibreOffice Kit 路径改成目标的取法。

第 3 步是机械劳动但必须做——不改的话技能会「找不到工具」，退化成凭记忆回答，
而那正是这套工具要避免的事。

---

## 一句话总结

**丢进 `raw/research/`，说 `/ingest`。想问就 `/query`。每周 `/lint` 一次。**
其余的，工具会替你把规矩守住。
