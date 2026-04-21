## 变更摘要

完成 P2 首轮实现（P2-A + 配置接线）：训练导出支持默认开启的流式写出路径，并保留可回退开关；`row_align` 尾部处理新增 `training_remainder_mode`（本轮默认 `drop`）。

## 代码变更

1. `metadata/src/openspatial_metadata/export/training_pack.py`
   - 新增流式导出路径：
     - `_iter_training_items_from_metadata_qa`
     - `_export_streaming_writer`
   - 保留并封装旧的缓冲聚合路径：
     - `_export_buffered_legacy`
   - 增加参数：
     - `pipeline_streaming_enabled: bool = True`
     - `training_remainder_mode: str = "drop"`
   - 支持 `drop/sidecar` 两种 remainder 策略（本轮默认 `drop`）。
   - `export_training_bundles_for_split` 透传上述新参数。

2. `metadata/src/openspatial_metadata/cli.py`
   - `_training_pack_settings` 扩展为返回：
     - `rows_per_part`, `row_align`, `pipeline_streaming_enabled`, `training_remainder_mode`
   - pipeline 日志补充新导出开关与 remainder 模式信息。
   - `_finalize_training_export_for_split` 增加新参数并传递到导出层。
   - 更新 pipeline 注释说明可覆盖键集合。

3. `metadata/src/openspatial_metadata/config/schema.py`
   - `GlobalConfig` 新增字段：
     - `pipeline_streaming_enabled: bool = True`
     - `training_remainder_mode: str = "drop"`

## 测试变更

1. 新增 `metadata/tests/test_training_export_streaming_modes.py`
   - `pipeline_streaming_enabled=true/false` 两路径行级等价性测试。
   - `training_remainder_mode=drop` 下尾部丢弃行为测试。

2. 更新 `metadata/tests/test_training_pipeline_batching_perf.py`
   - 新增 `_training_pack_settings` 默认值与 pipeline 覆盖值测试。

3. 回归验证通过（见下方）。

## 文档变更

1. `metadata/docs/config_yaml_zh.md`
   - 新增全局与 pipeline 级导出参数说明：
     - `pipeline_streaming_enabled`
     - `training_remainder_mode`
   - 更新训练 pipeline 描述为“默认流式导出 + 可回退”语义。

## 自测记录

- `python -m pytest metadata/tests/test_training_export_streaming_modes.py -q` ✅
- `python -m pytest metadata/tests/test_training_export_shard_progress.py -q` ✅
- `python -m pytest metadata/tests/test_training_pipeline_batching_perf.py -q` ✅
- `python -m pytest metadata/tests/test_training_pipeline_cli_e2e.py -q -k "training_pipeline_cli_e2e or multi_bundle"` ✅

> 说明：仍有既有 Pydantic v2 deprecation warnings（历史问题），本轮未新增失败。
