# 论文团队规范（受控词表规则）

> 本文件由 `.dsh/scripts/team_vocab.py --emit-doc` 自动生成，**请勿手工编辑**。
>
> **这里只写规则，不列团队。** 词表本体是数据，在你自己的 `.dsh/team-vocab.json` 里 ——
> 它随你摄入的论文增删，本文件不随它变化（改了词表**不需要**重新生成本文件）。
>
> 想知道当前允许哪些团队：`python .dsh/scripts/team_vocab.py --list`

## 一、硬规则

1. **只允许 `.dsh/team-vocab.json` 的 `teams` 段登记过的规范名**出现在论文页 frontmatter 的 `team:` 字段里。
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

**当前词表是空的**（`teams` 里一条都没有）—— 这是出厂状态，不是出错。

出厂只给「机构 / 实验室两级粒度 + 多单位合作全记」这个骨架，**不给任何具体团队**。
理由：团队名是最贴着你研究领域的东西，预设一套（比如塞满某些大厂与大庙）既会误导别的领域的使用者，
也会让人错过自己领域里真正该追踪的组。

**冷启动阶段的放宽规则**（仅当词表为空时适用）：

- **首篇论文取词即可**，不需要凑够若干页 —— 团队是**事实字段**，本来就不同于 tag 的检索词门槛；
- **但纪律不放松**：取用的团队必须在**同一次 ingest 的收尾**登记进 `.dsh/team-vocab.json` 的
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

5. 未登记的新团队：先在 `.dsh/team-vocab.json` 登记 `teams` 与 `aliases`，
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

> 权威来源是 `<工作区根>/.dsh/team-vocab.json`。想换一整套团队词表（例如把团队表换成"实验室/课题组"级别），
> 见仓库里的 `docs/CUSTOMIZE.md`。

## 五、常见误用（反面清单）

> 下表用**示例**说明错误模式，示例里的团队名不代表你的词表内容，具体以 `.dsh/team-vocab.json` 为准。

| ✗ 错误写法 | ✓ 正确写法 | 理由 |
|---|---|---|
| 同一团队两种写法：`Meta AI`、`FAIR`、`Facebook AI Research` | 归一到一条规范名，其余进 `aliases` | 别名并存会让按团队检索漏掉一半 |
| 只记第一单位 | 多单位全部列出 | 「这篇是谁做的」本身就是检索维度 |
| `School of Computer Science, Xxx University` | `Xxx University` | 院系不是团队，是机构的下级 |
| `Xxx University (Key Laboratory of Y)` 但 `Xxx University` 未登记 | 两条都登记，实验室条目的 `base` 指向机构条目 | 没有机构条目，按机构聚合时会漏 |
| 把邮箱、基金号、`Authorized licensed use…` 水印当团队 | （删除） | 它们不是署名单位 |
| 双盲投稿硬猜单位 | `team: ["待确认"]` + 日志说明 | 事实字段宁可留白，不可臆造 |
