# Tag 规范（受控词表规则）

> 本文件由 `.dsh/scripts/tag_vocab.py --emit-doc` 自动生成，**请勿手工编辑**。
>
> **这里只写规则，不列词条。** 词表本体是数据，在你自己的 `.dsh/tag-vocab.json` 里 ——
> 它随你的研究领域增删，本文件不随它变化（改了词表**不需要**重新生成本文件）。
>
> 想知道当前允许哪些词：`python .dsh/scripts/tag_vocab.py --list`

## 一、硬规则

1. **只允许 `.dsh/tag-vocab.json` 的 `canonical` 段登记过的 tag** 出现在 `wiki/**/*.md` 的 frontmatter `tags:` 字段中。
   封闭词表是防止标签膨胀的唯一机制：没有它，tag 数量会随页数线性增长，最终失去检索价值。
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

## 二、七个分面

**分面是固定的，叶节点是你的。** 给一页选 tag，就是逐分面问一遍自己：

| 分面 | 收什么 | 判断问题 |
|---|---|---|
| `domain/` | 研究面向的应用场景、学科领域与数据来源平台 | 这一页服务于哪个应用/平台？ |
| `task/` | 这一页要解决/讨论的预测目标或输出形态 | 这一页的输出是什么？ |
| `modality/` | 输入数据、传感器或信号的形态 | 输入数据是什么形态/传感器？ |
| `method/` | 架构、机制、学习范式与求解手段 | 用了什么架构或机制？ |
| `challenge/` | 使任务变难的统计、物理或工程障碍 | 是什么让任务变难？ |
| `data/` | 数据集、基准、合成与仿真、数据治理 | 涉及哪个数据集/基准/仿真？ |
| `meta/` | 综述、路线图、实验分析与设计空间 | 这是综述、路线图还是实验分析？ |

> 角色 tag `母概念` / `子概念` 不走分面，用于标记概念层级（见硬规则 2）。
>
> **不设第八个分面**：分面是结构，不是词表。一个词若归不进上面任何一面，
> 说明它不该是 tag —— 写进正文即可。

## 三、查看与维护词表

| 命令 | 作用 |
|---|---|
| `python .dsh/scripts/tag_vocab.py --list` | **列出当前词表全部词条**（按分面分组） |
| `python .dsh/scripts/tag_vocab.py --check` | 自洽性校验（`map` 指向的 tag 是否存在、有无死词条、分面是否合法） |
| `python .dsh/scripts/tag_vocab.py --emit-doc` | 重新生成本文件（**只有改规则时才需要**） |
| `python .dsh/scripts/tag_audit.py` | 全库审计：未登记 tag、超限、频次分布 |
| `python .dsh/scripts/tag_audit.py --unregistered` | 只列出未登记的 tag |
| `python .dsh/scripts/tag_apply.py` | 按 `map` 迁移历史 tag（**预演**，不写盘） |
| `python .dsh/scripts/tag_apply.py --apply` | 实际改写并生成备份到 `.dsh/tmp/tags-backup-*.json` |
| `python .dsh/scripts/tag_apply.py --rollback <备份>` | 从备份精确还原 tags |
| `python .dsh/scripts/tag_verify_migration.py` | 独立验证：备份 → 重新推导 → 与磁盘逐页比对 |

> 权威来源是 `<工作区根>/.dsh/tag-vocab.json`。想换一整套领域词表，
> 见仓库里的 `docs/CUSTOMIZE.md` → 「换 tag 词表」一节。

## 四、新增 tag 的流程

1. **先想清楚它属于哪个分面**；若答不出分面，说明它不该是 tag（写进正文即可）。
2. **先查是否已有近义词条**：跑 `tag_vocab.py --list`，并检索 `.dsh/tag-vocab.json` 的 `map`。
   同义、单复数、大小写、连字符差异一律合并到已有词条。
3. **门槛**：该词需在 **≥3 个页面**上有实际检索价值，否则合并到最接近的现有词条。
4. 通过后：在 `.dsh/tag-vocab.json` 的 `canonical` 增加 `叶节点: 中文释义`，
   并在 `map` 登记来源词（含被合并的近义词；一条来源可映射到多个规范 tag）。
5. 运行 `python .dsh/scripts/tag_vocab.py --check` 确认自洽。
6. 运行 `python .dsh/scripts/tag_audit.py` 确认没有未登记 tag 出现在 frontmatter。

## 五、常见误用（反面清单）

> 下表用**示例**说明错误模式，帮助你识别同类问题；示例里的词条名不代表你的词表内容，
> 具体以 `.dsh/tag-vocab.json` 为准。

| ✗ 错误写法 | ✓ 正确写法 | 理由 |
|---|---|---|
| 同义/大小写并存：`dl`、`deep-learning`、`DL` | 归一到单一词条（如 `method/deep-learning`） | 同义词条必须合并，否则检索被稀释 |
| 复合词：`image-classification` | `modality/image` + `task/classification` | 一个 tag 只表达一个维度 |
| 年份：`2024` | （删除） | 年份已在 frontmatter 的 `year` / 文件名中 |
| 模型或数据集专名：`GPT`、`ImageNet` | `method/foundation-model`、`data/dataset` | 专名靠正文检索，不占 tag 名额 |
| 实验手段：`ablation` | `meta/analysis` | 实验方法归入 meta 分面 |
| 把非综述页标成 `meta/survey` | 改挂 `meta/analysis` 或对应 `task/` | tag 要描述页面实际是什么 |
| 一页挂 9 个以上主题 tag | 压到 8 个以内（推荐 3–5） | 挂满等于没挂，区分度归零 |
