## 执行计划：CLI enrich 配置

### 修改范围

- `metadata/src/openspatial_metadata/cli.py`
  - 解析 `ds.enrich` 配置
  - 在写出前执行 2D enrich（按开关）
- `metadata/configs/datasets/demo_dataset/dataset.yaml`
  - 显式写 `enrich: {relations_2d: false, relations_3d: false}`（示例 + 防误触发）
- 测试：
  - 新增 `metadata/tests/test_cli_enrich_config.py`（或在 framework unittest 中补充）

### 实施步骤

1. 在 CLI 增加 helper：
   - `_get_enrich_flags(ds) -> (bool, bool)`
   - `_apply_enrich_if_enabled(out_dict, flags) -> out_dict`

2. 在 `main()` 中：
   - 读取 flags
   - 若 `relations_3d=true` 直接报错（未实现）
   - 在 `_apply_adapter` 之后、写出前调用 `_apply_enrich_if_enabled`

3. 更新 demo dataset.yaml：
   - 增加 enrich 块（默认 false）

4. 测试：
   - UT：启用 2D enrich 时，输出 dict 中出现 `aux.enrich_2d` 结构
   - 回归：`pytest metadata/tests -q`

5. 完成后写 `change_log.md`

