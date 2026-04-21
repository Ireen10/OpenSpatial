## 实施计划

基于已对齐的设计，本批按 P0/P1 一次性落地“固定开销优化”，不做架构级重写。

### P0-1 早短路（QA 前置）

1. 在 `spatial_relation_2d` 生成入口添加更早返回：
   - `objects` 为空时直接返回；
   - `relations` 为空时直接返回；
   - `sub_tasks` 计划总需求为 0 时直接返回。
2. 在 `qa_tasks.build_qa_items` 中增加 task 级“最小可执行条件”检查（先覆盖 `spatial_relation_2d`）：
   - 若 metadata 不满足最小输入条件，直接返回空列表，避免加载/执行下游生成逻辑。

### P0-2 去除 ensure_qa 内部冗余 dump/validate

1. 在 `utils/pydantic_compat.py` 新增跨 Pydantic v1/v2 的“浅拷贝+字段更新”兼容函数。
2. 在 `cli._process_jsonl_file_training_pipeline` 的 `_build_metadata_views` 中：
   - 现状：`build_qa_items -> md_dump -> 注入qa_items -> md_validate`
   - 目标：`build_qa_items -> model_copy(update={"qa_items": items})`
3. 保持 `md_noqa` / `md_qa` 对外语义不变；仅减少中间序列化和反序列化。

### P1-1 写入序列化的复用与条件化

1. 在训练流水 `_enqueue_payloads` 路径保持“仅在需要落盘时 dump”。
2. 在 `persist_noqa=false` 且无 `qa_items` 场景下，确保不会触发无意义 dump。

### P1-2 测试增强与回归保护

1. 为 `spatial_relation_2d` 新增“空 objects/relations 早返回”测试。
2. 为训练流水新增“ensure_qa 为空结果时不触发内部冗余 dump”的测试。
3. 保留并复用现有 batching/resume/tqdm 相关测试，确认无回退。

### 非本批实现（保留到后续）

- `noqa -> qa -> export` 跨阶段流水并发；
- 阶段间共享中间表示的大规模改造；
- records_parallelism 自适应策略。
## 实施计划

基于已对齐的设计，本批按 P0/P1 一次性落地“固定开销优化”，不做架构级重写。

### P0-1 早短路（QA 前置）

1. 在 `spatial_relation_2d` 生成入口添加更早返回：
   - `objects` 为空时直接返回；
   - `relations` 为空时直接返回；
   - `sub_tasks` 计划总需求为 0 时直接返回。
2. 在 `qa_tasks.build_qa_items` 中增加 task 级“最小可执行条件”检查（先覆盖 `spatial_relation_2d`）：
   - 若 metadata 不满足最小输入条件，直接返回空列表，避免加载/执行下游生成逻辑。

### P0-2 去除 ensure_qa 内部冗余 dump/validate

1. 在 `utils/pydantic_compat.py` 新增跨 Pydantic v1/v2 的“浅拷贝+字段更新”兼容函数。
2. 在 `cli._process_jsonl_file_training_pipeline` 的 `_build_metadata_views` 中：
   - 现状：`build_qa_items -> md_dump -> 注入qa_items -> md_validate`
   - 目标：`build_qa_items -> model_copy(update={"qa_items": items})`
3. 保持 `md_noqa` / `md_qa` 对外语义不变；仅减少中间序列化和反序列化。

### P1-1 写入序列化的复用与条件化

1. 在训练流水 `_enqueue_payloads` 路径保持“仅在需要落盘时 dump”。
2. 在 `persist_noqa=false` 且无 `qa_items` 场景下，确保不会触发无意义 dump。

### P1-2 测试增强与回归保护

1. 为 `spatial_relation_2d` 新增“空 objects/relations 早返回”测试。
2. 为训练流水新增“ensure_qa 为空结果时不触发内部冗余 dump”的测试。
3. 保留并复用现有 batching/resume/tqdm 相关测试，确认无回退。

### 非本批实现（保留到后续）

- `noqa -> qa -> export` 跨阶段流水并发；
- 阶段间共享中间表示的大规模改造；
- records_parallelism 自适应策略。
