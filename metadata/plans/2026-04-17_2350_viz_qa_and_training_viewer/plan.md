## 执行计划（Plan）：viz 兼容 QA metadata 与 training bundle

依据：`design.md`。

## 交付物清单

- 文档：本目录 `design.md`、`plan.md`、`test_plan.md`；实现完成后补 `change_log.md`。
- 代码：
  - `metadata/src/openspatial_metadata/viz/paths.py`：metadata 枚举兼容子目录；新增 training bundle 枚举与 tar 切片读取工具
  - `metadata/src/openspatial_metadata/viz/server.py`：新增 `/api/training_*` 与扩展 `/api/tree`
  - `metadata/src/openspatial_metadata/viz/cli.py`：参数与配置接线（增加 `--qa-config`，并在 `/api/config` 中回显）
  - `metadata/src/openspatial_metadata/viz/static/index.html`：UI 增加 Training 面板与 QA 面板
- 测试：新增 UT 覆盖 training tar 切片读取、tree 枚举；E2E 用 `metadata/tests/.tmp_pipeline_out` 或 fixtures 生成最小 bundle 验证接口可用。

## 任务拆解

### 任务 0：配置接线与 index 扩展

- 在 viz CLI 增加 `--qa-config`（可选），默认取 global `qa_config`；在 `/api/config` 返回中新增 `qa_config_path`（只读回显）。
- dataset index 中新增 resolved training root：优先 dataset `training_output_root`，否则 fallback 到 viz `--output-root`（与 CLI fallback 一致）。

### 任务 1：tree 枚举升级

- metadata：`enumerate_metadata_jsonl` 改为递归枚举 `{dataset}/{split}/**/*.metadata.jsonl`（排除 `.checkpoints`），并把 stage 信息打出来（flat / metadata_noqa / metadata_qa）。
- training：新增 `enumerate_training_parts(training_root)`，列出可用 `(dataset, split, part_id)`，并校验 jsonl/tar/tarinfo 三件套是否齐全。
- **大数据约束落地**：tree 只枚举到 `part`（不枚举行），并为接口增加 `limit` 上限（例如 200）。

### 任务 2：training bundle 读取 API

- `/api/training_record`：按行读取 `jsonl/part_*.jsonl`
- `/api/training_lines`：按 `offset/limit` 分页读取 `jsonl/part_*.jsonl`，避免 UI 端一次拿全量
- `/api/training_image`：
  - 读取 `*_tarinfo.json` 找到 member 的 `offset_data/size`
  - 对 `part_*.tar` 进行 `seek + read` 返回 bytes
  - content-type 用 `image/jpeg`（或基于 relpath 后缀推断）

### 任务 3：UI 扩展

- Sidebar 增加 Training 分组（dataset/split/part）。
- Training 模式：
  - 解析训练行结构：展示第一轮 user 的 image + text，并把后续 turns 渲染为对话列表
  - 点击 Prev/Next 按行号切换
  - **分页加载**：默认只请求 `offset/limit` 的一页（例如 50 行），并只渲染当前行附近的少量条目
- Metadata 模式：
  - Inspector 新增 “QA” tab：列出 `qa_items`（question/answer/qa_style/n_marked_boxes）

## 完成条件

- 同一条命令启动 viz 后：
  - 能浏览 metadata_noqa / metadata_qa 文件
  - 能浏览 training bundle 的某个 part jsonl 行，并正确加载图片（无需解压 tar）
- 新增测试通过（见 `test_plan.md`）。

