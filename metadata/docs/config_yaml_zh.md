# YAML 配置说明：Global Config 与 Dataset Config

本文描述 `openspatial-metadata` CLI 使用的两类 YAML 配置：**全局配置（global）**与**数据集配置（dataset）**。字段与代码中的 Pydantic 模型一致，见 `metadata/src/openspatial_metadata/config/schema.py`。

维护约定：修改 schema / loader / CLI 时，请与本页一并更新；流程与自检表见 `metadata/docs/docs_sync_convention_zh.md`。

---

## 两类配置各自解决什么问题

### Global Config（全局）

- **作用**：为一次 CLI 运行提供**跨数据集共用**的默认值（输出根目录、批大小、是否续跑等）。
- **是否必须**：**否**。不传 `--global-config` 时，使用代码内置默认值（见下文「Global 字段」中的默认值列）。
- **与 CLI 的关系**：
  - `--output-root` 若指定，则**覆盖** global 中的 `metadata_output_root`。
  - `--resume` 为真时，与 global 中的 `resume` **逻辑或**：任一为真即按续跑处理。
  - `--num-workers` 若大于 `0`，则**覆盖** global 的 `num_workers`；若为 `0`（默认），则沿用 global 的 `num_workers`。

### Dataset Config（数据集）

- **作用**：描述**一个**数据集的标识、元信息、可选适配器，以及若干 **split**（每个 split 一种输入形态与输入路径列表）。
- **是否必须**：**是**（至少一个 dataset YAML）。`--config-root` 为**单个 `.yaml` 文件**时只处理该数据集；为**目录**时，会递归发现其下所有 `**/*.yaml`（注意会扫到子目录里全部 YAML，建议专用子目录如 `configs/datasets/`）。

---

## Global Config 字段说明

对应模型：`GlobalConfig`。YAML 顶层即字段键值对。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `metadata_output_root` | string | `metadata_out` | **metadata 输出根目录**。CLI `--output-root` 可覆盖（仅覆盖 metadata）。其下会按 `数据集名 / split 名` 建子目录。 |
| `training_output_root` | string, 可选 | `null` | **训练数据输出根目录**（training bundle）。dataset 可覆盖；若 dataset 也未配置，则回退到 `metadata_output_root`。 |
| `scale` | int | `1000` | 归一化坐标刻度（与 metadata v0 中 `coord_scale` 等概念对齐）；当前 CLI 主流程中未强依赖，供后续与工具函数使用。 |
| `batch_size` | int | `1000` | JSONL 写出时**攒批条数**：每满一批写盘并更新 checkpoint（JSONL）。 |
| `num_workers` | int | `0` | 与 CLI `--num-workers` 合并得到**基础并行度**，再与展开后的输入文件数、硬顶 `32` 取最小值得到有效并行度 `effective`（见下文「并行与 `num_workers`」）。`effective <= 1` 时不创建线程池，整段 split 顺序执行。 |
| `resume` | bool | `false` | 为 `true` 时启用 checkpoint **续跑**（与 CLI `--resume` 合并为「任一为真即续跑」）。 |
| `strict` | bool | `true` | **遇错即停**（本轮仅支持 `true`）：并行或顺序路径下，worker / 读入失败会打印 **stderr** 并以**退出码 1** 结束；失败前已 **flush** 的批次会照常写盘并更新对应 checkpoint。CLI **不提供** `strict=False`。 |
| `qa_config` | string, 可选 | `null` | 全局 QA 任务注册表 YAML 路径（例如 `metadata/configs/qa_tasks.yaml`）。可被 CLI `--qa-config` 覆盖。仅在启用 dataset `pipelines.ensure_qa` / `pipelines.export_training` 路径时需要。 |

允许**额外键**（模型 `extra = "allow"`），便于将来扩展；未知键当前会被静默保留在内存中，但**未必**被使用。

---

## Dataset Config 字段说明

对应模型：`DatasetConfig`。顶层字段如下。

### `name`（必填）

- **类型**：string  
- **说明**：数据集标识，同时用于输出目录名：`{metadata_output_root}/{name}/{split.name}/...`。

### `meta`（可选）

- **类型**：任意 YAML 映射（在模型中为 `Dict[str, Any]`）  
- **说明**：数据集级元信息（来源、版本说明、许可证等），**不参与路径解析**；可自由扩展。

### `metadata_output_root`（可选）

- **类型**：string  
- **说明**：仅作用于**本数据集**的 metadata 写出根目录；若省略则使用 global 的 `metadata_output_root`。与 CLI `--output-root`（全局覆盖 metadata）的优先级关系见 `metadata/src/openspatial_metadata/cli.py`。

### `viz`（可选）

- **类型**：映射，对应 `VizSpec`（见 `metadata/src/openspatial_metadata/config/schema.py`）。  
- **作用**：供 **`openspatial-metadata-viz`**（metadata JSONL 浏览器）使用，与 `openspatial-metadata` 主流程解耦；ingestion **不读取**这些字段。

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `mode` | string | v0 仅支持 **`flat`**：图像在磁盘上为扁平树，`Path(image_root) / sample.image.path` 可读。 |
| `image_root` | string，可选 | 解压 tar 后的图像根目录（与数据文档中 tar 内相对路径一致）。**若为相对路径**，则相对于**该数据集 `dataset.yaml` 所在目录**解析（便于写 `../../../tests/fixtures/...` 一类仓库内路径）。未设置时，浏览器无法通过 `/api/image` 加载像素，仅可看 JSON。 |

### `training_output_root`（可选）

- **类型**：string
- **说明**：训练数据 bundle（`images/*.tar` + `*_tarinfo.json` + `jsonl/*.jsonl`）的输出根目录。若省略则回退到 `{global.training_output_root or dataset.metadata_output_root or global.metadata_output_root}`。

### `pipelines`（可选，推荐用于端到端）

- **类型**：映射（当前实现接受 dict；模型允许 extra 字段）
- **说明**：当配置 `pipelines.ensure_qa=true` 或 `pipelines.export_training=true` 时，CLI 对 `jsonl` 输入会走“单条记录不中断”的串联执行路径（同一 worker 内）：
  - `to_metadata`：可选。对非 metadata 输入做 adapter/meta/enrich 后写出 `metadata_noqa/`
  - `ensure_qa`：可选。对每条 metadata 生成 `qa_items` 并写出 `metadata_qa/`
  - `export_training`：可选。将带 `qa_items` 的 metadata 导出为训练 bundle（`images/` + `jsonl/`）

支持字段（最小集）：

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `to_metadata` | bool | `true` | 为 `false` 时表示输入已是 metadata（跳过 adapter/meta/enrich），但仍会写出 `metadata_noqa/`。 |
| `ensure_qa` | bool | `false` | 生成 `qa_items`（需要 `--qa-config` 或 `global.qa_config`）。 |
| `export_training` | bool | `false` | 输出训练 bundle（需要 `ensure_qa` 先产出 QA，或输入本身已带 `qa_items`）。 |
| `qa_task_name` | string | `spatial_relation_2d` | 使用的 QA 任务名（在 `qa_tasks.yaml` 中注册）。 |
| `qa_task_overrides` | mapping | `null` | 覆盖全局 QA 任务 params 的少量字段。 |

### `adapter`（可选）

- **类型**：映射，对应 `AdapterSpec`。  
- **作用**：声明本数据集使用的适配器类；`resolve_adapter()` 会尝试 **import 并 `getattr` 该类**，仅校验**可导入**，**不在当前 CLI 主流程里调用转换逻辑**（框架阶段占位）。

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `file_name` | string，可选 | 省略 `module` 时，会解析为模块 `openspatial_metadata.adapters.<file_name>`（例如 `passthrough` → `openspatial_metadata.adapters.passthrough`）。 |
| `class_name` | string，可选 | 适配器类名，例如 `PassthroughAdapter`。可与 YAML 键 `class` 互换（模型里 `class` 映射到 `class_`）。 |
| `module` | string，可选 | 完整 Python 模块路径；若指定则**不再**用 `file_name` 拼前缀。 |
| `class` | string，可选 | 与 `class_name` 等价（YAML 常用 `class` 避免与关键字混淆时可写 `class_name`）。 |

`module` 与 `class_name`（或 `class`）都具备时即可完成解析；仅 `file_name` + `class_name` 亦为常见写法。

### `splits`（必填）

- **类型**：split 项的列表；每项对应 `SplitSpec`。

每个 **split** 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 输出子目录名：`{metadata_output_root}/{dataset.name}/{name}/`。 |
| `input_type` | string | **`jsonl`** 或 **`json_files`**（仅此两种）。 |
| `inputs` | string 列表 | 输入路径或模式列表，见下一节。 |

---

## `splits[].inputs`：路径、通配与范围展开

由 `expand_inputs()` 处理，行为如下（与**当前进程工作目录**相对；建议在仓库根目录运行 CLI，或使用绝对路径）。

1. **范围花括号**（单段）：形如 `data_{000000..000003}.jsonl`，展开为多个字面路径。  
2. **通配符**：若字符串中含 `*`、`?`、`[`，则按 **当前工作目录** 做 `glob`，结果排序后加入列表。  
3. **普通路径**：无通配时，按路径字符串使用（相对路径即相对 cwd）。  
4. 列表内展开结果会**按顺序去重**。

> **提示（Windows）**：`inputs` 中含 `*` 的 glob 依赖当前工作目录下的 `Path.glob` 解析；若遇到「展开为空」或路径怪异，请改用**显式文件列表**或**绝对路径字面量**（逗号分行），避免依赖对「绝对路径 + 通配」的跨平台差异。

---

## 并行与 `num_workers`（`ThreadPoolExecutor`）

- **实现方式**：仅 **`ThreadPoolExecutor`**（文件级任务）；**不**使用 `ProcessPoolExecutor`。
- **有效并行度** `effective`：记 CLI 解析值为 `cli_n`（`--num-workers`，默认 `0` 表示不覆盖）、global 为 `g_n`、`F = len(展开后的输入文件)`。则  
  `raw = cli_n if cli_n > 0 else g_n`，再 `effective = min(raw, F, 32)`（硬顶 `32` 防止过量线程）。  
  若 `effective <= 1`，该 split **整段走顺序逻辑**（与旧行为一致）。
- **`jsonl`**：`effective > 1` 时，**每个输入文件**一个任务，仍各自 **1:1** 输出与**按文件**的 checkpoint（与顺序模式语义一致，仅调度并发不同）。
- **`json_files`**：`effective > 1` 时，worker 仅负责**读入单文件 JSON** 并构造 `aux.record_ref`；**主线程**负责攒 `batch_size`、写 `part-*.jsonl`，且 **仅在 flush 成功之后** 对本批涉及的源文件写入 `done` checkpoint。**输出行序不保证**与 YAML 中 `inputs` 列表一致，但每行的 `aux.record_ref.input_file` 可追溯到真实路径。
- **失败与收尾**：任一线程任务失败 → `shutdown(wait=True, cancel_futures=True)` → stderr 含输入路径与异常 → **进程退出码 1**。`json_files` 并行路径在退出前若内存中仍有未满批的已读记录，会先 **flush + checkpoint** 再退出，避免已成功的 worker 结果丢失。

---

## `input_type` 与输出布局（当前 CLI 行为摘要）

- **`jsonl`**：对每个展开后的输入文件 **1:1** 生成 `{输入文件主名}.out.jsonl`，写在 `{output_root}/{dataset}/{split}/` 下。Checkpoint 记录 `next_input_index`（按行）。  
- **`json_files`**：将多个单文件 JSON 聚合为 `part-000000.jsonl` 等；每个输入文件在 **对应记录已成功写入某 part 且 flush 完成后** checkpoint 标记 `done`（顺序与并行路径一致）。

---

## 最小示例

**Global**（`metadata/configs/global.yaml`）：

```yaml
output_root: metadata_out
scale: 1000
batch_size: 3
num_workers: 0
resume: false
strict: true
```

**Dataset**（节选）：

```yaml
name: demo_dataset
meta:
  source: demo
adapter:
  file_name: passthrough
  class_name: PassthroughAdapter
splits:
  - name: train_jsonl
    input_type: jsonl
    inputs:
      - "metadata/tests/fixtures/jsonl_shard_small.jsonl"
  - name: train_json
    input_type: json_files
    inputs:
      - "metadata/tests/fixtures/json_files_small/*.json"
```

---

## 与 CLI 的对应关系

```text
openspatial-metadata \
  --config-root <目录或单个 dataset yaml> \
  [--global-config <global yaml>] \
  [--output-root <覆盖 output_root>] \
  [--resume] \
  [--num-workers <int>]
```

`--num-workers`：`0`（默认）表示使用 global 的 `num_workers`；`>0` 时覆盖 global，再与文件数、`32` 取 `min` 得到有效并行度。

配置校验入口：`load_global_config` / `load_dataset_config`（YAML → Pydantic）；适配器校验：`resolve_adapter`。

---

## 相关代码与文档

- 模型定义：`metadata/src/openspatial_metadata/config/schema.py`  
- 加载与展开：`metadata/src/openspatial_metadata/config/loader.py`  
- CLI：`metadata/src/openspatial_metadata/cli.py`  
- Metadata 结构（非 YAML）：`metadata/docs/metadata_spec_v0_zh.md`
