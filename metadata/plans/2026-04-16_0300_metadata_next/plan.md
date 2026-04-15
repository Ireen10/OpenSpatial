# 执行计划（Plan）：2D 关系增强（image_plane）

> **依据**：`design.md`（已定稿）。**首轮范围**：纯 Python **库 + 单测**；**不**新增 `openspatial-metadata` 子命令；enrich **与 adapter 解耦**。

---

## 交付物清单

- **文档**：本目录 `test_plan.md` 与实现同步勾选；`README.md` 指回 design；`metadata/README.md` 增加 **enrich 库入口** 一句（无新 CLI 时可不写 config_yaml）。
- **代码**：`metadata/src/openspatial_metadata/enrich/`（或等价单模块 `relation2d.py`）— **公开 API** 如 `enrich_relations_2d(metadata: MetadataV0, *, options: ...) -> MetadataV0`（签名以实现为准）；内部分拆 `geometry.py` / `filters.py` 仅当单文件过长。
- **配置**：物体级过滤等 **首轮以 dataclass + 默认值 + 可选参数** 为主；与 `design.md` §4.2 **写死**项（IoU/近中心/对称向/平局丢弃）为 **模块常量**。
- **样例/fixtures**：`metadata/tests/fixtures/` 下最小 JSON（或手写 `MetadataV0` dict）用于黄金向量与异常路径。

---

## 文档同步（与本变更一并交付）

- [ ] `metadata/docs/config_yaml_zh.md` — **首轮可勾选「无需更新」**（无 global enrich YAML）；若实现阶段引入 YAML 再改。
- [ ] `metadata/docs/metadata_spec_v0_zh.md` — **无需更新**（除非实现发现与 §4.1 字段不一致）。
- [ ] `metadata/README.md` — 增加 enrich **库用法**（import 路径 + 一行示例）。
- [ ] `metadata/plans/2026-04-16_0300_metadata_next/test_plan.md` — 随用例实现勾选。
- [ ] `metadata/docs/project_progress_zh.md` — **整轮结束**（自测 + `change_log.md`）后更新。
- [ ] 其他：**无**

---

## 任务拆解

### T1：几何与谓词核心

- **目标**：由两物体代表点 `(du, dv)` 判定单原子 `predicate` 或复合 `components` + 主 `predicate`；**image_plane** 下 `above` ⇔ 更小 `v`（y 向下）写死并加注释。
- **文件**：`enrich/relation2d.py`（或合并名）、常量模块（IoU 阈值、近中心阈值、平局带比率）。
- **完成条件**：`test_plan.md` 中 **UT-G1** 全部通过。

### T2：物体级过滤 + 代表点

- **目标**：`geom_valid`、边界、`min_area_*`（仅框）、`max_objects_per_sample` 等按 `design.md` §4.1；`rep_point()` 框中心 / 点坐标。
- **文件**：`enrich/filters.py` 或与 T1 同目录拆分。
- **完成条件**：**UT-F1** 通过；非法框/点从候选集中剔除且 `aux.enrich_2d.dropped_objects` 有记录。

### T3：关系对过滤 + 对称向 + 写回 metadata

- **目标**：全组合 → **无序对只保留 anchor `object_id` 字典序较小者 → target**；应用 IoU **或** 近中心写死丢弃；平局带内丢弃；对称对向不在第二层重复；写入 `relations` 与 `source`/`evidence`；填充 `aux.enrich_2d` 统计。
- **文件**：`enrich/relation2d.py` + `schema/metadata_v0.py` **仅当**需辅助方法（否则不动 schema）。
- **完成条件**：**UT-R1** 通过（**IT-1** 见 `test_plan.md`，有 fixture 后再纳入里程碑）。

### T4：入口 API 与防御性校验

- **目标**：`enrich_relations_2d(metadata)` 对 **同一 object 同时有 bbox 与 point** 抛 **`ValueError`**（与 design §2.2 一致）；文档字符串说明与 adapter 解耦。
- **文件**：`enrich/__init__.py` 导出公共 API。
- **完成条件**：**UT-X1** 通过。

### T5：收尾

- **目标**：`change_log.md`；`pytest metadata/tests -q` 全绿。
- **完成条件**：见 `test_plan.md` Gate。

---

## 里程碑与回滚

| 里程碑 | 内容 |
|--------|------|
| **M1** | T1 + T2 + UT-G1 + UT-F1 |
| **M2** | T3 + T4 + UT-R1 + UT-X1（+ 可选 IT-1） |
| **M3** | T5 + README + `project_progress_zh.md` |

- **回滚**：单 PR revert；enrich 为**新增模块**，不影响现有 CLI 默认路径。

---

## 残留疑问（实现前若仍不确定）

- **无阻塞项**：`design.md` §7 已全部收口。若数据侧出现「全点无框」与「全框」混合 sample，按现有规则分别走代表点逻辑即可。
