# Metadata（v0）团队 Wiki 版：单视角空间关系归档（JSON）

本文是面向团队 Wiki 的 **Metadata v0** 说明页，目标是让数据/算法/标注/评测同学能用同一份结构进行**归档、检索、转换与 QA 生产**。

- **适用范围**：单视角（singleview）图像样本
- **归档格式**：每个 sample 一条 JSON（或 JSON Lines），字段见下文
- **标签策略**：方位标签（`left/right/above/below/front/behind`）统一；通过 `ref_frame` 消歧；QA 生产时再映射到自然语言表述

---

## 1. 设计目标

- **统一表达**：兼容 2D grounding、3D 场景派生数据、人工标注的 3D 方位标签等不同来源。
- **可定位 object**：任何关系/查询都必须能稳定指向某个 `object_id`（避免 “chair” 在图中多个实例时的歧义）。
- **可扩展**：未来支持 `allocentric`（场景固定参照系）时，不改变 v0 的主结构。
- **工程可用**：能方便地映射到 OpenSpatial 的 Parquet 行（`image/obj_tags/bboxes_2d/...`）或作为旁路 JSON 归档使用。

---

## 2. 坐标系与参照系约定

### 2.1 图像平面（`ref_frame = image_plane`）

- 像素坐标：\(x\) 向右增，\(y\) 向下增
- `above/below` 在该参照系下表示**图像平面上/下**

### 2.2 相机自我中心（`ref_frame = egocentric`）

v0 对 egocentric 采用以下任务定义：

- **前/后（front/behind）**：相机“扶正”（俯仰角归零）后的**深度次序**。越靠近相机的越 `front`。
- **上/下（above/below）**：建议对应**重力意义**的上/下；若样本缺少重力/姿态信息，可仅保留人工标注 label，或把该轴标为 unknown。

> 说明：2D 与 3D 的 `above/below` **不在标签层拆分**；依靠 `ref_frame` 区分几何含义，QA 生产时再把它映射为“图像上方”或“高度更高”等自然语言。

---

## 3. JSON 归档格式（顶层结构）

一个 sample 的 JSON 顶层结构如下（字段详见第 4 节数据字典）：

```json
{
  "dataset": { "...": "..." },
  "sample": { "...": "..." },
  "camera": null,
  "objects": [],
  "relations": [],
  "aux": {}
}
```

### 3.0 顶层字段总览（必选/可选）

| 模块 | 必选 | 用途 | 常见来源 |
|---|---:|---|---|
| `dataset` | 是 | 数据集标识（名称/版本/split），用于归档与追溯 | 数据集配置、导出脚本 |
| `sample` | 是 | 样本基本信息与图像定位（`sample_id` / 路径 / 尺寸等） | 原始数据索引、文件系统 |
| `camera` | 否 | 3D 几何复算所需的相机参数与深度；缺失时仍可归档人工 3D 标签 | 3D 场景数据、SfM/SLAM、深度估计 |
| `objects` | 是 | 实例表：为 grounding、关系、QA 提供稳定的 `object_id` | 检测/分割/标注/3D 实例 |
| `relations` | 否 | 关系标签（2D/3D 统一 label + `ref_frame` 消歧） | 人工标注、规则计算、外部导入 |
| `aux` | 否（建议保留为空 `{}`） | 预留扩展区：审核信息、阈值版本、调试缓存等 | 任意（不应影响主流程） |

### 3.1 模块划分

- **`dataset`**：数据集标识信息（来源、版本、split 等）
- **`sample`**：图像与样本基础信息（id、view、文件路径、尺寸等）
- **`camera`**：相机内外参（可为 `null`）
- **`objects`**：目标/实例属性列表（用于定位 object）
- **`relations`**：关系列表（2D/3D 统一标签 + ref_frame 消歧）
- **`aux`**：辅助信息（非必选，先预留）

---

## 4. 数据字典（字段名 / 类型 / 说明 / 示例）

### 4.1 `dataset`（数据集标识信息）

| 字段名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `dataset.name` | `string` | 数据集名称或代号 | `"cvbench"` |
| `dataset.version` | `string` | 数据集版本 | `"v1.0"` |
| `dataset.split` | `string` | split 标识 | `"train"` |
| `dataset.license` | `string?` | 可选：协议 | `"CC-BY-4.0"` |

### 4.2 `sample`（图像基本信息）

| 字段名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `sample.sample_id` | `string` | 全局唯一 id（推荐 `dataset/image_id`） | `"cvbench/img_000123"` |
| `sample.view_id` | `int` | 单视角固定 `0`（为多视角预留） | `0` |
| `sample.image.path` | `string` | 图像路径（推荐相对路径） | `"images/img_000123.png"` |
| `sample.image.bytes` | `string?` | 可选：base64 编码的 bytes（若不使用 path） | `null` |
| `sample.image.width` | `int?` | 可选：宽 | `640` |
| `sample.image.height` | `int?` | 可选：高 | `480` |
| `sample.image.coord_space` | `string?` | 坐标空间标识（推荐） | `"norm_0_999"` |
| `sample.image.coord_scale` | `int?` | 坐标 scale（推荐） | `1000` |

### 4.3 `camera`（相机内外参，可为 None）

> 若数据源无法提供几何复算能力，`camera` 允许为 `null`。只要关系来自人工标注或外部标签，仍可归档与产 QA。

| 字段名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `camera` | `object|null` | 相机模块整体 | `null` |
| `camera.intrinsic_4x4` | `number[4][4]?` | 可选：4×4 内参矩阵 | `[[...],[...],[...],[...]]` |
| `camera.pose_c2w_4x4` | `number[4][4]?` | 可选：camera-to-world 外参 | `[[...],[...],[...],[...]]` |
| `camera.coord_convention` | `string?` | 坐标约定（固定值） | `"x_right_y_down_z_forward"` |
| `camera.depth_map.path` | `string?` | 深度图路径 | `"depth/img_000123.png"` |
| `camera.depth_map.scale` | `number?` | 深度 scale | `1000` |
| `camera.depth_map.is_metric` | `bool?` | 是否米制深度 | `true` |

### 4.4 `objects`（目标属性列表，用于定位 object）

`objects` 是数组，每个元素为一个实例对象：

| 字段名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `objects[].object_id` | `string` | 实例主键（稳定、唯一） | `"chair#0"` |
| `objects[].category` | `string` | 类别名 | `"chair"` |
| `objects[].phrase` | `string?` | 指代描述（若有） | `"the wooden chair"` |
| `objects[].bbox_xyxy_norm_1000` | `int[4]?` | 2D bbox（归一化到 `[0,1000)` 的整数，xyxy） | `[120,210,260,420]` |
| `objects[].point_uv_norm_1000` | `int[2]?` | 2D 点（归一化到 `[0,1000)` 的整数，uv） | `[188,315]` |
| `objects[].mask_path` | `string?` | mask 路径 | `"masks/chair_0.png"` |
| `objects[].center_xyz_cam` | `number[3]?` | 可选：相机坐标系 3D 代表点 | `[0.3, -0.1, 2.4]` |
| `objects[].obb_world` | `number[9]?` | 可选：3D OBB（world） | `[cx,cy,cz,xl,yl,zl,roll,pitch,yaw]` |
| `objects[].quality.bbox` | `string?` | bbox 质量 | `"low"` |
| `objects[].quality.geometry` | `string?` | 几何质量 | `"unknown"` |

#### 4.4.1 从 `{label, boxes, points, count}` 展开 objects（规则）

当上游一条 grounding 记录包含同时包含 `boxes` 与 `points` 时，推荐按以下规则展开：

- 设 \(n_b=len(boxes)\)，\(n_p=len(points)\)
- 若 \(n_b>0\) 且 \(n_p>0\) 且 \(n_b==n_p\)：按 index 配对，展开 \(n_b\) 个 object，每个 object 同时填 `bbox_xyxy_norm_1000` 与 `point_uv_norm_1000`
- 若仅 `boxes` 非空：展开 \(n_b\) 个 object，仅填 `bbox_xyxy_norm_1000`
- 若仅 `points` 非空：展开 \(n_p\) 个 object，仅填 `point_uv_norm_1000`
- 若 `boxes` 与 `points` 都非空但长度不一致：v0 建议拆成两条 query（同 label，不同 query_id 后缀）分别管理 boxes 与 points，并在 `aux` 中记录告警，避免强行错配

同时建议校验：`count` 应与当前采用的列表长度一致（配对时 `count==n_b==n_p`）。

### 4.5 `relations`（关系列表）

`relations` 是数组，每条关系描述一对 objects 的方位关系（2D/3D 都在这里，靠 `ref_frame` 区分）。

| 字段名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `relations[].anchor_id` | `string` | anchor 的 `object_id` | `"table#0"` |
| `relations[].target_id` | `string` | target 的 `object_id` | `"chair#0"` |
| `relations[].predicate` | `string` | 方位标签（统一标签集） | `"front"` |
| `relations[].ref_frame` | `string` | `"image_plane"` \| `"egocentric"` \| `"allocentric"` | `"egocentric"` |
| `relations[].components` | `string[]?` | 可选：复合方位分量 | `["left","front","above"]` |
| `relations[].axis_signs` | `object?` | 可选：复合方位的离散轴符号（推荐） | `{"right":-1,"up":0,"front":1}` |
| `relations[].source` | `string` | `"huashan_annotated"` \| `"computed"` \| `"imported"` | `"huashan_annotated"` |
| `relations[].score` | `number?` | 可选：置信度 0~1 | `1.0` |
| `relations[].evidence` | `object?` | 可选：证据（点/差值/方法） | `{...}` |

#### 4.5.1 `axis_signs`（推荐的复合方位表达）

当需要表达“左前上 / 右后下”等复合方位时，推荐使用：

- `axis_signs.right ∈ {-1,0,+1}`：-1=left，+1=right
- `axis_signs.up ∈ {-1,0,+1}`：-1=below，+1=above
- `axis_signs.front ∈ {-1,0,+1}`：-1=behind，+1=front（egocentric 下按“扶正后深度次序”）

并可派生：

- `components`: 例如 `{"right":-1,"front":+1}` → `["left","front"]`

### 4.6 `aux`（辅助信息，预留）

`aux` 用于承载不确定但可能有用的信息，建议先保留为空对象 `{}`，不要在 v0 强制结构。

可能的候选包括：
- 标注者信息、审核信息
- 关系判定阈值、版本
- 自然语言 verbalization 结果缓存（不推荐做 v0 必选）

---

## 5. 自然语言映射（QA 生产时使用）

v0 只规定 **标签** 与 **参照系**；具体 QA 文本由映射函数决定：

- `(predicate="above", ref_frame="image_plane")` → “在图像中位于……上方”
- `(predicate="above", ref_frame="egocentric")` → “在高度上更高 / 位于……上方（以重力为准）”
- `(predicate="front", ref_frame="egocentric")` → “更靠近相机 / 更在前方（相机扶正后深度更小）”

---

## 6. Metadata 更新与增强（Enrichment，记录）

为便于后续持续“刷”QA 数据，metadata 通常会经历从 **raw → enriched → QA** 的多阶段演进。这里先记录推荐做法，细节（是否在 QA 阶段回写、如何做版本管理等）后续再讨论定稿。

### 6.1 概念：raw 与 enriched

- **raw metadata**：只保证样本可定位与可追溯（`dataset/sample/objects` 为主），以及外部/人工已给定的关系（若有）。
- **enriched metadata**：在 raw 基础上新增或补全派生信息，典型包括：
  - 由 grounding / 几何规则计算得到的 `relations`
  - 由 `axis_signs` 派生的 `components`
  - 质量标记、过滤标记（如指代描述是否含空间词）

### 6.2 关系的来源标记（必须）

当同一份 metadata 中同时存在“人工标注关系”和“计算得到的关系”时，必须用 `relations[].source` 区分：

- **`huashan_annotated`**：来自华山标注平台
- **`computed`**：由 grounding / 几何规则计算得到
- **`imported`**：外部系统/数据集/旧版迁移导入（非本流水线计算产物）

建议额外补充（可选）：
- `relations[].evidence.method`：如 `"2d_bbox_center_rule"` / `"depitch_depth_order_rule"` 等，便于复现与 debug。

### 6.3 QA 生产与 metadata 的联动（先记录思路）

后续 QA 阶段若需要“同步更新 metadata 以便继续刷 QA”，可以考虑以下两类产物：

- **QA 输出（必有）**：`qa.jsonl`（或 OpenSpatial 的 `messages` parquet），记录每条 QA 的 `(sample_id, anchor_id, target_id, predicate, ref_frame, verbalization, ...)`。
- **metadata 回写（可选）**：在 `aux` 中追加与 QA 采样相关的统计/历史，例如：
  - 已生成的 QA 计数、各 predicate 分布
  - 已采样过的 object pair 去重集合（或其 hash）
  - 采样策略版本号

> 注意：v0 不强制在 QA 阶段回写 metadata；仅预留 `aux` 作为容器，避免污染主结构。

---

## 6. 完整示例（可直接归档）

```json
{
  "dataset": { "name": "human_anno", "version": "v0", "split": "train" },
  "sample": {
    "sample_id": "human_anno/img_000123",
    "view_id": 0,
    "image": {
      "path": "images/img_000123.png",
      "width": 640,
      "height": 480,
      "coord_space": "norm_0_999",
      "coord_scale": 1000
    }
  },
  "camera": null,
  "objects": [
    {
      "object_id": "chair#0",
      "category": "chair",
      "phrase": "the wooden chair",
      "bbox_xyxy_norm_1000": [120, 210, 260, 420],
      "point_uv_norm_1000": null,
      "quality": { "bbox": "low", "geometry": "unknown" }
    },
    {
      "object_id": "table#0",
      "category": "table",
      "phrase": "the dining table",
      "bbox_xyxy_norm_1000": [300, 240, 520, 460],
      "point_uv_norm_1000": null,
      "quality": { "bbox": "low", "geometry": "unknown" }
    }
  ],
  "relations": [
    {
      "anchor_id": "table#0",
      "target_id": "chair#0",
      "predicate": "front",
      "ref_frame": "egocentric",
      "components": ["left", "front"],
      "axis_signs": { "right": -1, "up": 0, "front": 1 },
      "source": "huashan_annotated",
      "score": 1.0,
      "evidence": { "front_order": "target_closer", "de_pitch_method": "unknown" }
    }
  ],
  "aux": {}
}
```

