## 设计：RefCOCO grounding 数据集最小 E2E 跑通

### 目标

跑通完整链路：**config 读取 → 文件读取 → adapter 转换 → 2D 关系增强 → jsonl 写出**，且 `global.yaml` 中的 `scale` 能影响输出（`sample.image.coord_scale`）。

### 变更点

- 新增数据集配置：
  - `metadata/configs/datasets/refcoco_grounding_aug_en_250618/dataset.yaml`
  - 配置 `adapter=GroundingQAAdapter`，并开启 `enrich.relations_2d=true`
- 新增最小真实样例 jsonl（仅 1 条 record）：
  - `metadata/configs/datasets/refcoco_grounding_aug_en_250618/sample_small.jsonl`
- CLI adapter 实例化支持注入：
  - `dataset_name`（已有）
  - `split`（传 `split.name`，替代 unknown）
  - `coord_scale`（来自 `global.yaml` 的 `scale`）
  - `coord_space`（默认 `norm_0_999`，可后续扩展）

### 验收

- CLI 跑 `refcoco_grounding_aug_en_250618/dataset.yaml` 可在输出中看到：
  - `objects/queries` 被解析
  - `relations` 经过 `enrich_relations_2d` 写入
  - `aux.enrich_2d` 存在
  - `sample.image.coord_scale == global.yaml.scale`

