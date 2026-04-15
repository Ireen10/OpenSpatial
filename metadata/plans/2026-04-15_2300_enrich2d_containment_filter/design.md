## 设计：2D relation 增加“大包小（containment）”过滤

### 背景

仅用 IoU 阈值（如 `AMBIGUOUS_IOU=0.3`）无法过滤“**大框包含小框**”的情况：当面积差很大时，
\(IoU \approx A_{small}/A_{big}\) 会很小，即使小框几乎完全在大框内部。

该类情况常对应：

- 检测/标注的层级不一致（scene-level box vs part-level box）
- 重复标注或粗框覆盖细框，容易产生不稳定/无意义的方位关系

### 目标

在 `ref_frame=image_plane` 的 bbox-bbox pair 规则中增加一个**宽松**的 containment 过滤：

- 若交集面积占小框面积比例（IoA w.r.t. smaller box）满足：
  - \(\frac{|A \cap B|}{\min(|A|,|B|)} \ge 0.7\)
- 则该无序对的候选关系 **直接丢弃**（不进入谓词判定），并记录 dropped reason。

### 非目标

- 不对点模式（point-point）引入 containment 概念
- 不改变现有 IoU/near_center 的阈值语义，仅新增一条独立过滤

### 设计细节

- 新增常量：`CONTAINMENT_IOA = 0.7`
  - 放在 `metadata/src/openspatial_metadata/enrich/constants.py`
- 在 bbox-bbox 的 pair 预检查中计算：
  - `inter_area`（交集面积）
  - `ioa_small = inter_area / min(area_a, area_b)`（若 min area 为 0 则视为 0）
- 若 `ioa_small >= CONTAINMENT_IOA`：
  - 跳过该 pair，`aux.enrich_2d.dropped_relation_candidates` 追加：
    - `{"anchor_id": ..., "target_id": ..., "reason": "containment"}`（必要时可附 `ioa_small`）

### 测试

新增 UT 覆盖“**IoU 很小但 containment 高**”的典型反例：

- big: `[0,0,900,900]`
- small: `[10,10,110,110]`（远离中心，避免 near_center 误触发）
- 期望：`relations == 0` 且 dropped reason 包含 `containment`

