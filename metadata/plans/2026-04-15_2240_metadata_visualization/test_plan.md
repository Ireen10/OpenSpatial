## 测试方案（Test Plan）

> 与 `plan.md` 功能点逐项对应；实现完成后在本文件勾选 Gate。

### 测试范围

- **覆盖**
  - `dataset.yaml` 中 **`viz.image_root`**（及可选 `output_root`）的加载与向后兼容（无 `viz` 块）。
  - **`dataset.name` ↔ 磁盘目录名 ↔ 记录内 `dataset.name`** 一致时的配置匹配与图像路径拼接。
  - `**/*.metadata.jsonl` 枚举规则（排除 `.checkpoints`）。
  - 单条 `MetadataV0` 的图像解码与 bbox/关系叠加逻辑（`image_plane`）；`egocentric` 仅列表、无画布箭头。
- **不覆盖**
  - tar + tarinfo 模式（设计 v0 已改为仅模式 A，本阶段不测）。
  - 跨多个 JSONL 文件的全局 `sample_id` 搜索（design 未要求 v0 必做）。

### 单元测试

| ID | 功能点（对应 plan） | 输入构造 | 断言点 | 状态 |
|----|---------------------|----------|--------|------|
| U1 | `VizSpec` / `DatasetConfig` 解析 | 最小 yaml 字符串：含 `viz.image_root`；另一份无 `viz` | 有 `viz` 时字段正确；无 `viz` 时默认不报错 | `test_viz_config_index.py` |
| U2 | 数据集配置索引 `name → config` | 两个临时 yaml，`name` 不同 | 按 name 取到对应 `image_root` | 同上 |
| U3 | 图像路径拼接（模式 A） | HTTP `/api/image` + 磁盘文件 | 见 I1 | `test_viz_server.py` |
| U4 | metadata 文件枚举 | `tmp/metadata_out/ds1/split1/a.metadata.jsonl`，并建 `.checkpoints/x.json` | 列表含 `a.metadata.jsonl`，不含 `.checkpoints` 内文件 | `test_viz_paths.py::test_enumerate_*` |
| U5 | coord 映射 | 固定 `width/height`、`coord_scale`、`bbox_xyxy_norm_1000` | 像素框与手算一致（允许整数舍入） | （前端；未单测） |

### 集成测试

| ID | 场景 | 需要的样例 | 预期 | 状态 |
|----|------|------------|------|------|
| I1 | 端到端 HTTP：列目录 + 读一行 + 读图 | `tmp` 下完整 `output_root` 树 + Pillow 生成 JPEG + 一行 metadata | 树/record/seek/image 均成功 | `test_viz_server.py` |
| I2 | 缺失 `viz.image_root` | metadata 可读，`dataset.yaml` 无 `viz` | 图像请求 404 或明确提示需配置 `viz.image_root`（行为以 plan 实现为准，需文档化） | （未自动化） |

### 手动 / 浏览器 Gate（Linux）

- [ ] 启动 `openspatial-metadata-viz`（参数与 `global.yaml`、`configs/datasets` 一致），能打开 UI。
- [ ] 选择 `output_root` 下某 `dataset/split/*.metadata.jsonl`，上一条/下一条切换正常。
- [ ] 图像与 bbox 对齐；`components` 复合关系展示与 `predicate` 单轴区分符合 design。
- [ ] Relations 中 `ref_frame=egocentric`（若 fixture 手工加入）仅列表显示，画布无 3D 箭头。

### 质量门槛（Gate）

- **通过条件**：上述 U1–U5 + I1 在 CI 或本地 `pytest` 通过；I2 行为与 README 一致；手动 Gate 勾选完成。
- **失败定位**：API 返回体包含 `dataset.name`、`sample.image.path`、`image_root`（若已解析），便于排查路径问题。
