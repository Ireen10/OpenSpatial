# 计划目录：`2026-04-16_0300_metadata_next`

**主题（已定方向）**：**2D 空间关系增强（relation enrichment）**——在 metadata v0 输出形态已明确的前提下，从「单图 + 多物体（描述 + **框或点二选一** grounding）」等**尚未完全固定的上游输入**生成或补全 **`ref_frame=image_plane`** 的 2D 关系；**设计重心为过滤与消歧策略**。**已定**：**不做 NMS**；**一框/一点对应一物体**；多 label 多几何则展开为多 `Object`。

**文档状态**

- `design.md`：**已定一版可讨论稿**（待你确认未决问题后再锁 `plan.md` / `test_plan.md`）。
- `plan.md` / `test_plan.md`：骨架保留，**勿在 design 对齐前 deep 实现**。

**与规范的关系**：输出字段与语义对齐 `metadata/docs/metadata_spec_v0_zh.md` §4.1（Relation2D / image_plane）；当前代码里 Pydantic 为 `relations: List[RelationV0]`（`predicate` + `ref_frame` + 可选 `evidence`），本阶段以 **写入该列表 + `source`/`evidence`** 为主，必要时在 `aux` 记录过滤日志。
