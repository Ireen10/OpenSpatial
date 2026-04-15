# 计划目录：`2026-04-16_0300_metadata_next`

**状态**：已从 `metadata/plans/templates/` 拷贝文档骨架；**本轮主题、目标与非目标尚未定稿**，需与维护者在 `design.md` 上对齐后再写 `plan.md` / `test_plan.md`。

**建议下一步（候选，多选一或组合）**：

1. **GitHub Actions CI**：在 Linux 上跑 `pytest metadata/tests`（与 `project_progress_zh.md` 中 TODO 一致）。
2. **适配器管线**：CLI 在处理每条记录时调用已解析的 `adapter`（当前多为透传占位）。
3. **Parquet I/O**：读/写与 OpenSpatial 主仓约定的 Parquet 形态（依赖与路径边界需先定 design）。
4. **其它**：由你在讨论中指定。

定稿后请把本 README 中的「状态」改为已对齐，并在 `design.md` 首段写清正式标题（可与目录名 `topic` 部分一致）。
