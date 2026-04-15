# 文档与代码如何保持同步（metadata 子项目）

很多能力当前仍是**占位或未接线**。要避免「代码已变、文档仍写旧行为」，建议把**更新文档**当作交付的一部分，并写进你们的 **doc-first** 流程里（见仓库 `.cursor/skills/doc-first-workflow/SKILL.md`）。

---

## 1. 原则（最少要记住的三条）

1. **同一变更里改代码 + 改文档**：合并前自检清单里包含「用户可见说明是否已更新」，不把文档留到「以后再补」。  
2. **单一事实来源（SSOT）**：  
   - **字段/默认值**以 `metadata/src/openspatial_metadata/config/schema.py`（及实际读配置的代码）为准；  
   - **用户可读说明**以 `metadata/docs/` 下对应文档为准；  
   - 文档里写清「详见源码路径」，减少两处各写一套互相漂移。  
3. **占位必须显式**：未实现的行为在文档里用固定句式标出（例如 **「当前 CLI 未实现」**），功能落地时**同一 PR**删掉或改写该句，避免沉默过期。

---

## 2. 维护矩阵（改这里时，记得对表更新）

| 你改了什么（代码/配置） | 建议同步更新的文档（至少检查） |
|---------------------------|----------------------------------|
| `config/schema.py`、`config/loader.py` | `metadata/docs/config_yaml_zh.md` |
| `cli.py`（参数、行为、输出路径） | `metadata/docs/config_yaml_zh.md`、`metadata/README.md` |
| `schema/metadata_v0.py`、校验逻辑 | `metadata/docs/metadata_spec_v0_zh.md`（及 wiki 若仍维护） |
| `tests/`、fixtures、推荐命令 | `metadata/plans/.../test_plan.md`、`metadata/README.md` |
| 新占位 / 已实现某能力 | 对应 `metadata/plans/.../plan.md` 与收尾 **`change_log.md`** |

新增长篇说明时：优先放进 **`metadata/docs/`**，在 **`metadata/README.md`** 的「更多文档」里加一条链接即可。

---

## 3. 与 doc-first 流程对齐（具体怎么做）

每次**非琐碎**功能或行为变更：

1. 在 **`plan.md` 的交付物清单**里显式列出要改的文档路径（模板已预留「文档同步」小节）。  
2. 在 **`test_plan.md`** 里写清如何验证新行为；若文档声称与行为一致，可把「对照某节文档」作为一条检查项。  
3. 实现并跑通测试后，在 **`change_log.md`** 里写「**文档**：已更新 xxx」或「**文档**：无对外行为变更，未改」——**二选一**，避免漏想。

琐碎 bugfix 仍可用 `bugfix_brief.md`，但若动了对外 YAML/CLI 语义，应**升格**为完整流程或至少在 brief 里写一句文档是否要动。

---

## 4. Code review / 合并前自检（可复制）

```markdown
- [ ] `config/schema.py` 与 `metadata/docs/config_yaml_zh.md` 是否一致（字段、默认值、未实现说明）
- [ ] `cli.py` 与 README / config 文档中的命令与参数是否一致
- [ ] 若删除或实现占位，文档中是否已去掉「未实现」表述或改为新语义
- [ ] `change_log.md` 是否记录本次文档变更或声明「无文档变更」
```

---

## 5. 自动化能做什么、不能做什么

- **能做**：在 CI 里跑测试、跑 `pytest`；对 Markdown 做简单链接检查（可选）。  
- **不能可靠替代人**：判断「用户文档读起来是否仍正确」仍需作者或 reviewer 对照上表过一遍。

若日后希望加强约束，可在 CI 中加脚本：例如检测 `config_yaml_zh.md` 中「当前.*未实现」类句式与 `cli.py` 中 `TODO`/`NotImplemented` 的粗略一致性（仅作提醒，易产生误报，需迭代规则）。

---

## 相关文件

- 工作流技能：`.cursor/skills/doc-first-workflow/SKILL.md`  
- 计划 / 变更模板：`metadata/plans/templates/plan.md`、`metadata/plans/templates/change_log.md`  
- YAML 配置说明：`metadata/docs/config_yaml_zh.md`
