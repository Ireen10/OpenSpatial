# OpenSpatial Metadata 规范（v0，单视角）

本文给出一版**可立即落地**的 metadata 设计，用于从多种数据源（2D grounding / 3D 场景数据 / 人工标注）统一表达并生产空间关系 QA。该版本明确将 **2D（image_plane）** 与 **3D（egocentric）** 分开处理；其中 3D 方位关系允许来自**人工标注 label**，不强依赖可复算的几何证据。

> 约束：本文仅覆盖**单视角**（singleview），并与 OpenSpatial 当前以 Parquet 行为中心的工程形态兼容。

---

## 1. 目标与非目标

### 1.1 目标

- **统一字段**：能同时承载
  - 单实例 2D grounding（类别/指代表达 + bbox）
  - 多实例 2D grounding（同类多个 bbox，类别无法唯一指代）
  - 3D 场景派生数据（深度/分割/点云/3D box 等）
  - **人工标注数据**（指代描述 + 粗 bbox + 人工 3D 方位 label）
- **可扩展**：后续增加 `allocentric`（世界坐标/房间坐标）时不推翻字段。
- **可用于 QA 生产**：metadata 中要能支持生成：
  - 2D 图像平面方位关系 QA（left/right/up/down）
  - 3D egocentric 方位关系 QA（left/right/higher/lower/front/behind）

### 1.2 非目标（v0 不做）

- 不强制每条 3D 关系都能从几何数据**自动复算**（人工标注可以只提供 label）。
- 不要求处理多视角一致性与跨视角引用（v0 只单视角）。

---

## 2. 术语与坐标约定

### 2.1 Ref frame（参照系标签）

- **`image_plane`（2D）**：像素平面坐标。默认约定：\(x\) 向右增，\(y\) 向下增。
- **`egocentric`（3D）**：以相机为原点的 3D 参照系，语义上是“从相机视角理解空间方位”。
- **`allocentric`（预留）**：世界/场景固定参照（v0 预留字段，不定义计算方式）。

### 2.2 Egocentric 下的“扶正”定义（重要）

你当前的任务定义为：

- **前/后（front/behind）**：以“相机扶正”（俯仰角变为 0）后的**深度次序**定义。越靠近相机的越 `front`。
- **上/下（higher/lower）**：建议定义为重力意义的上/下（若无重力/姿态信息，可在 v0 中把该轴标为 `unknown` 或仅使用人工标注）。

因此 v0 推荐把 egocentric 3D 的方向基轴抽象为：

- `front_axis`: “depth order after de-pitch”
- `up_axis`: “gravity aligned” 或 “unknown”
- `right_axis`: 与 up/front 组成右手系（若有姿态信息）

> 工程提示：仅靠单张 RGB + 2D bbox 很难可靠推断 3D 方位；因此 v0 允许 3D 方位来自人工标注 label，并在 metadata 中记录来源与置信度。

---

## 3. 统一数据结构（建议存为 Parquet 的 JSON 列或拆成多列）

### 3.1 顶层：一个 sample（一行）

建议每行具备以下顶层字段：

- **`sample_id: str`**：全局唯一（推荐 `dataset_name/scene_or_image_id`）
- **`view_id: int`**：单视角固定为 `0`
- **`image: str | {"bytes": ...}`**
- **`objects: list[Object]`**
- **`queries: list[Query]`**（可为空）
- **`relations_2d: list[Relation2D]`**（可为空，可在线计算或离线标注）
- **`relations_3d: list[Relation3D]`**（可为空，可在线计算或人工标注）
- **`camera: CameraMeta | null`**（若要几何复算 3D，建议提供）
- **`depth: DepthMeta | null`**（同上）
- **`provenance: dict`**（可选：记录来源、版本、清洗规则）

### 3.2 `Object`（实例表）

每个对象建议至少包含：

- **`object_id: str`**：稳定主键（不要只用类别名）
- **`category: str`**：类别/粗标签（用于 prompt）
- **`grounding`**（可选）
  - `bbox_xyxy: [float,float,float,float] | null`
  - `mask_path: str | null`
  - `phrase: str | null`（若有指代描述）
- **`geometry`**（可选）
  - `center_xyz_cam: [float,float,float] | null`（若已知/可算）
  - `obb_world: [cx,cy,cz,xl,yl,zl,roll,pitch,yaw] | null`
  - `pointcloud_path: str | null`
- **`quality`**（建议）
  - `bbox_quality: "high"|"medium"|"low"|"unknown"`（你提到 bbox 不准时很关键）
  - `geometry_quality: "high"|"medium"|"low"|"unknown"`

> v0 关键：即便 bbox 不准，也应记录下来，并用 `bbox_quality="low"` 标注，避免后续把它当成可靠 2D 证据。

### 3.3 `Query`（指代/grounding 查询）

用于承载你提到的单实例/多实例 grounding 数据差异：

- **`query_id: str`**
- **`query_text: str`**：指代描述或类别名
- **`query_type`**：
  - `"single_instance_grounding"`
  - `"multi_instance_grounding"`
  - `"3d_grounding"`
  - `"human_annotated"`（人工标注也可归入）
- **`candidate_object_ids: list[str]`**：候选集合
- **`gold_object_id: str | null`**：若能唯一指向则填
- **`filters`**（建议）
  - `contains_spatial_terms: bool`
  - `spatial_terms: list[str]`

> 对单实例 grounding：建议通过 `candidate_object_ids` 长度=1 来**验证**“类别唯一”假设，而不是仅口头假设。

---

## 4. 空间关系结构（2D / 3D 分开）

### 4.1 `Relation2D`（image_plane）

**用途**：图像平面内上下左右。

字段建议：

- `anchor_id: str`
- `target_id: str`
- `predicate: "left_of"|"right_of"|"above"|"below"`
- `ref_frame: "image_plane"`
- `evidence`（建议）
  - `anchor_point_uv: [u,v]`（bbox center 或 mask centroid）
  - `target_point_uv: [u,v]`
  - `delta_uv: [du,dv]`
- `score: float | null`
- `source: "computed"|"human_annotated"|"imported"`

### 4.2 `Relation3D`（egocentric）

**用途**：相机 egocentric 3D 方位（与你的定义 B 对齐）。

字段建议：

- `anchor_id: str`
- `target_id: str`
- `ref_frame: "egocentric"`（v0 先不引入 allocentric）

#### 4.2.1 原子谓词（可选其一表示方式）

**方式 A：轴符号（推荐，天然支持复合方位）**

- `axis_signs`：以 `right/up/front` 语义表达复合方向
  - `right: -1|0|+1`（-1=left, +1=right）
  - `up: -1|0|+1`（-1=lower, +1=higher）
  - `front: -1|0|+1`（-1=behind, +1=front；按“扶正后深度次序”定义）

并可选存：
- `components: list[str]`：如 `["left","front","higher"]`（从 axis_signs 派生）

**方式 B：显式复合谓词**

- `predicate: "left_front_higher" | ...`
- `components: ["left","front","higher"]`

> v0 推荐方式 A：`axis_signs` 让标签空间可控，不会因组合爆炸难以维护。

#### 4.2.2 证据与来源

因为 v0 允许 3D 关系来自人工标注，建议显式记录：

- `source: "human_annotated"|"computed_from_geometry"|"imported"`
- `score: float | null`
- `evidence`（强烈建议）
  - `anchor_point_xyz_cam: [x,y,z] | null`
  - `target_point_xyz_cam: [x,y,z] | null`
  - `delta_xyz_cam: [dx,dy,dz] | null`
  - `front_order`（可选）：`"target_closer"|"anchor_closer"|"tie"|"unknown"`
  - `de_pitch_method`（可选）：如 `"use_pose_gravity"` / `"unknown"`

---

## 5. 与 OpenSpatial 工程的映射建议

### 5.1 存储形态

OpenSpatial 当前主路径是 **Parquet 行**。v0 有两种落地方式：

- **方式 1（最小侵入）**：在现有 Parquet 中新增 JSON 列：
  - `objects_json`、`queries_json`、`relations_2d_json`、`relations_3d_json`
- **方式 2（更可直接用）**：拆成若干列并复用工程既有列名：
  - `obj_tags` ≈ objects.category
  - `bboxes_2d` / `masks` / `pointclouds` / `bboxes_3d_world_coords`
  - 再额外新增：`object_ids`、`queries`、`relations_2d`、`relations_3d`

若短期目标是用现有 annotation 框架快速迭代，建议采用 **方式 2**，因为 `SceneGraph` 已能消费一批标准列。

### 5.2 2D 与 3D 任务分开跑

- **2D 关系 QA**：只依赖 `image + bbox/mask`，可以直接由 metadata 计算 `relations_2d` 或在生成 QA 时在线计算。
- **3D 关系 QA**：
  - 若来自人工标注：可直接消费 `relations_3d` 产 QA（不依赖深度/点云）
  - 若要几何复算：需要 `depth/intrinsic/(pose)` 或 `center_xyz_cam/pointcloud/obb` 等字段

---

## 6. v0 样例（示意）

```json
{
  "sample_id": "human_anno/img_000123",
  "view_id": 0,
  "image": "data/images/img_000123.png",
  "objects": [
    {
      "object_id": "chair#0",
      "category": "chair",
      "grounding": {"bbox_xyxy": [120.5, 210.0, 260.0, 420.0], "phrase": "the wooden chair"},
      "quality": {"bbox_quality": "low", "geometry_quality": "unknown"}
    },
    {
      "object_id": "table#0",
      "category": "table",
      "grounding": {"bbox_xyxy": [300.0, 240.0, 520.0, 460.0], "phrase": "the dining table"},
      "quality": {"bbox_quality": "low", "geometry_quality": "unknown"}
    }
  ],
  "queries": [
    {
      "query_id": "q0",
      "query_text": "the wooden chair",
      "query_type": "human_annotated",
      "candidate_object_ids": ["chair#0"],
      "gold_object_id": "chair#0",
      "filters": {"contains_spatial_terms": false, "spatial_terms": []}
    }
  ],
  "relations_3d": [
    {
      "anchor_id": "table#0",
      "target_id": "chair#0",
      "ref_frame": "egocentric",
      "axis_signs": {"right": -1, "up": 0, "front": +1},
      "components": ["left", "front"],
      "source": "human_annotated",
      "score": 1.0,
      "evidence": {"front_order": "target_closer", "de_pitch_method": "unknown"}
    }
  ]
}
```

---

## 7. 后续（v1）建议

- 增加 `allocentric`：当具备 world 坐标与重力对齐时，可定义场景固定方位（如 room north）。
- 明确 `de_pitch_method`：若具备 `pose` 且世界系 Z-up，可给出稳定的 de-pitch；否则 3D 方位仅使用人工标注或弱监督。
- 引入阈值与不确定性：对 `axis_signs` 的 0（tie/unknown）统一规范，并用 `score` 过滤低置信样本。

