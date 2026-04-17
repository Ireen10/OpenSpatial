## Change Log：viz 兼容 QA metadata 与 training bundle

### 本轮交付摘要

- **配置化**：`openspatial-metadata-viz` 继续使用 `--config-root` + `--global-config`，并新增可选 `--qa-config`（仅用于 UI 展示/追溯）。
- **metadata 兼容目录**：`/api/tree` 枚举 `output_root/{dataset}/{split}/.../*.metadata.jsonl`，并给出 `stage`（`metadata_noqa` / `metadata_qa` / `flat`）。
- **training bundle 浏览**：
  - `/api/tree` 额外返回 `training_parts`（只到 `dataset/split/part` 粒度，避免大数据爆内存）。
  - 新增 `/api/training_lines?dataset&split&part&offset&limit`：分页读取 training `jsonl/part_*.jsonl`，服务端强制 `limit<=200`。
  - 新增 `/api/training_image?dataset&split&part&relpath`：基于 `*_tarinfo.json` 的 `offset_data/size`，直接从 `.tar` 切片读取图片 bytes（无需解压）。
- **前端 UI**：左侧分为 Metadata 与 Training 两块；Training 模式下按页加载 records，并在右侧展示对话 turns + 从 tar 读取的图片。

### 自测

- `python -m pytest -q`（在 `metadata/` 下）：通过。
- 本地 smoke：`/api/training_lines` 与 `/api/training_image` 可返回有效记录与 JPEG bytes。

