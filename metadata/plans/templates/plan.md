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

