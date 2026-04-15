# 测试方案（Test Plan）：2D 关系增强（image_plane）

> **依据**：`design.md`、`plan.md`。与 **Plan** 映射：`UT-G1`→T1，`UT-F1`→T2，`UT-R1`/`IT-1`→T3，`UT-X1`→T4。

---

## 测试范围

- **覆盖**：`ref_frame=image_plane` 下单/复合 `predicate` + `components`（复合时 `predicate`=水平腿）；物体级过滤；对称向（字典序 anchor）；IoU/近中心写死丢弃；`ValueError` 混用框点；`aux.enrich_2d` 基础字段。
- **不覆盖**：CLI 子命令、adapter 具体类、3D、NMS、YAML 全局配置（首轮无）。

---

## 单元测试

### UT-G1 几何与谓词（Plan T1）

| 编号 | 输入（两代表点相对位置） | 期望 |
|------|--------------------------|------|
| G1.1 | target 在 anchor 右侧（du 大、dv tie） | `predicate="right"`，`components` 省略或单元素与实现约定一致 |
| G1.2 | target 在 anchor 上方（dv 更小） | `predicate="above"` |
| G1.3 | 右下复合（du>0, dv>0 且两轴均过显著阈值） | `components=["right","below"]`，`predicate`=`components[0]` |
| G1.4 | 一轴在 `min_abs_delta_*` 以下 | 仅输出另一轴单原子 |
| G1.5 | 两轴均显著且 \|du\|≈\|dv\| | 仍输出复合，`predicate`=`components[0]` |

- **输入构造**：手写 `MetadataV0`（最小 `dataset`/`sample`/`objects`，两至三个 `ObjectV0`）。
- **断言点**：`predicate`/`components`/`ref_frame`/`source`/`evidence.delta_uv` 与手算一致。

### UT-F1 物体过滤（Plan T2）

- F1.1：面积 0 或越界框 → 不入关系候选、`dropped_objects` 含原因。
- F1.2：仅点物体，`geom_valid` 越界 uv → 丢弃。
- F1.3：`max_objects_per_sample` 截断后条数与顺序符合实现约定（面积降序等）。

### UT-R1 对级规则（Plan T3）

- R1.1：两框 IoU 超内定常量 → 该对无 relation，`dropped_relation_candidates` 含 `high_iou`。
- R1.2：两代表点距离小于内定常量 → `near_center`。
- R1.3：`A`/`B` 无序对只出现 **一条**有向 relation，且 anchor 为 `min(id_a,id_b)`（与实现一致即可，须在测试注释写死约定）。

### UT-X1 混用框点（Plan T4）

- X1.1：同一 `ObjectV0` 同时填 `bbox_xyxy_norm_1000` 与 `point_uv_norm_1000` → `enrich_relations_2d` 抛 `ValueError`。

---

## 集成测试

### IT-1 最小 JSON 管线（可选与 CLI 无关）

- **步骤**：从 fixture 读入 **已是 `MetadataV0` 兼容 dict**（或经现有 loader 若已有），调用 `enrich_relations_2d`，写回 JSON 再解析。
- **断言**：`relations` 条数与 golden 文件一致或集合相等；`aux.enrich_2d.stats` 非空。

（若首轮无 loader 路径，**可降级为仅 UT**；IT-1 标记为可选直至有 fixture 路径。）

---

## 质量门槛（Gate）

- `python -m pytest metadata/tests -q` 全通过（仓库根）。✅
- `python -m unittest discover -s metadata/tests -p "test_*.py" -q` 全通过（无 pytest 环境时）。✅

**失败定位**：对照 `design.md` §4.2 与实现常量；打印 `aux.enrich_2d`。

---

## 文档验收

- [x] `plan.md` 任务与实现一一对应。
- [x] `change_log.md` 已写（整轮末尾）。
