# Design：训练导出多 part 切分、I/O 并行与断点续跑（与 metadata I/O 对齐）

## 背景与目标

本轮要把 **metadata → 训练数据（grounding 同构 JSONL + images tar + tarinfo）** 做到：

1. **I/O 对应策略与上游一致**：对齐 `openspatial-metadata` 现有的“输入文件 ↔ 输出文件/part”规则、文件粒度并行与 checkpoint。
2. **三种端到端链路都打通**（避免冗余）：
   - **E2E-A**：上游 grounding JSONL →（adapter/enrich）→ **metadata（无 QA）** →（annotation）→ **metadata（带 QA）** →（export）→ **训练数据**。
   - **E2E-B**：metadata（无 QA）→（annotation）→ metadata（带 QA）→ export → 训练数据。
   - **E2E-C**：metadata（带 QA）→ export → 训练数据。
3. **断点续跑策略清晰可实现**：支持 resume，不重复、不乱序、可验证。
4. **“单条数据在流程内不中断跑完全程”**：对任意单条输入 record，处理链路在同一执行流内完成（不要求“整个阶段全部结束后再跑下一阶段”）。

## 配置收束（方案 A：沿用“一 dataset 一 yaml + config-root 扫描”）

你已确认采用方案 A，并要求：

1. **兼容现状**：继续使用 `dataset.yaml` + `--config-root` 扫描多 dataset 的模式；输入 `splits[].inputs` 保持现有语义（glob / range pattern），不引入“巨型单配置”。
2. **输出根策略**：
   - metadata（无 QA / 带 QA）共享 **同一个 metadata 输出根**（沿用 `dataset.output_root` / `global.output_root` 规则），并在其下分 `metadata_noqa/` 与 `metadata_qa/` 子目录。
   - training bundle 使用 **另一个根**，并且 **放在 dataset.yaml 中**作为显式字段（新增字段，便于 per-dataset 管理）。
3. **QA 生成不依赖 OpenSpatial pipeline**：尽量直接使用 annotation task 逻辑（不走 `run.py` / `BasePipeline`），并把必要能力收束到 `metadata` 子项目内管理。

### dataset.yaml 需要新增的字段（建议）

- `training_output_root: str?`  
  训练导出根目录（写 `images/` + `jsonl/`）。缺省时可回退到 `global.output_root` 下的子目录（但推荐显式配置，避免不同 dataset 互相覆盖）。

> 注：当前 `DatasetConfig` 允许 extra 字段，因此可先按约定写入并实现读取；后续再把字段加进 `config/schema.py` 做强校验。

## 已有 I/O 策略（必须对齐的上游事实）

来自 `metadata/src/openspatial_metadata/cli.py` + `io/json.py` + `metadata/plans/2026-04-14_1737_metadata_framework/plan.md`：

### 核心抽象：record 流

上游框架的设计点是：不管输入来自哪里，都统一抽象成：

- `Iterator[(record_dict, record_ref)]`
- 其中 `record_ref = { input_file, input_index }`（实现为 `RecordRef`）

当前实现对应到：

- `iter_jsonl(path) -> Iterator[(dict, RecordRef)]`
- `iter_json_file(path) -> Iterator[(dict, RecordRef)]`

也就是说，“jsonl / json_files”是 **record 流的两类 source**，而不是两套完全不同的处理框架。

### source A：`jsonl`（分片 JSONL）

- **输出映射**：每个输入文件 `ip` 写出 **同名**：`out_dir / (ip.stem + ".metadata.jsonl")`（1:1）。
- **并行粒度**：文件粒度线程并行（`ThreadPoolExecutor`），每个 worker 消费一个 `ip` 的 record 流。
- **checkpoint 语义**：按输入文件 key（hash）存储，核心字段 `next_input_index`（逐行推进）。

### source B：`json_files`（单 JSON 文件列表）

- **输出映射**：record 流在 writer 端聚合，flush 成 `part-{idx:06d}.metadata.jsonl`（由 `batch_size` 决定）。
- **并行粒度**：可并行读取/转换单 JSON 文件，但 **写出由单 writer 负责**（buffer flush）。
- **checkpoint 语义**：按源文件记录 `done=true`（文件级完成）。

> 对齐原则：training export 也采用 **record 流** 视角；仅在“source 是 jsonl 还是 json_files”时分叉输出映射/并行粒度/checkpoint 语义（与上游保持同构）。

## 统一“处理图”（避免冗余的抽象）

为了覆盖 E2E-A/B/C 且不重复实现，抽象 3 个纯步骤（可独立启用/跳过）：

1. **`to_metadata(record)`**：上游 record → `MetadataV0`（adapter + dataset meta + enrich）。  
   - 对于 E2E-B/C：输入已是 metadata，则跳过。
2. **`ensure_qa(metadata)`**：`MetadataV0` → `MetadataV0(with qa_items)`（annotation）。  
   - 对于 E2E-C：若 `qa_items` 非空则跳过。
3. **`export_training(metadata_with_qa)`**：生成训练行（分组、多轮）+ 重绘图像 + 写 tar/tarinfo/jsonl。

**端到端的“不中断”定义**：对每条输入 record，按上述 1→2→3 顺序在同一次处理里完成；I/O 仅是“流式读写”，不构成阶段间人为分割。

## Output 规则（必须与现文档一致）

参考 `metadata/docs/training_data_format_zh.md`：

- `output_root/images/part_{id:06d}.tar`
- `output_root/images/part_{id:06d}_tarinfo.json`
- `output_root/jsonl/part_{id:06d}.jsonl`

以及 JSONL 行结构（`meta_prompt==[""]`、user/assistant 交替、首轮 user 含 image+text，其后仅 text）。

## part 切分与 I/O 对应策略（核心设计点）

### 1）当输入为 `jsonl`（grounding 或 metadata.jsonl）

对齐上游 jsonl 策略：**输入文件 1:1 对应一个输出“bundle”**（一组 tar+tarinfo+jsonl），其 part id 由“输入文件序号”决定。

- 输入：`.../shard_00.jsonl`, `.../shard_01.jsonl`, ...
- 输出（示例）：  
  - `images/part_000000.tar` + `_tarinfo.json` + `jsonl/part_000000.jsonl` 对应 shard_00  
  - `images/part_000001.*` 对应 shard_01

并行策略：与上游一致，**文件粒度并行**（每个 worker 处理一个输入文件，从 `next_input_index` 续跑）。

checkpoint：每个输入文件一份 ckpt，字段：

- `input_file`
- `next_input_index`
- （可选）`output_part_id`（稳定映射，便于迁移）
- `errors_count`

### 2）当输入为 `json_files`

对齐上游 json_files 策略：聚合输出 `part_{id:06d}.*`，由 `batch_size` flush 决定 part id 递增；读取/转换可并行，但写出为单 writer flush。

checkpoint：沿用“源文件 done”语义：

- 每个源 json 文件：`{input_file, done=true, errors_count=0}`
- 全局：`next_part_id`（或通过扫描输出目录恢复）

## tar 写入与 tarinfo（断点续跑要求）

本轮要支持 resume，因此必须明确：

1. **追加写**：当 `resume=true` 且目标 `part_000xyz.tar` 已存在，应能继续写入后续成员，并同步更新 tarinfo 与 jsonl（append）。
2. **去重/冲突**：tarinfo 是 dict（key 唯一），因此 tar 内成员名必须在该 part 内唯一。

建议策略：

- **member name** 的基准仍以 `sample.image.path` 为主（原图沿用；带框用 `_m{8hex}.jpg`），但若出现重复键（同名冲突），采用稳定的 disambiguation：`{stem}__r{input_index}.jpg`（或在目录前缀加 `record_index/`），并将这一规则写入文档。
- resume 时，从既有 `*_tarinfo.json` 载入已有 key 集合，遇到冲突按同一规则生成新 key（保证确定性）。

tarinfo `offset_data/size/sparse`：与现阶段一致（优先 `offset_data`，否则 fallback）。此处不展开；属于实现细节。

## 三种 E2E 的落点（如何不冗余）

### E2E-A：grounding → metadata(noQA) → metadata(withQA) → training

实现为单 worker 逐 record：

1. 读 grounding JSONL 一行
2. `to_metadata` 得到 `MetadataV0`（可选择同时写出 `*.metadata.jsonl` 无 QA 版本；写出策略与上游一致：**同名 shard 输出**）
3. `ensure_qa` 得到带 `qa_items` 的 metadata（可写出带 QA 的 metadata.jsonl，同样 1:1）
4. `export_training` 写入训练 bundle（tar+tarinfo+jsonl）

关键：metadata 的两种输出（无 QA / 带 QA）与训练 bundle 都以 **同一输入文件** 为单位（同一个 worker），避免跨阶段切换造成对齐困难。

### E2E-B：metadata(noQA) → metadata(withQA) → training

跳过 `to_metadata`，其余同 E2E-A；仍采用 jsonl 输入 1:1 输出策略。

### E2E-C：metadata(withQA) → training

跳过 `to_metadata` 与 `ensure_qa`，只做 export；仍采用 jsonl 输入 1:1 输出策略。

## 断点续跑（resume）设计原则

### jsonl 输入（文件粒度并行）

- 每个输入文件有独立 ckpt（`next_input_index`），resume 时从该 index 继续迭代。
- 输出 jsonl 采用 append；输出 tar 采用 append；tarinfo 采用“读旧 + 增量写回”。
- 若写出失败，保证 ckpt 只在成功 flush 后推进（与上游 `_write_checkpoint_atomic` 对齐）。

### json_files 输入（聚合 + 单 writer）

- 处理每个源文件的 done ckpt，不重复处理已 done 的文件。
- part id 的推进与 flush 强绑定：每写完一个 part（tar+tarinfo+jsonl）就推进 `next_part_id`。

## 未决点（需在 plan/test_plan 前收敛）

## 对齐结论（已采访确认）

1. **E2E-A 必须同时写出两份 metadata**：无 QA 与带 QA **用不同子目录区分**（不靠文件名后缀）。  
   - 约定形态（示例）：`.../{dataset}/{split}/metadata_noqa/*.metadata.jsonl` 与 `.../{dataset}/{split}/metadata_qa/*.metadata.jsonl`。  
   - 这样既保持 `*.metadata.jsonl` 后缀一致，又避免文件名膨胀。

2. **tar member name 冲突策略**：**不改变目录结构**（不加额外目录前缀），采用 **稳定后缀** 消解同 part 内 key 冲突，并控制长度。  
   - 原图：默认使用 `sample.image.path`；若冲突则改为 `{stem}__r{input_index}{ext}`（`input_index` 来自 `RecordRef.input_index`，为稳定整数）。  
   - 带框图：默认 `{stem}_m{8hex}.jpg`；若冲突则在 `.jpg` 前追加 `__r{input_index}`：`{stem}_m{8hex}__r{input_index}.jpg`。  
   - 后缀长度控制：`__r{input_index}` 只引入十进制 index；`m{8hex}` 固定 9 字符（含 m），整体可控。

3. **并行与写入锁（容错 vs 性能）**：本阶段采用 **“一个 worker 独占一个 part bundle”**（最容错、最易 resume）。  
   - 即：同一输入文件（jsonl source）在同一 worker 内顺序完成 **读取 →（可选）to_metadata →（可选）ensure_qa → export_training（写 tar+tarinfo+jsonl）**。  
   - 性能扩展（后续阶段）：可在“一个 worker 独占 part”的前提下，把 **渲染/重绘**改成批量并行（线程/进程池）但仍由该 worker 串行写入，以避免跨线程/跨进程写 tar 的一致性问题。

> 下一步（plan.md）会把上述未决点落成实现项与测试项，并明确 CLI/库 API 的入口形态。

