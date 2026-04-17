# Change log — qa_items → grounding 训练导出（首版）

## 2026-04-17

### 行为与代码

- **标注任务** `spatial_relation_2d`：不再向样本行写入 `QA_images` / 图像 bytes；仍生成 `question` / `answer` / `meta`（含画框语义与 `anchor_id`/`target_id` 等）。
- **配置** `demo_2d_spatial_relation.yaml`：`keep_data_columns` 去掉 `QA_images`。
- **导出包** `openspatial_metadata.export`：
  - `visual_group_key` / `group_qa_items`（按 `n_marked_boxes`、`marked_roles`、`mark_colors` 分组）。
  - **PIL** 延后重绘 JPEG（原图或按 meta + `objects[].bbox_xyxy_norm_1000` 画框），不依赖 `task.VisualMarker`。
  - `write_tar_and_tarinfo`：写出 `part_{id:06d}.tar` 与 `part_{id:06d}_tarinfo.json`（`offset_data` 优先用 `TarInfo.offset_data`，否则 `offset + 512`）。
  - `export_metadata_to_training_bundle`：写出 `images/` + `jsonl/` 下 `part_000000` 三件套。
  - `attach_task_result_as_qa_items`：把 `AnnotationGenerator` 行 dict 转为带 `qa_items` 的 `MetadataV0`（便于 E2E）。
- **依赖**：`metadata/pyproject.toml` 主依赖增加 `Pillow>=9.0`。

### 测试

- `metadata/tests/test_export_grouping.py`
- `metadata/tests/test_grounding_export_e2e.py`（dense fixture + 任务 + 导出目录验收）

### 已知限制

- 多 part、checkpoint、分布式写入：按 plan 推迟。
- tar 内 `offset_data` 回退为 `offset+512`，若将来使用长路径/GNU 扩展头，需改为严格解析或仅依赖 Python 3.12+ `offset_data`。

### 2026-04-17（晚）

- **`relative_path` 命名**：改为以 **`sample.image.path`** 为基准；原图组沿用该路径；带框组为同目录 `{stem}_m{8hex}.jpg`（`8hex` = SHA-256(`visual_group_key`) 前 8 位 hex，实现见 `openspatial_metadata.export.paths`）。
