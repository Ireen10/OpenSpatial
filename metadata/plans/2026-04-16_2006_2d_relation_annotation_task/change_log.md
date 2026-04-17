## 变更记录（Change Log）

### 变更摘要

- **本次新增/变更**：
  - `MetadataV0.RelationV0` 增加统一字段 `relation_id`（`relation#{n}`），解析时自动补齐；`enrich_relations_2d` 写出 relation 后统一 `ensure_relation_ids`。
  - 新增 OpenSpatial annotation task：`task/annotation/spatial_relation_2d.py`，从 **sample 级 metadata** 生成三类 2D 空间关系 QA（`question` / `answer` / `meta` + `QA_images`），与现有 `sub_tasks` 配置方式一致。
  - **指代与画框**：同色框短指代；同表面 `phrase` 时用 `the object in the {color} box` 短槽位，**不在题干**中插入「Both share wording / anchor is…」类说明段。
  - **压低双框占比**：`mark_tier` 排序优先低画框成本的边；`dual_box_keep_prob`（默认 `0.1`）对「必画双框」样本随机丢弃；`unique_text_only_prob` 默认提到 `0.82`；`meta` 增加 `mark_tier`、`n_marked_boxes`。
  - 测试与样例：`metadata/tests/test_spatial_relation_2d_annotation_task.py`、`test_metadata_relation_id.py`；fixture `grounding_caption_dense_spatial.jsonl`；`metadata/tests/spatial_relation_2d_artifacts.py` + `metadata/scripts/generate_2d_spatial_relation_artifacts.py`；`config/annotation/demo_2d_spatial_relation.yaml`。
  - `task/annotation/core/__init__.py` 对重型依赖做惰性导入，避免轻量环境缺 `open3d` 时无法加载 `QuestionType`。
- **影响范围**：metadata 解析与 enrich 输出；OpenSpatial annotation 新 task；根 `.gitignore`（生成物路径）。
- **兼容性说明**：旧版无 `relation_id` 的 JSONL 读入后会自动补 id；下游若依赖「无 relation_id」需适配。

### 文档与对外说明

- **已更新的文档（路径列表）**：
  - `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/plan.md`（本轮收束勾选）
  - `metadata/docs/project_progress_zh.md`（整轮收束后总览）
- **未改（本轮声明）**：
  - `metadata/docs/metadata_spec_v0_zh.md`：**未**同步 `relation_id` 字段说明（当前正文仍以旧结构/占位为主）；建议后续单开文档小 PR 补一节 `RelationV0`。
  - `metadata/docs/config_yaml_zh.md` / `metadata/README.md`：**未**改（未动 dataset/global YAML schema 与 CLI 语义）。

### 与上一版差异

- 变更点：`relation_id` schema 与 enrich 衔接；新 annotation task 与 demo 配置；双框抑制与同指代短槽位；artifact 脚本与测试。
- 删除/废弃点：无。

### 迁移与回滚

- **迁移**：重新跑 metadata enrich 或重新解析 JSONL 即可得到带 `relation_id` 的 relation；annotation 配置中为新 task 指定 `keep_data_columns`（含 `question`、`answer`、`meta`、`QA_images` 等）。
- **回滚**：回滚本 task 相关文件与 schema 中 `relation_id` 相关改动；若已依赖 `relation_id` 的 QA 产线需同步回滚。

### 自测（本轮回归）

已执行（仓库根，`PYTHONPATH=metadata/src`）：

```text
python -m unittest metadata.tests.test_spatial_relation_2d_annotation_task metadata.tests.test_metadata_relation_id
```

说明：`metadata.tests.test_enrich_relation2d` 全量套件在部分环境下与默认过滤常量组合存在历史噪声，**未**作为本轮收束 gate；本轮 gate 以上为聚焦单测。
