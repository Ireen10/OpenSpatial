## 测试计划：CLI enrich 配置

### 测试项

- **UT-E1：默认兼容**
  - demo_dataset enrich 默认关闭
  - 断言：`pytest metadata/tests -q` 中 framework CLI 用例仍通过

- **UT-E2：relations_2d 开关生效**
  - 构造最小 record（两个 bbox objects）
  - 调用 CLI 内部 enrich 应用函数
  - 断言：输出 `aux.enrich_2d.stats` 存在，且 `relations` 数量符合预期（>=0，至少 aux 出现）

- **UT-E3：relations_3d 未实现时报错**
  - 构造 ds.enrich.relations_3d=true
  - 断言：CLI 启动/执行时报 ValueError

### 执行命令

- `python -m pytest metadata/tests -q`

