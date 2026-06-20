---
name: wechat-seed-matrix-builder
description: 从 DailyWriting 的 material/ 结构化素材和 wiki/ 选题资产中提炼批量写作 seed，生成可供 $wechat-article-batch-orchestrator 使用的规划 CSV。适用于按热点、痛点、解决方案、账号矩阵、CTA/hook 包和发布节奏批量设计公众号选题种子。
---

# WeChat Seed Matrix Builder

当用户希望从素材库生成批量文章 seed、规划 CSV、选题矩阵或给 `$wechat-article-batch-orchestrator` 准备 `source_table` 时，使用这个 skill。

这个 skill 是上游规划层，不写文章、不生成配图、不启动批量生产。它把 `material/` 和可选 `wiki/` 里的选题资产整理成稳定 CSV。每个 seed 必须显式包含文章结构四件套：选题、痛点、解决方案、钩子。

## 输入变量

从用户请求中获取或推断这些变量：

- `material_dirs`：一个或多个素材目录，例如 `material/260518`。
- `wiki_dir`：可选，默认 `wiki`。用于查重和补充热点、痛点、解决方案、topic。
- `output_csv`：输出 CSV 路径，例如 `AIFC_matrix_distribution_plan.csv` 或 `seed_matrix_260601.csv`。
- `start_seed`：起始 seed ID，例如 `S001`。
- `start_day`：起始天编号，例如 `D01`。
- `slots_per_day`：每天排几个 seed，默认 `3`。
- `seeds_per_material`：每个 material 生成几个 seed，默认 `1`；当素材自带 `选题` 数不足时，脚本会基于已有选题扩展不同写作角度。
- `max_seeds`：可选，限制本次输出 seed 数。
- `hook_package`、`primary_hook_ids`：可选；用户未提供时留空，不强行添加默认转化钩子。
- `expected_article_count`：每个 seed 下游预计生成文章数，默认 `10`。

## 工作流

1. 读取用户指定的 `material_dirs`。必要时抽样查看 JSON，确认它们符合 `wechat-raw-materializer` 的 material schema。
2. 可选读取 `wiki/SCHEMA.md` 和相关 `wiki/topics/`、`wiki/hotspots/`、`wiki/pain-points/`、`wiki/solutions/`，用于避免重复 seed 或补足角度。
3. 运行生成脚本：

   ```bash
   python3 .agents/skills/wechat-seed-matrix-builder/scripts/build_seed_matrix.py \
     --material-dir <material/YYMMDD> \
     --output <output_csv> \
     --start-seed S001 \
     --start-day D01 \
     --slots-per-day 3
   ```

   常用可选参数：

   ```bash
   --seeds-per-material 2
   --max-seeds 30
   --hook-package <name>
   --primary-hook-ids "H001|H002"
   --expected-article-count 10
   --force
   ```

4. 读取输出 CSV，重点检查并人工修订这些策略字段：
   - `content_pool`
   - `topic`
   - `pain_point`
   - `solution`
   - `hook`
   - `mother_topic_prompt`
   - `primary_account_type`
   - `backup_account_types`
   - `hook_package`
   - `primary_hook_ids`
   - `cta_strategy`
   - `publishing_note`
5. 运行校验：

   ```bash
   python3 .agents/skills/wechat-seed-matrix-builder/scripts/validate_seed_matrix.py \
     --source-table <output_csv>
   ```

6. 完成后汇报输出 CSV、seed 数、起止 seed、是否通过校验，以及是否可直接交给 `$wechat-article-batch-orchestrator`。

## CSV Schema

默认输出字段与批量编排 skill 兼容：

```text
day,slot,seed_id,content_pool,topic,pain_point,solution,hook,mother_topic_prompt,variant_ids_to_generate,expected_article_count,primary_account_type,backup_account_types,hook_package,primary_hook_ids,cta_strategy,publishing_note
```

字段含义：

- `day`：发布或生产批次天编号，如 `D01`。
- `slot`：当天第几个 seed。
- `seed_id`：稳定 ID，如 `S001`。下游按它选择行。
- `content_pool`：短标签，表示该 seed 属于哪个内容池。
- `topic`：选题，一篇文章要写的核心角度。
- `pain_point`：痛点，目标读者在什么情境下遇到什么问题或损失。
- `solution`：解决方案，文章要交付的方法、产品、工作流、判断框架或行动方案。
- `hook`：钩子，文章结尾或转化处承接的动作。可以是中性收藏/关注/咨询，也可以是用户提供的 hook 包；不要凭空添加二维码或报名入口。
- `mother_topic_prompt`：母题 prompt，是下游主稿生成最重要的规划字段。
- `variant_ids_to_generate`：默认 `V01|...|V10`。
- `expected_article_count`：默认 `10`，通常表示主稿加 9 个变体。
- `primary_account_type`、`backup_account_types`：账号矩阵定位。
- `hook_package`、`primary_hook_ids`、`cta_strategy`：钩子的拆分策略字段；没有用户提供时可以留空或写非强转化动作，但 `hook` 列仍要说明中性承接方式。
- `publishing_note`：发布和去重提醒。

## 约束

- 不要在 skill 或脚本里写死某个项目的数据源路径。`material_dirs` 和 `output_csv` 必须来自用户请求或本次推断。
- 不要强行添加二维码、报名入口、教程群、优惠包等 hook。用户未提供时，`hook` 写中性承接方式，`hook_package` 和 `primary_hook_ids` 可以留空。
- 生成器给出的策略字段是初稿。批量生产前，agent 应检查母题 prompt 是否足够差异化，避免同一批 seed 只是在换词。
- 不要覆盖用户已有 CSV，除非用户明确允许或命令带 `--force`。
- 输出 CSV 必须至少包含 `seed_id` 列，因为 `$wechat-article-batch-orchestrator` 的计划脚本依赖它。
- 如果素材 JSON 缺字段，优先跳过坏文件并报告；不要编造不存在的事实。
