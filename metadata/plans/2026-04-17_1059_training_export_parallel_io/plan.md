# 执行计划（Plan）：训练导出多 part 切分、I/O 并行与断点续跑

依据：`design.md`（已采访对齐）、`metadata/docs/training_data_format_zh.md`。

## 交付物清单

- 文档：本目录下 `plan.md`、`test_plan.md`；实现完成后补 `change_log.md`。
- 代码（核心）：
  - 配置：扩展 `dataset.yaml`（仍由 `--config-root` 扫描）增加 `training_output_root`，并支持从 metadata 起步的 dataset（adapter=passthrough）。
  - 训练导出新增/改造为 **record 流**入口（source= jsonl/json_files）并实现：
    - part 映射（jsonl 1:1；json_files 聚合 part）
    - 文件粒度并行（jsonl）
    - checkpoint/resume（与上游语义同构）
    - tar+tarinfo+jsonl 的一致写入（同一 worker 独占一个 part bundle）
  - E2E-A/B/C 三种链路的“单条 record 不断链”执行器（通过可跳过步骤组合实现，避免冗余）。
- 测试：
  - 并行/恢复/冲突去重的单测与 E2E（见 `test_plan.md`）。

## 约束（来自设计对齐）

1. **E2E-A 必须写两份 metadata**：`metadata_noqa/` 与 `metadata_qa/` 两个子目录（不靠文件名后缀）。
2. **tar member 冲突**：不改目录结构，采用稳定后缀 `__r{input_index}` 去重，并控制长度。
3. **并行与容错优先**：本阶段采用“一个 worker 独占一个 part bundle”（跨 part 并行；part 内顺序写）。

## 任务拆解

### 任务 0：配置落地（方案 A）

- **目标**：保持“每 dataset 一个 `dataset.yaml` + `--config-root` 扫描”的体验，同时在 dataset 级别配置训练导出输出根。
- **工作项**：
  - 在 `metadata/src/openspatial_metadata/config/schema.py::DatasetConfig` 增加显式字段 `training_output_root: Optional[str]`（保留 extra allow）。
  - 增加**全局 QA 配置**加载入口（建议：`--qa-config <path>`，默认 `metadata/configs/qa_tasks.yaml`）。
  - 定义 `dataset.yaml` 对 QA 的引用字段：`pipelines.ensure_qa.qa_task_name` + 可选 `qa_task_overrides`（仅覆盖少量参数）。
  - 在文档与样例 dataset.yaml 中示例该字段。
  - 定义 fallback 规则：若 dataset 未配置 `training_output_root`，则使用 `{dataset.output_root or global.output_root}/{dataset.name}/{split}/training`（具体路径在实现中固定，避免覆盖）。
- **完成条件**：`dataset.yaml` 写法与现状兼容（inputs 仍可 glob/range），且可以 per-dataset 指定训练输出根。

### 任务 1：把 training export 提升为“record 流 source/sink”框架

- **目标**：对齐 `openspatial-metadata` 的 record 流抽象（`(record_dict, RecordRef)`），让训练导出能消费：
  - source A：jsonl（逐行 record 流）
  - source B：json_files（每文件 1 record 的流）
- **改造点**：
  - 将现有 `export_metadata_to_training_bundle(md, ...)` 保留为 **单 record**级 API（复用现逻辑），并新增 “流式 runner”：
    - `export_records_jsonl(...)`：输入 jsonl → 输出 part_{id}.*（1:1）
    - `export_records_json_files(...)`：输入 json_files 列表 → 输出 part_{id}.*（聚合）
- **完成条件**：runner 能在不引入 QA 的情况下处理 “metadata(withQA) → training” 的最小链路（E2E-C 的子集）。

### 任务 2：定义并实现三步组合管线（to_metadata / ensure_qa / export_training）

- **目标**：用同一套执行器覆盖 E2E-A/B/C：
  - `to_metadata(record)`：上游 grounding record → `MetadataV0`（adapter/enrich）
  - `ensure_qa(md)`：md(noQA) → md(withQA)（annotation task）
  - `export_training(md_with_qa)`：写入 images tar+tarinfo + jsonl
- **实现策略**：
  - 每条 record 的处理在同一 worker 内串联执行，不依赖“阶段间全量落盘再读回”。
  - E2E-B/C 通过跳过前置步骤实现（避免重复实现）。
  - 从 metadata 起步（E2E-B/C）采用“写法一”：metadata 也作为一个 dataset 配置（`adapter: passthrough`，`input_type: jsonl`，inputs 指向 `*.metadata.jsonl`），并通过 pipeline 开关跳过 `to_metadata`。
  - QA 生成参数来源：优先使用全局 QA 配置（`--qa-config`），dataset 仅引用 `qa_task_name` 并可用 `qa_task_overrides` 做少量覆盖。
- **完成条件**：E2E-A/B/C 均可被同一 runner 配置跑通。

### 任务 3：I/O 对齐——part 映射与目录结构

#### 3.1 jsonl source：输入文件 1:1 → part id

- **目标**：对每个输入文件 `ip`，稳定映射到一个 `part_{id:06d}.*`：
  - `images/part_{id}.tar`、`images/part_{id}_tarinfo.json`、`jsonl/part_{id}.jsonl`
  - 同时（E2E-A/B）写出两份 metadata：
    - `{out}/{dataset}/{split}/metadata_noqa/{ip.stem}.metadata.jsonl`
    - `{out}/{dataset}/{split}/metadata_qa/{ip.stem}.metadata.jsonl`
- **完成条件**：目录与命名符合 design，且可从输入文件列表顺序稳定复现 part id（或明确写出“part id 由排序后序号决定”的规则）。

#### 3.2 json_files source：聚合 part 输出

- **目标**：与上游一致：buffer 达 `batch_size` flush 一个 part（tar+tarinfo+jsonl），part id 递增。
- **完成条件**：单 writer flush；每个源文件 done checkpoint。

### 任务 4：断点续跑（checkpoint/resume）与一致性

#### 4.1 jsonl source（文件粒度并行）

- **目标**：checkpoint 语义与上游同构：
  - 每输入文件一个 ckpt（hash key），字段至少包含 `next_input_index`
  - resume 时从 `next_input_index` 继续，输出 jsonl/tar/tarinfo 采用 append+增量写回
- **完成条件**：人为中断后 resume，最终输出内容与一次跑完一致（以测试断言）。

#### 4.2 json_files source（聚合）

- **目标**：每源文件 done + 全局 next_part_id（或可恢复等价物）。
- **完成条件**：中断/续跑不重复处理 done 文件；part id 单调推进不回退。

### 任务 5：tar member 冲突去重（按对齐结论落地）

- **目标**：当同一 part 内出现相同 `relative_path` key：
  - 原图：`{stem}__r{input_index}{ext}`
  - 带框：`{stem}_m{8hex}__r{input_index}.jpg`
- **完成条件**：tarinfo key 唯一；jsonl 引用的 `relative_path` 均能在 tarinfo 中命中。

### 任务 6：并行策略（先容错，后扩展）

- **本阶段**：一个 worker 独占一个 part bundle（同一输入文件对应一个 worker；part 内顺序写）。
- **后续可选**：在不改变“写入独占”的前提下，对重绘渲染做批内并行（不纳入本阶段验收）。

## 非本阶段（显式推迟）

- 多进程写 tar、分布式写入、跨 part 的复杂调度优化。
- 训练 `id` 命名规则（继续允许 `""`）。

## 收束检查（合并前）

- [ ] `test_plan.md` 中条目全部通过
- [ ] E2E-A/B/C 三条链路均有最小可复现用例（至少 1 个输入文件）
- [ ] `change_log.md` 写完（实现完成后补）

