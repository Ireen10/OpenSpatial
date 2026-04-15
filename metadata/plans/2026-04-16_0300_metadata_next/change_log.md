# 变更记录（Change Log）：2D 关系增强（2026-04-16）

## 变更摘要

- **新增** `openspatial_metadata.enrich`：`enrich_relations_2d`（`MetadataV0` → 深拷贝后写 `relations`）、物体级过滤（`filters.py`）、与 `coord_scale` 成比例的阈值常量（`constants.py`）。
- **语义**：`delta_uv = target - anchor`；`above` ⇔ 更小 `v`；无序对仅 **anchor `object_id` 字典序较小** 的一条有向边；IoU 过高 **或** 代表点过近丢弃；双轴显著且落入平局比丢弃；**无 NMS**。
- **校验**：同一 `ObjectV0` 同时含 bbox 与 point → **`ValueError`**。
- **测试**：`metadata/tests/test_enrich_relation2d.py`（几何、过滤、IoU/近心、对称、点模式、非变异、scale 缩放）。

## 文档与对外说明

- 已更新：`metadata/README.md`、`metadata/plans/2026-04-16_0300_metadata_next/test_plan.md`（实现勾选）、`metadata/docs/project_progress_zh.md`。
- **未改** `metadata/docs/config_yaml_zh.md`（首轮无 enrich YAML，与 plan 一致）。

## 自测

- `python -m pytest metadata/tests -q`
- `python -m unittest discover -s metadata/tests -p "test_*.py" -q`

## 与上一版差异

- **新增** enrich 包；**未改** CLI 默认行为。

## 迁移与回滚

- **回滚**：删除 `enrich/` 包与对应测试即可恢复；无 schema 破坏性变更。
