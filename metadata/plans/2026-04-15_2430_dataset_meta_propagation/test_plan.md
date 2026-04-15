## 测试计划：dataset meta 贯通

### 测试项

- **UT-M1：dataset.source 注入**
  - 输入输出未提供 `dataset.source`
  - dataset.yaml 的 `meta.source` 存在
  - 断言：输出 `dataset.source` 被补齐

- **UT-M2：dataset.meta 保留**
  - `ds.meta` 有多个键
  - 断言：输出 `dataset.meta` 包含这些键（不要求固定 schema）

- **E2E-M1：refcoco 小样例输出包含 source**
  - 跑 `test_cli_e2e_refcoco_small.py`
  - 断言：输出 `dataset.source == "local_fixture"`

### 执行命令

- `python -m pytest metadata/tests -q`

