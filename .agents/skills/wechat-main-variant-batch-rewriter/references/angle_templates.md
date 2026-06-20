# Narrative Angle Templates

Use these templates to produce variants that preserve the same hotspot, pain, solution, and hook while changing the article's visible structure.

## Selection Rule

Pick templates that fit the source material. Do not force every template onto every article.

- Risk / failure articles: prefer `案例复盘型`, `成本账型`, `问题诊断型`, `反常识型`, `趋势判断型`.
- Tutorial / prompt / workflow articles: prefer `问题诊断型`, `方法论拆解型`, `分类地图型`, `清单自查型`, `案例复盘型`.
- Multi-option articles: prefer `分类地图型`, `清单自查型`, `反常识型`.
- Decision / budget / whether-to-start articles: prefer `路径选择型`, `成本账型`, `清单自查型`.
- Industry or product-shift articles: prefer `趋势判断型`, `反常识型`, `成本账型`.

## Templates

### 问题诊断型

Structure: common mistake -> why it fails -> judgment standards -> correct path -> hook.

Use when the source has a clear wrong behavior, such as unsafe recharge, bad prompts, broken workflow, or misuse of a tool.

### 案例复盘型

Structure: concrete scene -> failure process -> cause analysis -> better choice -> hook.

Use when the article can start from a realistic failure scenario. The case may be composite, but it must not invent factual claims beyond the source.

### 成本账型

Structure: surface gain -> hidden cost -> risk comparison -> better ROI path -> hook.

Use when the source has a "cheap but unstable", "fast but unreliable", or "simple but hard to scale" tradeoff.

### 方法论拆解型

Structure: principle -> modules -> why each module works -> reusable method -> hook.

Use for prompt, workflow, tutorial, design, product, and tool-use articles. Each module must explain why it works, not just list examples.

### 分类地图型

Structure: category framework -> use cases / risks / value -> selection path -> hook.

Use when the source contains several types, methods, templates, products, plans, or risks. The classification must help the reader choose.

### 清单自查型

Structure: self-check question -> 5-7 checks -> wrong/right practice -> action path -> hook.

Use for practical, bookmarkable articles. The checklist must change the reading experience, not just convert source paragraphs into bullets.

### 反常识型

Structure: familiar belief -> real variable -> new priority order -> judgment standard -> hook.

Use when the article can overturn a common assumption, such as "cheaper is better" or "longer prompt is stronger".

### 趋势判断型

Structure: what changed -> why the old playbook fails -> new standard -> who benefits -> action suggestion -> hook.

Use when the source can be framed as a market, platform, model, tool, or user-behavior shift.

### 路径选择型

Structure: decision forks -> cost / benefit / risk comparison -> exclude weak paths -> recommended priority -> hook.

Use when the article helps readers decide whether to start, pause, scale, buy, join, switch tools, or allocate budget.

## Similarity Guardrails

- Do not preserve the source paragraph order by default.
- Do not use the same first 300 characters across variants.
- Do not repeat exact explanatory paragraphs across variants unless they are mandatory promotional text, links, or image placeholders.
- Move the hook across variants: recommendation path, checklist result, method landing step, trend action, or closing conversion.
- Keep the invariant brief stable, but change the route used to reach it.
