# 执行计划（Plan）— 2D 关系增强

> **依赖**：`design.md` 讨论稿（过滤策略、最小输入契约）。**§7 未决问题确认前**，仅维护概要，不写可执行排期。

**已定方向摘要**：实现 `ref_frame=image_plane` 的 `relations` 计算 + 可配置过滤；输出对齐 `RelationV0` + `aux.enrich_2d` 统计。

**待 design 锁稿后补全**：交付物清单、任务拆解（库函数 / CLI / adapter 挂钩）、测试与文档同步勾选。

## 执行计划（Plan）

### 交付物清单

- 文档：
- 代码：
- 配置：
- 样例/fixtures：

### 文档同步（与本变更一并交付）

列出**必须随本变更更新或显式声明「无需更新」**的用户可见说明（路径写全，便于 reviewer 勾选）：

- [ ] `metadata/docs/config_yaml_zh.md`（若动 global/dataset schema、loader、CLI 配置语义）
- [ ] `metadata/docs/metadata_spec_v0_zh.md`（若动 v0 模型或对外 JSON 结构）
- [ ] `metadata/README.md`（若动安装、命令、目录结构说明）
- [ ] `metadata/plans/<本次目录>/test_plan.md`（若动可测行为）
- [ ] `metadata/docs/project_progress_zh.md`（**仅**在整轮结束：开发 + 自测通过 + `change_log.md` 之后更新；见 `metadata/docs/project_progress_zh.md` 页首）
- [ ] 其他：`…………`（无则写「无」）

约定：占位/未接线能力在文档中用明确措辞标出；**实现或删除该能力时，同一变更内**同步改写对应段落（见 `metadata/docs/docs_sync_convention_zh.md`）。

### 任务拆解

按顺序列出可执行的任务项，每项要包含：
- 目标
- 修改/新增的文件
- 完成条件

### 里程碑与回滚

- 里程碑：
- 回滚策略（如何撤销、如何验证恢复）：
