## 测试计划：`GroundingQAAdapter`

### 测试项

- **UT-A1：Grounding 标记解析**
  - 输入：一个最小 record dict（含 image + 两轮 assistant grounding 文本）
  - 断言：
    - `sample.image.path/width/height` 解析正确
    - `queries` 数量为 2（两次 ref）
    - `objects` 数量为 2（两次 box）
    - 每个 query 的 `candidate_object_ids` 数量与 box 数量一致

- **UT-A2：CLI 调用 adapter 不回归**
  - 运行现有 framework CLI 测试
  - 断言：输出仍包含 `aux.record_ref`

### 执行命令

- `python -m pytest metadata/tests -q`

### 通过标准

- 所有测试通过
- adapter 与 CLI 集成有效（UT-A1 覆盖核心解析路径）

