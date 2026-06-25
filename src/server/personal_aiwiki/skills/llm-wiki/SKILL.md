# llm-wiki

用于维护个人 AI Wiki 的 Skill。它把资料、结论和可复用知识沉淀到一个长期存在、互相链接的 Markdown 知识库中。

## 工作区

- 平台会提供 `WIKI_PATH`，它指向当前用户个人 workspace 下的 `wiki/` 目录。
- 如果没有显式环境变量，以任务提示词中的 `WIKI_PATH` 为准。
- `WIKI_PATH` 的父目录是个人 workspace，通常包含：
  - `raw/`：原始资料。只追加，不改写。
  - `wiki/`：结构化 Wiki。
- 不要访问或修改 `WIKI_PATH` 父目录之外的任何路径。
- 不同任务会共享同一个用户 workspace，因此每次任务都要先读取已有内容，再增量更新。

## 目录结构

`wiki/` 至少包含：

- `SCHEMA.md`：结构和写作规范。
- `index.md`：个人 Wiki 首页、主要入口、最近更新。
- `log.md`：导入和重大修订日志。
- `entities/`：人物、组织、产品、项目、地点等实体。
- `concepts/`：概念、方法、原则、事实卡、知识点。
- `comparisons/`：对比、权衡、决策依据。
- `queries/`：值得长期保存的问题、答案和检索路径。

可按内容需要新增子目录，但必须先更新 `SCHEMA.md` 说明用途。

## 任务开始

每次任务都必须先做三件事：

1. 读取 `SCHEMA.md`，确认当前结构约定。
2. 读取 `index.md`，了解主要入口和现有资产。
3. 读取 `log.md`，了解最近导入和修订。

如果三个文件不存在，先初始化 Wiki。

## 初始化

初始化时创建：

- `SCHEMA.md`
- `index.md`
- `log.md`
- `entities/`
- `concepts/`
- `comparisons/`
- `queries/`

`index.md` 应包含：

- Wiki 名称。
- 最近更新。
- 主要入口。
- 高频问题入口。
- 重要实体、概念和比较入口。

`log.md` 应按日期追加记录，不要覆盖旧日志。

## Frontmatter

每个 Wiki 词条都必须使用 YAML frontmatter：

```yaml
---
title: 词条标题
type: entity | concept | comparison | query | note | index
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [标签1, 标签2]
sources:
  - raw/260626/example.md
confidence: high | medium | low
---
```

要求：

- `title` 必填。
- `type` 必填。
- `created` 和 `updated` 必填。
- `tags` 必须是数组。
- 使用了原始资料时必须写入 `sources`。
- 不确定或推断性内容必须标注 `confidence`，并在正文说明依据。

## 链接

- 使用 `[[folder/slug]]` 或 `[[folder/slug|展示文本]]` 链接相关词条。
- 新词条必须能从 `index.md` 或其它已连接词条到达。
- 发现坏链接要修复；无法确定目标时，在 `log.md` 记录待处理项。
- 不要创建孤立页面。

## 导入资料

导入资料时：

1. 阅读本次任务提示中列出的 raw markdown。
2. 只提取可复用知识，不复制全文。
3. 把人物、组织、产品、项目写入 `entities/`。
4. 把方法、概念、事实、原则写入 `concepts/`。
5. 把选择、差异、优劣势和权衡写入 `comparisons/`。
6. 把有长期价值的问题写入 `queries/`。
7. 更新相关旧词条，而不是重复创建近似词条。
8. 更新 `index.md` 和 `log.md`。

原始资料必须保留在 `raw/`，不要修改、移动或删除。

## 增量维护

整理资料时同步检查：

- 孤立词条。
- 坏 wikilink。
- 缺失 frontmatter。
- `index.md` 未覆盖的重要词条。
- `log.md` 缺失最近任务记录。
- 重复词条。
- 明显矛盾或过期内容。
- 超长页面是否需要拆分。
- 标签是否过散或过泛。

修复范围应小而明确。大规模重组前必须在 `answer.md` 中说明建议，不要擅自重构整个 Wiki。

## 写作风格

- 使用中文。
- 事实和观点分开写。
- 优先短段落、列表和小标题。
- 结论要带依据。
- 不确定内容不要写成确定事实。
- 不要把 raw 原文搬进 Wiki。

## 完成条件

任务完成前确认：

- `index.md` 已更新。
- `log.md` 已追加记录。
- 新词条有 frontmatter。
- 新词条有链接入口。
- 如有本次整理摘要，已写入 `answer.md`。
- 没有修改 `raw/` 中既有原始资料。
