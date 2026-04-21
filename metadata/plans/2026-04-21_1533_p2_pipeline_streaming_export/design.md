## 背景

- 当前 `metadata` 训练链路总体为阶段串行：`to_metadata -> ensure_qa -> export_training`。
- 已完成若干固定开销优化（短路、批量写入、resume 跳过解析、tqdm 稳定），单 worker 吞吐仍有提升空间。
- 用户希望推进 P2 结构性优化，并重点关注：
  1) 内存开销是否可控；
  2) 训练导出按“固定每个 jsonl 行数分包”策略下的整体行为。

## 目标

在不改变主语义（产物字段与训练样本内容）的前提下，提升端到端吞吐并降低跨阶段重复 IO/反序列化。

1. 将线性流程改为“有界阶段流水并行”。
2. 共享稳定中间表示，减少重复 `json.loads/model_validate/model_dump`。
3. 引入可选轻量缓存（默认关闭，优先磁盘型而非内存型）。
4. 优化训练导出为固定行数分包的流式写出，避免大缓冲导致的峰值内存上涨。

## 非目标

- 不改 QA 模板策略与 LLM 刷新语义。
- 不引入重型中间件（消息队列、分布式缓存）。
- 不在本轮重构所有历史接口；优先兼容现有 CLI/config。

## 现状问题

### 1) 线性阶段导致资源闲置

- 当前阶段边界清晰但串行，常见情况是 CPU 与 IO 不能充分重叠。
- export 阶段晚启动，前序阶段产物落盘后再读回，存在重复读写。

### 2) 重复反序列化与模型转换

- 阶段之间以 JSONL 交换为主，稳定字段重复做解析与模型构建。
- 大规模数据下（25w+）累计开销显著。

### 3) 导出缓冲与尾部对齐策略

- 当前按 `rows_per_part` 分包是正确方向，但实现中存在较大内存 buffer 风险（尤其包含 `image bytes` 时）。
- `row_align` 尾部不足部分当前可能丢弃，影响可追溯与数据利用率。

## 方案设计

### A. 有界阶段流水并行（核心）

将单 split 的链路拆成三个可并行阶段（逻辑上）：

1. Stage-1: `to_metadata`（含 adapter/dataset_meta/enrich）
2. Stage-2: `ensure_qa`
3. Stage-3: `export_training`（可开关）

使用有界队列串联：

- `Q12`: Stage-1 -> Stage-2
- `Q23`: Stage-2 -> Stage-3

关键约束：

- 每个队列必须 `maxsize`（建议 `2~4 * worker` 起步）。
- 队列元素不携带大块二进制（特别是图像 bytes）；只传轻量结构和索引引用。
- 回压（backpressure）生效：下游慢时上游阻塞，防止内存无界增长。

### B. 共享中间表示（减少反序列化）

定义阶段间统一中间结构（示意）：

- `RecordEnvelope`：
  - `record_ref`（input_file, input_index）
  - `metadata_obj`（可选，优先模型对象）
  - `metadata_payload`（可选，必要时懒生成）
  - `qa_ready` 标记

策略：

- 同进程阶段间优先传 `metadata_obj`（避免 dump/load 往返）。
- 仅在“需要落盘/跨进程/恢复”时 materialize 为 payload。
- 保持 checkpoint 与输出语义不变。

### C. 可选轻量缓存（默认 off）

缓存对象仅限“稳定中间结果”：

1. `to_metadata` 后但未加 QA 的稳定结果；
2. 可重用的 export 前索引信息（不含图片 bytes）。

缓存层级：

- 首选磁盘缓存（SQLite 或分片 KV 文件），键用 `(input_file_hash, input_index, pipeline_signature)`。
- 内存缓存仅用于极短生命周期小窗口（LRU，小上限）。

禁忌：

- 不缓存大二进制图像。
- 不做无版本签名缓存，防止脏读。

### D. 训练导出固定行数分包：改为流式 writer

目标：保留 `rows_per_part` 分包语义，但去掉“大列表攒满再写”模式。

新机制：

1. 打开“当前 bundle writer”；
2. 每来一行训练样本立即写入当前 bundle；
3. 达到 `rows_per_part` 就 finalize 并滚动下一个 bundle；
4. 处理 `row_align` 时，引入 `remainder sidecar`（可配置）：
   - 默认：`drop`（与现有行为兼容）；
   - 可选：写入 `remainder` 文件，不丢弃。

收益：

- 内存由 `O(rows_per_part * avg_row_size)` 降为 `O(1~小窗口)`。
- 对大图像场景更稳，减少峰值 RSS 抖动。

## 内存开销评估（定性）

若采用“有界队列 + 无大二进制入队 + 流式导出”，内存可控且通常低于当前大缓冲导出路径。

近似上界：

- `RSS增量 ≈ Q12*E1 + Q23*E2 + exporter_window + cache_window`
- 其中：
  - `E1/E2` 为单条中间对象大小（不含图像 bytes）；
  - `exporter_window` 为当前 writer 的小窗口；
  - `cache_window` 受 LRU/磁盘页缓存控制。

风险场景：

- 队列无界；
- export 阶段缓存图片 bytes；
- `rows_per_part` 过大且仍采用聚合列表写出。

## 兼容性与迁移

- 保持现有配置项：`training_rows_per_part`, `training_row_align`。
- 增加可选配置：
  - `pipeline_streaming_enabled`（默认 true，保留开关可回退）
  - `pipeline_queue_size`
  - `training_remainder_mode`（`drop` / `sidecar`）
  - `pipeline_cache`（`off` / `disk` / `memory_lru`）
- 默认行为：`pipeline_streaming_enabled=true` 与 `training_remainder_mode=drop`。

## 风险与缓解

1. 并行引入顺序一致性风险
   - 缓解：record_ref 驱动保序写；增加顺序性测试。
2. checkpoint 语义复杂化
   - 缓解：分阶段 checkpoint + 最终提交点；失败可重放。
3. 缓存脏数据
   - 缓解：签名化 key（配置+代码版本+输入签名）。

## 验证口径

1. 功能一致性：
   - 同输入下，QA 内容与训练导出内容在可接受等价范围内一致（顺序允许按策略定义）。
2. 性能：
   - 单 worker 吞吐提升（重点看端到端 rec/s 与阶段占比）。
3. 内存：
   - 峰值 RSS 可控，不随总样本量线性攀升。
4. 稳定性：
   - tqdm 显示不扰动；resume 后结果一致。

## 已确认决策

1. `training_remainder_mode` 默认 `drop`。
2. `pipeline_streaming_enabled` 默认开启（保留开关便于回退/灰度）。
3. 缓存首版只做 `disk`（跳过 `memory_lru`）以降低内存不确定性。
