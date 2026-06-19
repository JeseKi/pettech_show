---
name: wechat-topic-wiki
description: 维护本仓库的公众号选题 wiki，把 `material/`、`raw/`、`main/` 文章中的 热点、痛点、解决方案、选题、搜索入口 沉淀成可复用资产。Use when asked to create, initialize, update, audit, or use a topic wiki for WeChat article strategy.
---

# WeChat Topic Wiki

维护一个轻量的公众号选题资产库。

这个 wiki 不是文章归档，也不是通用知识库。它的目标是让后续写作可以复用五类资产：

- 热点：最近发生的事件、新闻、产品变化、平台风险、市场讨论。
- 痛点：谁在什么情境下遇到什么问题，以及这个问题会带来什么具体损失。
- 解决方案：我们提供的工具、服务、教程、方法或工作流。
- 选题：把至少一个热点、一个痛点、一个或数个解决方案组合成一篇文章角度；来自 material 的选题应优先保留为疑问句。
- 搜索入口：用户真实可能搜索的长尾关键词和意图，用来指导标题覆盖，而不是泛泛标签。

不要维护“钩子”目录。优惠券、客服、私域引流等转化信息可以在文章索引里顺手记录，但不是一级 wiki 资产。

## Wiki 目录

在仓库根目录使用这个结构：

```text
wiki/
  SCHEMA.md
  index.md
  log.md
  hotspots/
  pain-points/
  solutions/
  topics/
  search-intents/
  articles/
```

初始化或更新 wiki 时，如果目录不存在，就创建缺失目录。

## 核心规则

- 不要把文章全文复制进 wiki。
- 不要每写一篇文章就机械创建 4 个新页面；先搜索，能复用就复用。
- 页面要短，重点记录可复用判断，不写成公众号正文。
- `topics/` 是核心层。每个 topic 必须连接至少一个 hotspot、一个 pain point、一个 solution；没有 solution 引用的 topic 是不合格资产。
- 从 material 入库时，把 `选题` 里的每个疑问句创建或更新为一个 topic；每个 topic 的 `solutions` frontmatter 必须列出一个或多个对应 solution slug，素材支持多个方案时全部列入。
- `search-intents/` 维护关键词池。每页聚合一个选题或主题簇下的搜索入口，不要为每篇文章机械创建单独页面。
- `articles/` 只做文章索引，记录这篇文章用了哪些资产。
- slug 使用稳定的 lowercase ASCII，例如 `openai-anthropic-account-bans.md`、`chatgpt-history-export-plugin.md`。
- 内部链接使用 wikilink，例如 `[[hotspots/openai-anthropic-account-bans]]`。
- hook、coupon、private-domain copy 不要写成一级资产；除非它影响选题策略，否则不要放进热点、痛点、解决方案页面。
- 使用中文来进行编写。

## 工作流

1. 读取相关来源：
   - 如果是已有文章：读取 `main/<date>/<output_id>/metadata.json` 和 `main.md`。
   - 如果是素材入库：读取 `material/<date>/*.json` 里的结构化热点、痛点、解决方案、选题和 `搜索入口`；必要时读取对应 `raw/<date>/*.md` 补足场景、图片和操作细节。
   - 如果是计划中的文章：读取选定的 `material/<date>/*.json`、相关 `raw/<date>/*.md`，以及用户补充的热点、痛点、解决方案。
2. 提取或确认五件事：
   - 热点：这篇文章为什么现在值得写。
   - 痛点：谁痛、在什么场景痛、会损失什么。
   - 解决方案：文章推荐什么，以及它如何解决痛点。
   - 选题：热点、痛点、解决方案如何组合成一个可直接扩写的疑问句文章角度。
   - 搜索入口：用户会用哪句话搜到这类文章，以及哪个入口最适合标题完整保留。
3. 先搜索已有 wiki 页面，再决定创建或更新。
4. 如果概念已经存在，更新旧页面；只有概念明显不同，才创建新页面。
5. 如果 material 包含 `搜索入口`，创建或更新 `search-intents/<topic-or-cluster-slug>.md`，把关键词按意图类型归并去重。
6. 对已生成文章，创建或更新 `articles/<output_id>.md`。如果只来自 material、还没有成稿，不创建 article 页面；对应 topic 使用 `status: idea` 或 `drafted`，并在正文记录 source material。
7. 为每个 topic 核对 `solutions`：至少引用一个解决方案页面；如果 material 中的同一选题可由多个方案共同支撑，全部写入 `solutions`，并在 `## 核心判断` 或 `## 复用方式` 中说明选题和方案的对应关系。
8. 更新 `index.md`，并在 `log.md` 追加一行维护记录。

## 页面类型

### 热点 / Hotspot

用于记录有时效性的外部背景。

frontmatter 必填字段：

- `title`
- `type: hotspot`
- `status`: `active`、`fading`、`expired`
- `created`
- `updated`
- `tags`
- `related_pain_points`
- `related_topics`

正文小节：

- `## 发生了什么`
- `## 为什么重要`
- `## 可用角度`
- `## 注意事项`

### 痛点 / Pain Point

用于记录“人群 + 情境 + 问题 + 损失”。

frontmatter 必填字段：

- `title`
- `type: pain_point`
- `audience`
- `scenario`
- `created`
- `updated`
- `tags`
- `related_hotspots`
- `related_solutions`
- `related_topics`

正文小节：

- `## 痛点`
- `## 最强场景`
- `## 具体损失`
- `## 写作提醒`

### 解决方案 / Solution

用于记录工具、服务、教程、方法、工作流或产品方案。

frontmatter 必填字段：

- `title`
- `type: solution`
- `created`
- `updated`
- `tags`
- `solves`
- `related_topics`

正文小节：

- `## 解决什么`
- `## 怎么呈现`
- `## 证据和素材`
- `## 最适合的痛点`
- `## 注意事项`

### 选题 / Topic

用于记录一个可复用文章角度。它是整个 wiki 的核心单位。

topic 的 `title` 应优先使用疑问句，尤其是从 material `选题` 入库时。`solutions` 必须是非空数组，引用一个或多个 `wiki/solutions/` 页面 slug；若没有可引用方案，先创建或更新 solution 页面，再创建 topic。正文的 `## 核心判断` 或 `## 复用方式` 需要说明这个疑问句为什么由这些解决方案承接。

frontmatter 必填字段：

- `title`
- `type: topic`
- `status`: `idea`、`drafted`、`used`、`retired`
- `created`
- `updated`
- `hotspots`
- `pain_points`
- `solutions`
- `articles`
- `tags`

正文小节：

- `## 核心判断`
- `## 文章结构`
- `## 复用方式`
- `## 避免事项`

### 文章索引 / Article

只用于索引已生成文章，不复制正文。

frontmatter 必填字段：

- `title`
- `type: article`
- `date`
- `output_id`
- `source_file`
- `hotspots`
- `pain_points`
- `solutions`
- `topics`

正文小节：

- `## 摘要`
- `## 资产映射`
- `## 备注`

### 搜索入口 / Search Intent

用于记录一个选题或主题簇可以覆盖的用户搜索入口。它不是普通关键词页面，而是标题生成前的入口分配表。

frontmatter 必填字段：

- `title`
- `type: search_intent`
- `created`
- `updated`
- `topics`
- `hotspots`
- `pain_points`
- `solutions`
- `source_materials`
- `tags`

正文小节：

- `## 用户会怎么搜`
- `## 关键词池`
- `## 覆盖分配`
- `## 标题使用提醒`
- `## 避免事项`

## 模板

热点模板：

```markdown
---
title: OpenAI / Anthropic account risk increases
type: hotspot
status: active
created: 2026-05-08
updated: 2026-05-08
tags: [account-risk, ai-tools]
related_pain_points:
  - ai-heavy-users-losing-chat-history
related_topics:
  - backup-chatgpt-history-before-ban
---

## 发生了什么

## 为什么重要

## 可用角度

## 注意事项
```

痛点模板：

```markdown
---
title: AI heavy users may lose chat history
type: pain_point
audience: ChatGPT heavy users
scenario: Account ban, login restriction, or abnormal account state
created: 2026-05-08
updated: 2026-05-08
tags: [data-loss, chatgpt]
related_hotspots:
  - openai-anthropic-account-bans
related_solutions:
  - chatgpt-history-export-plugin
related_topics:
  - backup-chatgpt-history-before-ban
---

## 痛点

## 最强场景

## 具体损失

## 写作提醒
```

解决方案模板：

```markdown
---
title: ChatGPT history export plugin
type: solution
created: 2026-05-08
updated: 2026-05-08
tags: [plugin, backup, chatgpt]
solves:
  - ai-heavy-users-losing-chat-history
related_topics:
  - backup-chatgpt-history-before-ban
---

## 解决什么

## 怎么呈现

## 证据和素材

## 最适合的痛点

## 注意事项
```

选题模板：

```markdown
---
title: ChatGPT 账号有风险时，重度用户该先怎么备份聊天记录？
type: topic
status: used
created: 2026-05-08
updated: 2026-05-08
hotspots:
  - openai-anthropic-account-bans
pain_points:
  - ai-heavy-users-losing-chat-history
solutions:
  - chatgpt-history-export-plugin
articles:
  - 260508_2
tags: [chatgpt, backup, account-risk]
---

## 核心判断

账号风险把聊天记录从普通历史记录变成工作流资产风险，文章要用聊天记录导出插件承接“先备份再迁移”的解决方案。

## 文章结构

## 复用方式

## 避免事项
```

文章索引模板：

```markdown
---
title: OpenAI and Anthropic risk increased, back up chat history first
type: article
date: 2026-05-08
output_id: 260508_2
source_file: main/260508/260508_2/main.md
hotspots:
  - openai-anthropic-account-bans
pain_points:
  - ai-heavy-users-losing-chat-history
solutions:
  - chatgpt-history-export-plugin
topics:
  - backup-chatgpt-history-before-ban
---

## 摘要

## 资产映射

## 备注
```

搜索入口模板：

```markdown
---
title: Codex token cost search entries
type: search_intent
created: 2026-06-11
updated: 2026-06-11
topics:
  - codex-token-resource-pool
hotspots:
  - ai-coding-token-cost
pain_points:
  - ai-coding-users-need-stable-token-pool
solutions:
  - codex-token-resource-pool
source_materials:
  - material/260505/example.json
tags: [codex, token-cost, ai-coding]
---

## 用户会怎么搜

记录这个主题簇最常见的搜索场景。

## 关键词池

| 意图类型 | 关键词 | 搜索意图 | 适合文章角度 | 标题使用建议 | 优先级 | 来源依据 |
| --- | --- | --- | --- | --- | --- | --- |

## 覆盖分配

记录主稿和变体应优先覆盖哪些入口，避免标题集中抢同一个词。

## 标题使用提醒

说明哪些关键词建议完整保留，哪些只作为方向。

## 避免事项

记录不能承接、容易标题党或容易互相抢词的表达。
```

## Index 和 Log

`wiki/index.md` 按这些板块列出现有资产：

- 活跃热点
- 可复用痛点
- 可用解决方案
- 按状态分类的选题
- 搜索入口关键词池
- 最近文章映射

`wiki/log.md` 保持追加式，简短即可：

```markdown
- 2026-05-08: Added topic `backup-chatgpt-history-before-ban` from `260508_2`.
```

## 完成前检查

- 每个 topic 至少连接一个 hotspot、一个 pain point、一个 solution；没有 solution 引用的 topic 必须补齐后才能完成。
- 从 material 入库的每个疑问句选题都已对应创建或更新 topic，并在 `solutions` 中引用一个或多个解决方案。
- material 中有 `搜索入口` 时，已创建或更新对应 `search-intents/` 页面。
- 新页面不是已有页面的重复版本。
- article 页面没有复制正文全文。
- 没有创建一级 hook 页面或 hook 目录。
- `index.md` 和 `log.md` 已同步更新。
