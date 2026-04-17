## 设计（Design）：viz 兼容 QA metadata 与 training bundle

### 背景与目标

现有 `openspatial-metadata-viz` 只能浏览 `{output_root}/{dataset}/{split}/*.metadata.jsonl`（浅层目录），并通过 `viz.image_root` 加载原图进行 overlay（objects/relations）。

本轮目标：

1. **viz 同样依赖配置文件**：
   - 仍使用 `--config-root` + `--global-config` 发现 datasets，并读取每个 dataset 的 `viz.image_root` 与 `training_output_root`。
   - 新增可选 `--qa-config`（与 CLI 对齐）用于在 UI 里展示“当前 dataset 使用的 QA task 配置来源/版本”（只读信息，不参与渲染）。
2. **兼容两类展示**：
   - **带 QA 的 metadata 展示**：支持浏览 `metadata_noqa/` 与 `metadata_qa/`（以及历史遗留的平铺输出），并在 UI 中展示 `qa_items` 列表。
   - **训练数据展示**：支持浏览 training bundle：`images/part_*.tar` + `images/part_*_tarinfo.json` + `jsonl/part_*.jsonl`；能按行查看一条对话，并显示对应图片（从 tar 按 offset/size 直接读，不要求解压）。

### 关键约束

- **不改变现有 bundle 格式**：training bundle 仍以 tar+tarinfo+jsonl 为 SSOT。
- **路径安全**：所有文件读取必须限定在解析后的 root 下（metadata output_root / training_output_root / image_root）。
- **大数据硬约束（从设计之初就纳入）**：
  - **按需读取**：只在用户选定 `(dataset, split, part)` 后，才读取对应 part 的少量行与单张图片；禁止全量加载 jsonl/tar 到内存。
  - **分页/限流**：任何“列表”与“读取记录”接口必须支持分页（`offset/limit`），并设置服务端上限（例如 `limit <= 200`）。
  - **不缓存大对象**：服务端不得缓存 tar member 的完整 bytes（允许很小的 LRU：例如 <= 32 张缩略图或 <= 64MB 总量）；默认无缓存也可用。
  - **tree 枚举最小化**：左侧树只枚举到 `dataset/split/part` 粒度；不枚举 part 内每一行，避免返回巨大 JSON 与 UI 卡死。

### 数据与目录约定（与现有实现对齐）

1. metadata 输出：
   - `{output_root}/{dataset}/{split}/metadata_noqa/*.metadata.jsonl`
   - `{output_root}/{dataset}/{split}/metadata_qa/*.metadata.jsonl`
   - 兼容旧：`{output_root}/{dataset}/{split}/*.metadata.jsonl`
2. training 输出：
   - `{training_output_root}/{dataset}/{split}/images/part_{id:06d}.tar`
   - `{training_output_root}/{dataset}/{split}/images/part_{id:06d}_tarinfo.json`
   - `{training_output_root}/{dataset}/{split}/jsonl/part_{id:06d}.jsonl`

### API 设计（HTTP）

在现有 server 基础上扩展：

- `GET /api/tree`
  - 返回 metadata 文件列表（包含 stage=metadata_noqa/metadata_qa/flat）
  - 返回 training bundle 列表（dataset/split 下的 part 清单）
- `GET /api/record`（保持）
  - 读取 metadata jsonl 的某一行
- `GET /api/image`（保持）
  - 基于 dataset.viz.image_root + relpath 读取原图
- `GET /api/training_record?dataset=...&split=...&part=000000&line=0`
  - 读取 training `jsonl/part_*.jsonl` 的某一行（允许扩展为 `offset/limit` 做分页）
- `GET /api/training_image?dataset=...&split=...&part=000000&relpath=...`
  - 通过对应 `*_tarinfo.json` 的 `offset_data/size` 从 tar 直接切片读出图片 bytes

补充（为大数据场景准备的分页接口）：

- `GET /api/training_lines?dataset=...&split=...&part=000000&offset=0&limit=50`
  - 返回该 part 的行范围（JSONL 按行解析），并返回 `line_count`（可缓存计数，禁止全量读入内存）

### UI 设计（静态单页）

- 左侧树：
  - **Metadata**：按 dataset/split/stage 分组显示 jsonl 文件
  - **Training**：按 dataset/split/part 显示 jsonl part
- 主视图：
  - Metadata：沿用原图 + overlay（objects/relations）；Inspector 新增 QA 面板（显示 `qa_items`，可点击定位并高亮 meta 字段）
  - Training：显示对话文本（data turns）与图片（从 tar 读取）；不绘制 overlay（training 图片已是最终渲染结果）

大数据交互约定：

- 默认仅加载一个 part 的 **可视窗口**（例如当前行 +/- 2）或一个分页页（例如 50 行），不提供“加载整个 part”按钮。

