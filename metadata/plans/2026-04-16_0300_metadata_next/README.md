# 计划目录：`2026-04-16_0300_metadata_next`

**主题（已定方向）**：**2D 空间关系增强（relation enrichment）**——在 metadata v0 输出形态已明确的前提下，从「单图 + 多物体（描述 + **框或点二选一** grounding）」等**尚未完全固定的上游输入**生成或补全 **`ref_frame=image_plane`** 的 2D 关系；**设计重心为过滤与消歧策略**。**已定**：**不做 NMS**；**一框/一点对应一物体**；多 label 多几何则展开为多 `Object`。

**文档状态**

- `design.md`：**已定稿**（§7 收口：enrich 与 adapter 解耦、框点混用报错、首轮仅库+测、对称向/平局/IoU 规则写死）。
- `plan.md` / `test_plan.md`：**已编写**，可进入实现阶段。

**与规范的关系**：输出对齐 `metadata/docs/metadata_spec_v0_zh.md` §2.3、§4.1（`image_plane` 下原子 `predicate` 与 **复合 `components`** / 可选 2D `axis_signs`）；代码侧为 `relations: List[RelationV0]`，本阶段以 **写入 `predicate`/`components`/`axis_signs`/`source`/`evidence`** 为主，必要时在 `aux` 记录过滤日志。
