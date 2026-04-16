## 执行计划（Plan）

> 依据：`metadata/plans/2026-04-15_2240_metadata_visualization/design.md`（已定稿方向：仅 `*.metadata.jsonl`、轻后端 + 前端、图像模式 A、`output_root` 树形浏览、3D 旁路）。  
> 配置约定：**`image_root` 等可视化参数写在各数据集 `dataset.yaml` 中**，与 ingestion 共用同一配置源，避免重复维护。

### 交付物清单

- **文档**
  - 更新 `metadata/docs/config_yaml_zh.md`：说明 `dataset.yaml` 中可选 **`viz`**（或同等命名）字段及 `image_root` 语义、与 `output_root` 的复用关系。
  - 更新 `metadata/README.md`：增加可视化工具入口命令、依赖（若新增）、与 `global.yaml` / `dataset.yaml` 的配合说明。
- **代码**
  - 在 `metadata/src/openspatial_metadata/config/schema.py` 中为可视化增加**显式可选模型**（例如 `VizSpec`），包含 `image_root`（可选字符串）、v0 固定 **`mode: flat`**（解压目录，与设计一致）；`DatasetConfig` 增加可选字段 `viz: Optional[VizSpec]`（或嵌套字典经校验），与现有 `extra = "allow"` 兼容迁移。
  - 新增可视化后端模块（建议路径 `metadata/src/openspatial_metadata/viz/` 或 `metadata/src/openspatial_metadata/app/`）：  
    - 枚举 `{output_root}/{dataset_name}/{split}/**/*.metadata.jsonl`（跳过 `.checkpoints`）；  
    - 按行读取当前记录，不提供全文件常驻内存；  
    - 提供 HTTP API：`output_root` 目录树、打开文件、按行号或顺序 prev/next、按 `sample_id` 在当前文件内定位（实现方式：首次需要时构建行级索引或线性扫描，见任务拆解）；  
    - **`GET` 图像**：`image_root` 来自**当前记录对应数据集**的 `dataset.yaml`（通过 `record.dataset.name` 与配置 `name` 匹配，或用户显式选中数据集配置路径）；路径解析为 `Path(image_root) / sample.image.path`，不存在则 404 + 明确错误信息。
  - 前端：单页（React 或轻量静态页），实现 design 中的 Header / Canvas / Inspector；`image_plane` 叠加 bbox、关系箭头；非 `image_plane` relation 仅列表。
- **配置**
  - 在测试配置根（如 `metadata/tests/configs/datasets/refcoco_grounding_aug_en_250618/dataset.yaml`）中增加 **`viz.image_root`** 示例（路径可为相对路径，便于仓库内 fixtures 复用）。
- **样例 / fixtures**
  - 测试用临时目录：最小 `*.metadata.jsonl` 一行 + 对应假图像文件，验证拼接路径可读。

### 文档同步（与本变更一并交付）

- [ ] `metadata/docs/config_yaml_zh.md`
- [ ] `metadata/README.md`
- [ ] `metadata/plans/2026-04-15_2240_metadata_visualization/test_plan.md`（本文件配套，实现后按用例勾选）
- [ ] `metadata/docs/metadata_spec_v0_zh.md` — **无需更新**（若不修改 `MetadataV0` JSON 对外字段）
- [ ] `metadata/docs/project_progress_zh.md` — **整轮收束后再更新**（开发 + 自测通过 + `change_log.md` 之后）
- [ ] 其他：无

### 任务拆解

按顺序执行；每项含目标、修改文件、完成条件。

1. **配置模型与 YAML 约定**
   - **目标**：可视化读取 `image_root` / 默认 `output_root` 时优先来自 **同一 `dataset.yaml`**，与 `openspatial-metadata` 行为一致。
   - **文件**：`metadata/src/openspatial_metadata/config/schema.py`；示例 `metadata/tests/configs/datasets/refcoco_grounding_aug_en_250618/dataset.yaml`。
   - **完成条件**：`load_dataset_config` 能解析 `viz`；文档中字段名与类型表一致；无 `viz` 时行为与现网兼容（ingestion 不受影响）。

2. **数据集配置解析辅助（viz 用）**
   - **目标**：给定 `config_root`（如 `metadata/tests/configs/datasets`）或单个 `dataset.yaml`，建立 **`dataset.name` → 已加载配置**（含 `viz`、`output_root`）的索引，供后端在浏览 `metadata_out/...` 时匹配 `record["dataset"]["name"]`。
   - **文件**：`metadata/src/openspatial_metadata/viz/...`（或 `config/` 下小模块）。
   - **完成条件**：单元测试：两个 mock yaml 不同 `name`，解析后索引正确；缺失 `viz` 时返回空 `image_root` 而非抛错。

3. **HTTP 后端：目录树与 JSONL 行访问**
   - **目标**：实现 design 中「绑定 output_root」流；不预加载全部 JSONL 内容。
   - **文件**：viz server 主模块 + 路由。
   - **完成条件**：API 返回数据集/split/文件列表；能按文件路径 + 行号返回单条 JSON；prev/next 不泄漏全文件到内存（允许按行迭代当前文件）。

4. **HTTP 后端：图像静态服务（模式 A）**
   - **目标**：`image_root / sample.image.path`；`image_root` 来自匹配到的 `dataset.yaml` 的 `viz.image_root`。
   - **文件**：同上。
   - **完成条件**：集成测试：临时目录下放一张图，metadata 一行指向相对 path，请求返回 200 与正确 `Content-Type`；错误路径返回可读错误体。

5. **前端 UI（v0）**
   - **目标**：画布 + Inspector；`phrase` > `category` > `object_id`；`coord_scale` 来自记录，缺失时用 `global.yaml` 的 `scale` 兜底（后端或前端一致即可，需在 README 写清）。
   - **文件**：前端源码目录（待实现时确定，如 `metadata/viz_ui/` 或 `src/openspatial_metadata/viz/static/`）。
   - **完成条件**：手工清单见 `test_plan.md`；核心布局与 design 一致。

6. **CLI 入口**
   - **目标**：例如 `openspatial-metadata-viz`，参数：`--global-config`、`--config-root`（datasets 目录或单 yaml）、`--output-root`（可覆盖，与 ingestion 对齐）、`--host`/`--port`。
   - **文件**：`metadata/pyproject.toml` `[project.scripts]`；入口函数。
   - **完成条件**：本地启动后浏览器可打开；`--help` 文档完整。

### 里程碑与回滚

- **里程碑**：M1 配置 + 后端 API + 最小前端可读图；M2 UI 完整与测试补齐。
- **回滚策略**：未合并前删除 `viz` 相关包与入口；已合并则通过 `pyproject` 移除 entry point 并保留分支还原；`DatasetConfig` 新增字段均为可选，回滚不影响 ingestion。
