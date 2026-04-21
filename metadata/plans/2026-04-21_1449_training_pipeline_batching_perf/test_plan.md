## 测试方案（Test Plan）：training_pipeline_batching_perf

### 测试范围

- 覆盖范围：
  - training pipeline 的 batch 写盘与 checkpoint 频率。
  - `persist_noqa=false` 时无效 `noqa` dump 的消除。
- 不覆盖范围：
  - 业务结果语义变更（本轮不改输出内容）。

### 单元测试

- 用例列表：
  - 新增 `tests/test_training_pipeline_batching_perf.py`
  - 现有 `tests/test_training_pipeline_cli_e2e.py`
  - 现有 `tests/test_records_parallelism_order.py`
- 输入构造：
  - 使用最小合法 metadata 行并重复构造小样本 jsonl。
- 断言点：
  - checkpoint 次数与 batch flush 对齐（非逐条）。
  - `persist_noqa=false` 且无 QA 输出时，`_md_dump` 不为 `noqa` 触发。

### 集成测试

- 与 OpenSpatial 的对接点：
  - `main()` 驱动的 training pipeline E2E。
- 需要的样例 Parquet / JSON：
  - 复用 `metadata/tests/fixtures/generated/spatial_relation_2d/*.jsonl`
- 预期输出与检查方式：
  - `metadata_qa` / training bundle 输出保持可用；
  - 全量测试通过。

### 质量门槛（Gate）

- 通过条件：
  - 新增测试 + 相关回归 + metadata 全量 `pytest` 通过。
- 失败时如何定位：
  - checkpoint 异常优先看 `cli.py` 中 pending flush 逻辑；
  - dump 次数异常优先看 `persist_noqa` 分支下 payload 组装时机。
