# EmbodiedScan / Omni3D 数据结构基线（用于 MetadataV0 转换策略）

本文档用于沉淀后续 3D 数据转换策略的“输入契约”，重点回答：

- EmbodiedScan 系列与 Omni3D 系列各自包含哪些子数据集；
- 两类上游数据结构（官方/仓内）在字段层面的形态；
- 如何映射到当前 `MetadataV0`；
- 当前 adapter 覆盖了什么、缺了什么（先记录，不在本文修改 adapter）；
- 点云能力边界（原生点云 / 可重建 / 仅 3D 框）。

> 口径说明：本页以当前 OpenSpatial 仓内实现与官方公开说明为准。  
> 本页是“结构基线文档”，不是“实现完成度承诺”。

---

## 1. 数据集系列与子数据集清单

### 1.1 EmbodiedScan 系列（OpenSpatial 当前预处理口径）

在 `OpenSpatial/data_preprocessing/embodiedscan` 的预处理实现中，明确支持四个来源数据集：

- `ScanNet`
- `3RScan`
- `Matterport3D`
- `ARKitScenes`

并按 `extract -> merge -> export -> validate` 四步生成 OpenSpatial Parquet。

参考：

- `data_preprocessing/embodiedscan/README.md`
- `assets/quick_start.md`

### 1.2 Omni3D 系列（官方统一基准口径）

Omni3D 官方将下列数据集统一到同一坐标系和标注格式：

- `KITTI`
- `nuScenes`
- `Objectron`
- `SUN RGB-D`
- `ARKitScenes`
- `Hypersim`

参考：

- [facebookresearch/omni3d DATA.md](https://raw.githubusercontent.com/facebookresearch/omni3d/main/DATA.md)

---

## 2. 官方输入结构（上游侧）

## 2.1 EmbodiedScan（仓内可见入口）

OpenSpatial 当前接入 EmbodiedScan 的直接入口是预处理包文档与导出数据，而非官方完整 Python 数据类定义。  
在仓内已确认的结构要点：

- 预处理输入包含：RGB、depth、pose、intrinsic、axis align、3D OBB 与标签；
- 标注文件为 `embodiedscan_infos_{train|val|test}.pkl`；
- 预处理导出为 per-image/per-scene JSONL 与 Parquet。

`extract` 后 per-image 记录（OpenSpatial 预处理导出口径）核心字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | `str` | 唯一记录 id |
| `dataset` | `str` | 来源数据集名 |
| `scene_id` | `str` | 场景 id |
| `image` | `str` | RGB 路径 |
| `depth_map` | `str` | 深度图路径 |
| `pose` | `str` | 4x4 外参路径 |
| `intrinsic` | `str` | 4x4 内参路径 |
| `depth_scale` | `int` | 深度缩放系数 |
| `bboxes_3d_world_coords` | `list[list[float]]` | 世界系 3D OBB（9DoF） |
| `obj_tags` | `list[str]` | 对象语义标签 |
| `axis_align_matrix` | `str` | 对齐矩阵路径 |

参考：

- `data_preprocessing/embodiedscan/README.md`

## 2.2 Omni3D（官方 COCO-like JSON）

Omni3D 官方标注文件是 COCO-like JSON：

- 顶层：`info` / `images` / `categories` / `annotations`
- `images` 常见字段：`id`, `width`, `height`, `file_path`, `K`, `src_90_rotate`, `src_flagged`
- `annotations` 常见字段：`id`, `image_id`, `category_id`, `category_name`, `valid3D`, `bbox2D_*`, `bbox3D_cam`, `center_cam`, `dimensions`, `R_cam` 等

坐标系约定：`+x right, +y down, +z toward screen`。

参考：

- [facebookresearch/omni3d DATA.md](https://raw.githubusercontent.com/facebookresearch/omni3d/main/DATA.md)

---

## 3. MetadataV0 目标结构（落地侧）

当前代码中 `MetadataV0` 的核心结构：

- 顶层：`dataset`, `sample`, `camera`, `objects`, `queries`, `relations`, `qa_items`, `aux`
- 对象：`object_id`, `category`, `phrase`, `bbox_xyxy_norm_1000`, `point_uv_norm_1000`, `mask_path`, `quality`
- 关系：`anchor_id`, `target_id`, `predicate`, `ref_frame`, `components`, `axis_signs`, `source`, `score`, `evidence`, `relation_id(可自动补)`

参考：

- `metadata/src/openspatial_metadata/schema/metadata_v0.py`

---

## 4. adapter 输入字段字典（当前实现）

## 4.1 EmbodiedScan3DAdapter（`embodiedscan_3d.py`）

### 顶层字段解析

| 目标字段 | 输入别名（按优先顺序） | 默认值/规则 |
|---|---|---|
| `sample.sample_id` | `sample_id` / `id` / `scene_id` | `"unknown"` |
| `sample.image.path` | `image_path` / `img_path` / `image` / `image_file` | `""` |
| `sample.image.width` | `width` | 仅 `int` 保留，否则 `None` |
| `sample.image.height` | `height` | 仅 `int` 保留，否则 `None` |
| `camera` | `camera` | 直接透传 |

### 对象列表容器与对象字段

对象容器别名：`objects` / `instances` / `annotations`（取第一个命中的 list）。

| 目标对象字段 | 输入别名 | 默认值/规则 |
|---|---|---|
| `object_id` | `object_id` / `id` / `instance_id` | fallback: `obj#{idx}` |
| `category` | `category` / `label` / `category_name` | `""` |
| `phrase` | `phrase` / `text` / `description` | 空串转 `None` |
| `center_xyz_cam` | `center_xyz_cam` / `center_3d` / `centroid` / `centroid_xyz_cam` | 需可转 `float[3]` |
| `bbox_xyxy_norm_1000` | `bbox_xyxy_norm_1000` | 需长度为 4，再转 int |

### 关系列表容器与关系字段

关系容器别名：`relations_3d` / `relations3d` / `spatial_relations_3d`。

| 目标关系字段 | 输入别名 | 默认值/规则 |
|---|---|---|
| `anchor_id` | `anchor_id` / `subject_id` / `src` | 必须非空 |
| `target_id` | `target_id` / `object_id` / `dst` | 必须非空 |
| `predicate` | `predicate` / `relation` | `"front"` |
| `ref_frame` | 固定 | `"egocentric"` |
| `source` | `source` | `"annotated_3d"` |
| `components` | `components` | list 时保留 |
| `axis_signs` | `axis_signs` | 仅保留 `right/above/front`，值转 int |
| `evidence` | `evidence` | dict 时拷贝 |

---

## 4.2 Omni3DAdapter（`omni3d.py`）

### 顶层字段解析

| 目标字段 | 输入别名（按优先顺序） | 默认值/规则 |
|---|---|---|
| `sample.sample_id` | `sample_id` / `id` / `image_id` | `"unknown"` |
| `sample.image.path` | `image_path` / `img_path` / `file_name` | `""` |
| `sample.image.width` | `width` | 仅 `int` 保留 |
| `sample.image.height` | `height` | 仅 `int` 保留 |
| `camera` | `camera` | 透传 |

### 对象列表容器与对象字段

对象容器别名：`objects` / `instances` / `annotations`。

| 目标对象字段 | 输入别名 | 默认值/规则 |
|---|---|---|
| `object_id` | `object_id` / `id` / `annotation_id` | fallback: `obj#{idx}` |
| `category` | `category` / `category_name` / `label` | `""` |
| `phrase` | `phrase` / `description` / `text` | 空串转 `None` |
| `center_xyz_cam` | `center_xyz_cam` / `center_3d` / `center_cam` / `xyz_cam` | 需可转 `float[3]` |
| `bbox_xyxy_norm_1000` | `bbox_xyxy_norm_1000` | 需长度为 4，再转 int |

### 关系字段

当前实现固定输出：

- `relations = []`

即 Omni3DAdapter 当前仅做对象标准化；3D 关系依赖后续 `enrich.relations_3d=true` 计算。

---

## 5. 映射矩阵：官方输入字段 -> MetadataV0 -> 当前 adapter 覆盖状态

说明：

- `已映射`：当前 adapter 已落地；
- `透传`：不做结构化，仅原样挂载；
- `未映射`：当前未进入 `MetadataV0` 目标字段。

| 官方输入字段（示例） | MetadataV0 目标 | EmbodiedScan3DAdapter | Omni3DAdapter |
|---|---|---|---|
| `sample_id` / `id` / `scene_id` / `image_id` | `sample.sample_id` | 已映射 | 已映射 |
| `image_path` / `file_name` | `sample.image.path` | 已映射 | 已映射 |
| `width` / `height` | `sample.image.width/height` | 已映射 | 已映射 |
| 相机参数（如 `K`, `cam2img`, `pose`, `cam2global`） | `camera` | 透传（仅 `camera` 键） | 透传（仅 `camera` 键） |
| `objects/instances/annotations` | `objects[*]` | 已映射（子集） | 已映射（子集） |
| `bbox2D_*` | `objects[*].bbox_xyxy_norm_1000` | 仅支持同名字段 | 仅支持同名字段 |
| `bbox3D_cam` / `center_cam` / `bbox_3d` | `objects[*].center_xyz_cam` 或扩展字段 | 部分映射（中心点别名） | 部分映射（中心点别名） |
| 关系列表（`relations_3d` 等） | `relations[*]` | 已映射（子集） | 未映射 |
| `components`, `axis_signs`, `evidence` | `relations[*].*` | 已映射（有过滤） | 未映射 |
| 点云路径 / 点云对象 | `objects[*].pointcloud_path`（通过 extra） | 未映射 | 未映射 |
| 分割 mask 路径 | `objects[*].mask_path` | 未映射 | 未映射 |
| 2D 点标注 | `objects[*].point_uv_norm_1000` | 未映射 | 未映射 |

---

## 6. 当前未覆盖但应纳入后续转换策略设计的字段

以下字段在 schema 或上游中有价值，但当前 adapter 未系统接入：

1. 几何/相机复算关键字段  
   - `cam2img`, `cam2global`, `pose`, `intrinsic`, `axis_align_matrix`, `depth_map`, `depth_scale`
2. 点云与几何载体  
   - 对象级 `pointcloud_path`，scene 级 mesh/point cloud 路径
3. 关系质量字段  
   - `score`, 细粒度 `evidence`（来源、阈值、中间量）
4. 对象质量字段  
   - `mask_path`, `point_uv_norm_1000`, `quality`
5. Omni3D 关系接入  
   - 若上游有弱关系或可导关系，应明确是“adapter 直读”还是“统一交给 enrich”。

---

## 7. 点云能力矩阵（策略设计前置）

| 数据来源 | 是否原生提供点云/mesh | 是否可由 depth+pose 重建点云 | 是否仅有 3D 框可用 |
|---|---|---|---|
| ScanNet（EmbodiedScan 来源） | 有 mesh（可导点云） | 是 | 否 |
| 3RScan（EmbodiedScan 来源） | 有重建数据（可导点云） | 是 | 否 |
| Matterport3D（EmbodiedScan 来源） | 有 region mesh | 是 | 否 |
| ARKitScenes（EmbodiedScan 来源） | 具备深度与相机信息（可重建） | 是 | 部分场景可能缺少统一点云导出 |
| Omni3D（统一标注 JSON） | 通常不直接附点云 | 取决于底层子数据集是否有 depth/pose | 常见为“RGB+相机+3D框”口径 |

备注：

- OpenSpatial 外层主流程已实现 depth 反投影生成对象点云 `.pcd`，说明“可重建点云”路径是可执行的。

---

## 8. OpenSpatial 外层流程中的点云相关阶段摘要（不复用但可借鉴）

外层引擎：`run.py` + `pipeline/base_pipeline.py`，通过 `depends_on` 串联 `data.parquet`。

点云相关关键任务：

1. `task/filter/3dbox_filter.py`  
   - 使用 depth 反投影得到场景点云；
   - 先做 3D 框投影 2D 合理性检查，再做 3D 框内部点云一致性检查；
   - 输出有效对象 mask（路径）。
2. `task/scene_fusion/depth_back_projection.py`  
   - 基于 `depth_map + intrinsic + masks` 回投对象点云；
   - 对点云做统计离群点去除；
   - 输出对象级 `.pcd` 路径列表到 `pointclouds`。
3. 部分标注任务使用点云作为几何证据输入（例如 scene graph / multiview 任务）。

借鉴点（后续策略可复用思想）：

- 将“几何有效性检查”和“关系生成”分层；
- 对点云生成做质量门槛（最少点数、空点云剔除）；
- 用文件路径而非大数组落表，降低 Parquet 膨胀。

---

## 9. 后续“点云计算数据转换策略”采访输入清单

本节用于下一轮采访，不涉及实现改动。

### 9.1 必选决策

1. 点云来源优先级  
   - A: 原生点云/mesh 优先，缺失时回退 depth 重建  
   - B: 统一全部 depth 重建（口径一致）
2. 关系计算坐标系  
   - A: 统一 camera-egocentric  
   - B: world 计算后再投影到 egocentric 表达
3. 关系来源融合策略  
   - A: annotated 与 computed 并存，冲突只记告警  
   - B: 指定优先源并做覆盖

### 9.2 建议量化门槛（首版）

- 覆盖率：有可用 3D 几何的对象对占比；
- 冲突率：`annotated` vs `computed` 组件不一致占比；
- 异常率：空点云、超小点云、无效外参/内参样本占比；
- QA 可用率：生成 `spatial_relation_3d` 样本占比。

### 9.3 输出接口约束（建议先定）

- `relations[*].source` 仅使用：`annotated_3d` / `computed_3d`；
- `axis_signs` 固定键：`right/above/front`；
- `evidence` 最小键：`geometry_source`, `delta_xyz_cam`, `thresholds`, `quality_flags`；
- `aux` 存统计摘要，不存超大中间数组。

---

## 10. 与实现边界的关系

本页只定义“结构与策略输入基线”，当前不做：

- adapter 行为修改；
- 新增字段回填实现；
- 配置默认值调整；
- 训练导出逻辑变更。

这些改动将放到后续“点云计算数据转换策略”设计与实施阶段处理。

