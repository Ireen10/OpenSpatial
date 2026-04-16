## 执行计划：dataset meta 贯通

### 修改范围

- `metadata/src/openspatial_metadata/cli.py`
  - 新增 `_apply_dataset_meta(out, ds, split_name)` 并在写出前调用
- 测试
  - 新增 `metadata/tests/test_cli_dataset_meta.py`
  - 更新 `metadata/tests/test_cli_e2e_refcoco_small.py` 断言 `dataset.source`
- 文档
  - 本目录补 `test_plan.md` / `change_log.md`

### 实施步骤

1. CLI 增加合并逻辑
   - 确保 `out["dataset"]` 是 dict（否则创建）
   - 若缺失 `name/version/split` 则补齐（来自 `ds.name` / 固定 v0 / split.name）
   - 若缺失 `source` 且 `ds.meta.source` 存在则补齐
   - 写入 `dataset.meta = ds.meta`（不覆盖已有 `dataset.meta`，或以输出优先）

2. 单测覆盖
   - `ds.meta={"source":"x","notes":"y"}` → 输出 `dataset.source=="x"` 且 `dataset.meta.notes=="y"`

3. E2E 更新
   - refcoco 输出断言 `dataset.source == "local_fixture"`

4. 自测
   - `python -m pytest metadata/tests -q`

