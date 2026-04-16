## Change log — metadata visualization (v0)

### 代码

- 新增 `openspatial_metadata.viz`：HTTP API（`/api/tree`、`/api/record`、`/api/seek`、`/api/image`、`/api/config`）、静态单页 `viz/static/index.html`。
- 新增入口 `openspatial-metadata-viz`（`openspatial_metadata.viz.cli:main`）。
- `DatasetConfig` 增加显式可选字段 `output_root`、`viz`（`VizSpec`：`mode`/`image_root`）；`VizSpec.mode` 当前仅 `flat`。
- `setup.py` / `pyproject.toml`：`package_data` 包含 `viz/static/index.html`；`dev` 增加 `Pillow` 供测试生成 JPEG。

### 文档

- `metadata/docs/config_yaml_zh.md`：`output_root`、`viz` 说明。
- `metadata/README.md`：可视化命令与 `viz.image_root` 约定。

### 测试

- `tests/test_viz_config_index.py`、`test_viz_paths.py`、`test_viz_server.py`（需 `[dev]` 含 Pillow）。

### 配置示例

- `metadata/tests/configs/datasets/refcoco_grounding_aug_en_250618/dataset.yaml` 启用 `viz.image_root`（相对 `dataset.yaml` 解析至 `metadata/tests/fixtures/refcoco_viewer_images`）。

### 资源

- 占位 JPEG：`metadata/tests/fixtures/refcoco_viewer_images/type7/train2014/COCO_train2014_000000569667.jpg`（640×426）。

### 行为

- `viz.image_root`：**相对路径**相对于该数据集 `dataset.yaml` 所在目录解析（`resolved_image_root`）。
