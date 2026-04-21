## 实施计划

基于已确认的设计，本轮按“先低风险可落地，再扩展能力”的策略分三批实施。

---

## 批次 P2-A（优先落地）

目标：先解决内存峰值与导出缓冲问题，不改整体 pipeline 编排。

### A1. 训练导出改流式分包（替换大 buffer）

1. 在 `export/training_pack.py` 引入“当前 bundle writer”滚动机制：
   - 每条样本到达即写入当前 bundle；
   - 达到 `rows_per_part` 即 finalize 并切换下一个 bundle。
2. 移除“积攒 `rows_per_part` 大列表再统一写”的主路径。
3. 保持 `rows_per_part % row_align == 0` 的现有约束不变。

### A2. 尾部 remainder 处理可配置

1. 增加配置项 `training_remainder_mode`：
   - `drop`（默认，与现有行为兼容）
   - `sidecar`（可选）
2. `sidecar` 模式下将尾部不足对齐样本写入 sidecar 文件（供后续拼接或下一轮消费）。

### A3. 验证与回归

1. 保证导出结果结构不变：`images/*.tar + jsonl/*.jsonl + tarinfo`。
2. 新增用例覆盖：
   - 分包边界滚动；
   - `row_align` 尾部处理（drop/sidecar）。

---

## 批次 P2-B（中风险）

目标：引入阶段流水并行，但严格有界、可回退。

### B1. 增加流水并行开关与队列参数

1. 新增配置：
   - `pipeline_streaming_enabled`（默认 `true`，可手动关闭回退）
   - `pipeline_queue_size`（默认 `2 * effective_workers`，最小 1）
2. 当开关关闭时，保持现有串行行为完全不变（用于灰度/回退）。

### B2. 单进程内三阶段有界流水

1. Stage-1: `to_metadata`
2. Stage-2: `ensure_qa`
3. Stage-3: `export_training`

要求：

- 阶段间使用有界队列；
- 队列元素只传轻量 envelope（不传图片 bytes）；
- 保序与 checkpoint 语义不退化。

### B3. 失败与恢复

1. 任一阶段异常可中止整条流水并输出可诊断信息；
2. resume 语义保持与当前一致（至少不弱化）。

---

## 批次 P2-C（可选增强）

目标：共享中间表示 + 轻量缓存，进一步减少重复反序列化。

### C1. 共享中间表示（RecordEnvelope）

1. 在阶段间优先传递模型对象（或轻量引用）；
2. 仅在持久化或跨边界时 materialize payload。

### C2. 缓存（默认关闭）

1. 首版只做 `disk` 缓存（签名化 key）；
2. `memory_lru` 暂不默认启用，避免引入内存不确定性。

---

## 配置与兼容策略

1. 默认策略：
   - `pipeline_streaming_enabled=true`
   - `training_remainder_mode=drop`
2. 仍保留显式开关，支持灰度禁用/快速回退。

---

## 交付顺序

1. 先完成 P2-A（流式导出 + remainder）并上线；
2. 再做 P2-B（流水并行开关）；
3. 最后评估是否启用 P2-C（缓存）。

这样可以确保每一步都有明确性能收益，同时将内存风险控制在可观测范围内。

---

## 已确认默认值

1. `training_remainder_mode=drop`。
2. `pipeline_streaming_enabled=true`（开关保留，用于灰度控制）。
