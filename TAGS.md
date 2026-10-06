# Tag 受控词表（Controlled Vocabulary）

> 本文件由 `.dsh/scripts/tag_vocab.py --emit-doc` 自动生成，**请勿手工编辑**。
> 新增/修改 tag 请改 `.dsh/tag-vocab.json` 的 `canonical` 与 `map`，再重新生成。

## 一、硬规则

1. **只允许本文件列出的 tag 出现在 `wiki/**/*.md` 的 frontmatter `tags:` 字段中。**
2. 角色 tag `母概念` / `子概念` **不带前缀，且必须是 `tags` 的第一项**——
   画布生成脚本与 lint 的分层检查依赖其字面值与位置。
3. 主题 tag 一律形如 `分面/叶节点`：分面只有 7 个，叶节点为小写 kebab-case 英文。
4. 每页主题 tag **1–8 个**（角色 tag 不计入），推荐 3–5 个；
   分面软上限 domain 2 / task 4 / modality 4 / method 6 / challenge 4 / data 2 / meta 2。
5. **禁止**用 tag 表达 `type`、年份、期刊名、论文缩写、数据集专名、模型专名——
   这些信息已由 frontmatter 字段或正文承载。数据集/模型专名统一归入
   `data/dataset` 与 `method/foundation-model`。
6. 排序：角色 tag → 分面顺序（domain → task → modality → method → challenge → data → meta）→ 面内字母序。
7. **tags 一律写成单行内联列表** `tags: [a, b, c]`，不用 YAML 块序列——
   统一写法才能被画布生成脚本与审计脚本无歧义解析。
8. **一个 tag 只表达一个维度**：`image-classification` 这类复合词必须拆成
   `modality/image` + `task/classification` 两个 tag，**不得新造复合词**。

## 一点五、工具链

| 命令 | 作用 | 退出码 |
|---|---|---|
| `python .dsh/scripts/tag_vocab.py --check` | 词表自洽性校验（映射指向的词条是否存在、有无死词条） | 非 0 = 失败 |
| `python .dsh/scripts/tag_audit.py` | 全库 tag 审计：未登记 tag、超限、频次分布 | 非 0 = 有未登记或硬违规 |
| `python .dsh/scripts/tag_audit.py --unregistered` | 只列出未登记的 tag | 同上 |
| `python .dsh/scripts/tag_apply.py` | 按 `map` 迁移历史 tag（**预演**，不写盘） | — |
| `python .dsh/scripts/tag_apply.py --apply` | 实际改写并生成备份到 `.dsh/tmp/tags-backup-*.json` | — |
| `python .dsh/scripts/tag_apply.py --rollback <备份>` | 从备份精确还原 tags | — |
| `python .dsh/scripts/tag_verify_migration.py` | 独立验证：备份 → 重新推导 → 与磁盘逐页比对 | 非 0 = 不一致 |
| `python .dsh/scripts/tag_vocab.py --emit-doc` | 用词表刷新本文件 | — |

## 二、分面总览

| 分面 | 词条数 | 收什么 | 判断问题 |
|---|---|---|---|
| `domain/` | 17 | 研究面向的应用场景、学科领域与数据来源平台 | 这一页服务于哪个应用/平台？ |
| `task/` | 24 | 这一页要解决/讨论的预测目标或输出形态 | 这一页的输出是什么？ |
| `modality/` | 12 | 输入数据、传感器或信号的形态 | 输入数据是什么形态/传感器？ |
| `method/` | 34 | 架构、机制、学习范式与求解手段 | 用了什么架构或机制？ |
| `challenge/` | 17 | 使任务变难的统计、物理或工程障碍 | 是什么让任务变难？ |
| `data/` | 8 | 数据集、基准、合成与仿真、数据治理 | 涉及哪个数据集/基准/仿真？ |
| `meta/` | 8 | 综述、路线图、实验分析与设计空间 | 这是综述、路线图还是实验分析？ |
| *角色* | 2 | 母页/子页层级标记 | 该页是否为某一族的母页或子页？ |

## 三、词表

### `domain/` — 研究面向的应用场景、学科领域与数据来源平台

| tag | 说明 |
|---|---|
| `domain/autonomous-driving` | 自动驾驶与地面移动平台 |
| `domain/cv` | 计算机视觉 |
| `domain/graph` | 图与网络数据研究 |
| `domain/hci` | 人机交互与用户研究 |
| `domain/llm` | 大语言模型 |
| `domain/medical-imaging` | 医学影像与临床数据分析 |
| `domain/multimodal` | 多模态研究 |
| `domain/nlp` | 自然语言处理 |
| `domain/remote-sensing` | 对地观测与地理空间数据（卫星/航空） |
| `domain/rl` | 强化学习（作为研究领域） |
| `domain/robotics` | 机器人与具身智能 |
| `domain/scientific-computing` | 科学计算与 AI for Science |
| `domain/security` | 安全与对抗（AI 安全、攻防） |
| `domain/speech` | 语音技术与口语处理 |
| `domain/systems` | 机器学习系统与工程（训练、推理、部署） |
| `domain/theory` | 理论与算法基础（学习理论、复杂度） |
| `domain/web` | Web、搜索与推荐 |

### `task/` — 这一页要解决/讨论的预测目标或输出形态

| tag | 说明 |
|---|---|
| `task/alignment` | 对齐（价值/偏好对齐） |
| `task/classification` | 分类 |
| `task/clustering` | 聚类与分组 |
| `task/code-generation` | 代码生成与程序合成 |
| `task/control` | 控制与执行 |
| `task/detection` | 目标检测 |
| `task/evaluation` | 评测与基准分析 |
| `task/forecasting` | 时序/数值预测 |
| `task/generation` | 生成（文本/图像/内容） |
| `task/navigation` | 导航、定位与建图 |
| `task/optimization` | 优化求解（组合/连续优化任务） |
| `task/planning` | 规划与决策 |
| `task/pose-estimation` | 位姿/关键点估计 |
| `task/question-answering` | 问答 |
| `task/ranking` | 排序与推荐 |
| `task/reasoning` | 推理与问题求解 |
| `task/regression` | 回归预测 |
| `task/representation-learning` | 表征学习（学习可迁移的特征空间） |
| `task/retrieval` | 检索与召回 |
| `task/segmentation` | 分割（语义/实例） |
| `task/summarization` | 摘要与压缩 |
| `task/tool-use` | 工具使用与智能体调用 |
| `task/tracking` | 目标跟踪 |
| `task/translation` | 翻译与跨语言转换 |

### `modality/` — 输入数据、传感器或信号的形态

| tag | 说明 |
|---|---|
| `modality/3d` | 三维表示（体素、网格、深度） |
| `modality/audio` | 音频（非语音） |
| `modality/code` | 源代码/程序文本 |
| `modality/graph` | 图与网络结构数据 |
| `modality/image` | 静态图像 |
| `modality/multimodal` | 多模态/跨模态输入 |
| `modality/point-cloud` | 点云/三维扫描 |
| `modality/speech` | 语音信号 |
| `modality/tabular` | 表格/结构化数据 |
| `modality/text` | 文本/自然语言 |
| `modality/time-series` | 时间序列/传感器信号 |
| `modality/video` | 视频/时序影像 |

### `method/` — 架构、机制、学习范式与求解手段

| tag | 说明 |
|---|---|
| `method/attention` | 注意力机制（自注意力、交叉注意力） |
| `method/bayesian` | 贝叶斯方法与概率建模 |
| `method/cnn` | 卷积网络（含 ResNet 等骨干） |
| `method/contrastive` | 对比学习与度量学习 |
| `method/curriculum` | 课程学习 |
| `method/deep-learning` | 深度学习（泛指神经网络方法） |
| `method/diffusion` | 扩散模型与基于分数的生成 |
| `method/distillation` | 知识蒸馏与教师-学生框架 |
| `method/ensemble` | 集成与模型融合 |
| `method/feature-fusion` | 特征融合与多源信息整合 |
| `method/federated` | 联邦学习与去中心化训练 |
| `method/fine-tuning` | 微调与指令微调 |
| `method/foundation-model` | 基础模型/预训练大模型（模型专名统一归这里） |
| `method/gan` | 生成对抗网络与对抗训练 |
| `method/gnn` | 图神经网络与消息传递 |
| `method/in-context-learning` | 上下文学习与少样本提示 |
| `method/interpretability` | 可解释性与归因分析 |
| `method/loss-design` | 损失函数与正则化设计 |
| `method/meta-learning` | 元学习与学会学习 |
| `method/mixture-of-experts` | 混合专家与稀疏激活 |
| `method/multi-task` | 多任务学习与辅助任务 |
| `method/optimization` | 优化算法（梯度下降、学习率调度） |
| `method/parameter-efficient` | 参数高效微调（LoRA、Adapter、PEFT） |
| `method/pretraining` | 预训练与预训练-微调范式 |
| `method/prompt-learning` | 提示学习与软提示 |
| `method/pruning` | 剪枝与稀疏化 |
| `method/quantization` | 量化与低精度推理 |
| `method/reinforcement-learning` | 强化学习与策略优化 |
| `method/retrieval-augmented` | 检索增强（RAG） |
| `method/rnn` | 循环网络（RNN/LSTM/GRU） |
| `method/self-supervised` | 自监督学习（掩码建模、预文本任务） |
| `method/ssm` | 状态空间模型（含选择性扫描类架构） |
| `method/transformer` | Transformer 架构（含 ViT、编码器-解码器） |
| `method/vae` | 变分自编码器与自编码器 |

### `challenge/` — 使任务变难的统计、物理或工程障碍

| tag | 说明 |
|---|---|
| `challenge/alignment-gap` | 对齐缺口（目标与人类意图不一致） |
| `challenge/catastrophic-forgetting` | 灾难性遗忘与持续学习 |
| `challenge/class-imbalance` | 类别不平衡与长尾 |
| `challenge/data-scarcity` | 数据稀缺与低资源 |
| `challenge/distribution-shift` | 分布偏移与域差异 |
| `challenge/efficiency` | 计算与存储效率（轻量化、显存） |
| `challenge/fairness` | 公平性与偏见 |
| `challenge/generalization` | 泛化与分布外表现 |
| `challenge/hallucination` | 幻觉与事实性错误 |
| `challenge/label-noise` | 标签噪声与弱监督 |
| `challenge/latency` | 延迟与实时性约束 |
| `challenge/long-context` | 长上下文与长文档处理 |
| `challenge/privacy` | 隐私与数据保护 |
| `challenge/reproducibility` | 可复现性 |
| `challenge/robustness` | 鲁棒性与对抗干扰 |
| `challenge/scalability` | 可扩展性（规模、数据与模型增长） |
| `challenge/sparsity` | 稀疏性与信息冗余 |

### `data/` — 数据集、基准、合成与仿真、数据治理

| tag | 说明 |
|---|---|
| `data/annotation` | 标注与人工标注流程 |
| `data/benchmark` | 评测基准与协议 |
| `data/curation` | 数据治理（清洗、去重、覆盖度） |
| `data/dataset` | 数据集（含公开数据集专名） |
| `data/leaderboard` | 排行榜与竞赛 |
| `data/open-source` | 开源模型/数据/权重 |
| `data/simulation` | 仿真环境与模拟器 |
| `data/synthetic` | 合成数据与数据增强 |

### `meta/` — 综述、路线图、实验分析与设计空间

| tag | 说明 |
|---|---|
| `meta/analysis` | 实验设计与诊断分析（消融、对比） |
| `meta/design-space` | 设计空间与方案权衡 |
| `meta/position-paper` | 观点/立场文章 |
| `meta/reproduction` | 复现与再实现 |
| `meta/roadmap` | 研究路线图与空白 |
| `meta/survey` | 综述与分类体系 |
| `meta/terminology` | 术语表与概念界定 |
| `meta/tutorial` | 教程与入门指南 |

### 角色 tag（无前缀，位首）

| tag | 说明 |
|---|---|
| `母概念` | 母页：统领 ≥3 个概念页，正文含 `## 子概念` 段 |
| `子概念` | 子页：正文首行含 `> **母概念**：[[母页]]` |

## 四、新增 tag 的流程

1. **先想清楚它属于哪个分面**；若答不出分面，说明它不该是 tag（写进正文即可）。
2. **先查是否已有近义词条**：检索本文件与 `.dsh/tag-vocab.json` 的 `map`。
   同义、单复数、大小写、连字符差异一律合并到已有词条。
3. **门槛**：该词需在 **≥3 个页面**上有实际检索价值，否则合并到最接近的现有词条。
4. 通过后：在 `.dsh/tag-vocab.json` 的 `canonical` 增加 `叶节点: 中文释义`，
   并在 `map` 登记来源词（含被合并的近义词；一条来源可映射到多个规范 tag）。
5. 运行 `python .dsh/scripts/tag_vocab.py --check` 确认自洽，
   再运行 `python .dsh/scripts/tag_vocab.py --emit-doc` 刷新本文件。
6. 运行 `python .dsh/scripts/tag_audit.py` 确认没有未登记 tag 出现在 frontmatter。

## 五、常见误用（反面清单）

| ✗ 错误写法 | ✓ 正确写法 | 理由 |
|---|---|---|
| `llm`, `LLM`, `large-language-model` 并存 | `domain/llm` | 大小写与同义词必须归一 |
| `dl` / `deep-learning` 混用 | `method/deep-learning` | 缩写与全称统一到同一词条 |
| `image-classification` | `modality/image` + `task/classification` | 拆成模态×任务两个分面 |
| `2024` | （删除） | 年份已在 `year`/文件名中 |
| `survey` 用于非综述页 | `meta/survey` | 只在该页确为综述/分类体系时使用 |
| `GPT` 这类模型专名 | `method/foundation-model` | 模型专名不设 tag，正文检索即可 |
| `ablation` | `meta/analysis` | 实验方法归入 meta 分面 |
