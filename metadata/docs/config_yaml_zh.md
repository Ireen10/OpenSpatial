# YAML 配置说明：Global Config 与 Dataset Config

本文描述 `openspatial-metadata` CLI 使用的两类 YAML 配置：**全局配置（global）**与**数据集配置（dataset）**。字段与代码中的 Pydantic 模型一致，见 `metadata/src/openspatial_metadata/config/schema.py`。

维护约定：修改 schema / loader / CLI 时，请与本页一并更新；流程与自检表见 `metadata/docs/docs_sync_convention_zh.md`。

---

## 两类配置各自解决什么问题

### Global Config（全局）

- **作用**：为一次 CLI 运行提供**跨数据集共用**的默认值（输出根目录、批大小、是否续跑等）。
- **是否必须**：**否**。不传 `--global-config` 时，使用代码内置默认值（见下文「Global 字段」中的默认值列）。
- **与 CLI 的关系**：
  - `--output-root` 若指定，则**覆盖** global 中的 `output_root`。
  - `--resume` 为真时，与 global 中的 `resume` **逻辑或**：任一为真即按续跑处理。

### Dataset Config（数据集）

- **作用**：描述**一个**数据集的标识、元信息、可选适配器，以及若干 **split**（每个 split 一种输入形态与输入路径列表）。
- **是否必须**：**是**（至少一个 dataset YAML）。`--config-root` 为**单个 `.yaml` 文件**时只处理该数据集；为**目录**时，会递归发现其下所有 `**/*.yaml`（注意会扫到子目录里全部 YAML，建议专用子目录如 `configs/datasets/`）。

---

## Global Config 字段说明

对应模型：`GlobalConfig`。YAML 顶层即字段键值对。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_root` | string | `metadata_out` | 输出根目录。CLI `--output-root` 可覆盖。其下会按 `数据集名 / split 名` 建子目录。 |
| `scale` | int | `1000` | 归一化坐标刻度（与 metadata v0 中 `coord_scale` 等概念对齐）；当前 CLI 主流程中未强依赖，供后续与工具函数使用。 |
| `batch_size` | int | `1000` | JSONL 写出时**攒批条数**：每满一批写盘并更新 checkpoint（JSONL）。 |
| `num_workers` | int | `0` | 计划用于**按输入文件**并行；**当前 CLI 尚未实现并行**，保留字段。 |
| `resume` | bool | `false` | 为 `true` 时启用 checkpoint **续跑**（与 CLI `--resume` 合并为「任一为真即续跑」）。 |
| `strict` | bool | `true` | 计划用于遇错即停等策略；**当前 CLI 尚未读取该字段**，保留字段。 |

允许**额外键**（模型 `extra = "allow"`），便于将来扩展；未知键当前会被静默保留在内存中，但**未必**被使用。

---

## Dataset Config 字段说明

对应模型：`DatasetConfig`。顶层字段如下。

### `name`（必填）

- **类型**：string  
- **说明**：数据集标识，同时用于输出目录名：`{output_root}/{name}/{split.name}/...`。

### `meta`（可选）

- **类型**：任意 YAML 映射（在模型中为 `Dict[str, Any]`）  
- **说明**：数据集级元信息（来源、版本说明、许可证等），**不参与路径解析**；可自由扩展。

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
| `name` | string | 输出子目录名：`{output_root}/{dataset.name}/{name}/`。 |
| `input_type` | string | **`jsonl`** 或 **`json_files`**（仅此两种）。 |
| `inputs` | string 列表 | 输入路径或模式列表，见下一节。 |

---

## `splits[].inputs`：路径、通配与范围展开

由 `expand_inputs()` 处理，行为如下（与**当前进程工作目录**相对；建议在仓库根目录运行 CLI，或使用绝对路径）。

1. **范围花括号**（单段）：形如 `data_{000000..000003}.jsonl`，展开为多个字面路径。  
2. **通配符**：若字符串中含 `*`、`?`、`[`，则按 **当前工作目录** 做 `glob`，结果排序后加入列表。  
3. **普通路径**：无通配时，按路径字符串使用（相对路径即相对 cwd）。  
4. 列表内展开结果会**按顺序去重**。

---

## `input_type` 与输出布局（当前 CLI 行为摘要）

- **`jsonl`**：对每个展开后的输入文件 **1:1** 生成 `{输入文件主名}.out.jsonl`，写在 `{output_root}/{dataset}/{split}/` 下。Checkpoint 记录 `next_input_index`（按行）。  
- **`json_files`**：将多个单文件 JSON 聚合为 `part-000000.jsonl` 等；每个输入文件 checkpoint 标记 `done`。

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
  [--resume]
```

配置校验入口：`load_global_config` / `load_dataset_config`（YAML → Pydantic）；适配器校验：`resolve_adapter`。

---

## 相关代码与文档

- 模型定义：`metadata/src/openspatial_metadata/config/schema.py`  
- 加载与展开：`metadata/src/openspatial_metadata/config/loader.py`  
- CLI：`metadata/src/openspatial_metadata/cli.py`  
- Metadata 结构（非 YAML）：`metadata/docs/metadata_spec_v0_zh.md`
