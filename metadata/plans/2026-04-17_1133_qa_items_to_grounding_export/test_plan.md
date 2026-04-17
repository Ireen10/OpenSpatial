# 测试计划（Test Plan）

映射 `plan.md` 任务；实现前对齐本表，实现后逐项勾选。

## 任务 1：标注阶段无图像 bytes

| ID | 对应 plan | 测试内容 | 预期 |
|----|-----------|----------|------|
| T1a | 任务 1 | `spatial_relation_2d` 产出的行 dict **无** `QA_images` 键或值为空（按实现约定二选一，与代码一致） | 单测或现有 task 测试更新后通过 |
| T1b | 任务 1 | `demo_2d_spatial_relation.yaml` 中 `keep_data_columns` 不含 `QA_images`（若仍列出则失败） | 配置审查或 grep |
| T1c | 任务 1 | `save_annotation_qa_metadata` 默认列无 `QA_images` | 单元测试或集成读配置 |

## 任务 2：`visual_group_key` 与分组

| ID | 对应 plan | 测试内容 | 预期 |
|----|-----------|----------|------|
| T2a | 任务 2 | `n_marked_boxes == 0`（或等价）→ key 为 `original` | `pytest` 纯函数 |
| T2b | 任务 2 | 两条 QA，`marked_roles`/`mark_colors`/`n_marked_boxes` 相同 → 同组 | 单测 |
| T2c | 任务 2 | 两条 QA，颜色或角色不同 → 不同组 | 单测 |
| T2d | 任务 2 | 同组内顺序与 `qa_items` 列表顺序一致 | 单测 |

## 任务 3：延后重绘与 tar + tarinfo

| ID | 对应 plan | 测试内容 | 预期 |
|----|-----------|----------|------|
| T3a | 任务 3 | 提供最小 `MetadataV0` + 本地小图 + `objects` bbox；需框组能生成非空图像并写入 **`images/part_000000.tar`** | `pytest` + `tmp_path` |
| T3b | 任务 3 | 同次导出写出 **`images/part_000000_tarinfo.json`**；每个键为 tar 内 `relative_path`，值含 **`offset_data` / `size` / `sparse`**（`sparse is None`） | `pytest` |
| T3c | 任务 3 | JSONL 中 `image.relative_path` 在 tarinfo 中存在且与 tar 内成员一致 | `pytest` |
| T3d | 任务 3 | `anchor_id` 在 `objects` 中缺失 bbox → 与 design 一致（跳过或 raise，与实现文档一致） | 单测 |

## 任务 4：JSONL 行结构

| ID | 对应 plan | 测试内容 | 预期 |
|----|-----------|----------|------|
| T4a | 任务 4 | 单轮：`meta_prompt==[""]`，`data` 长度 2，首轮 user 的 `content` 以 image 开头、后为 text | `pytest` |
| T4b | 任务 4 | 多轮：同组两条 QA → `data` 含 4 条消息，仅第一条 user 含 image | `pytest` |
| T4c | 任务 4 | `id` 为 `""` | 断言 |

## 任务 5：CLI / E2E（目录形态验收）

| ID | 对应 plan | 测试内容 | 预期 |
|----|-----------|----------|------|
| T5a | 任务 5 | 在 `output_root` 下存在 **`images/part_000000.tar`**、**`images/part_000000_tarinfo.json`**、**`jsonl/part_000000.jsonl`** | E2E / API |
| T5b | 任务 5 | 若 CLI 推迟：仅 **库 API** 级 E2E，但 **目录与三种文件仍须齐全** | 与 plan 收束检查一致 |

## 回归

| ID | 测试内容 | 预期 |
|----|----------|------|
| R1 | `metadata/tests/test_qa_items_schema.py` | 通过 |
| R2 | `metadata/tests/test_metadata_relation_id.py`（若仍适用） | 通过 |
| R3 | 与 `spatial_relation_2d` 相关的 `metadata/tests/test_spatial_relation_2d_annotation_task.py` | 更新 fixture 期望后通过 |

## 执行命令（建议）

```text
cd <repo>
python -m pytest metadata/tests/test_qa_items_schema.py metadata/tests/test_export_*.py -q
python -m pytest metadata/tests/test_spatial_relation_2d_annotation_task.py -q
```

（`test_export_*.py` 为实现后新增测试文件名，若不同请替换。）
