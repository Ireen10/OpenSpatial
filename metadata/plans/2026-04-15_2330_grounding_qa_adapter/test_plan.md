## 测试计划：`GroundingQAAdapter`

### 测试项

- **UT-A1：Grounding 标记解析**
  - 输入：一个最小 record dict（含 image + 两轮 assistant grounding 文本）
  - 断言：
    - `sample.image.path/width/height` 解析正确
    - `queries` 数量为 2（两次 ref）
    - `objects` 数量为 2（两次 box）
    - 每个 query 的 `candidate_object_ids` 数量与 box 数量一致

- **UT-A1b：ref → 多 box**
  - 输入：单条 assistant 文本中同一 `ref_exp` 后紧跟多个 `<|box_start|>...<|box_end|>`
  - 断言：
    - 产出 1 条 query 且 `count == N`
    - 产出 N 个 objects 且 bbox 顺序与文本一致
    - `gold_object_id` 不应填写（多实例）

- **UT-A1c：ref-only / box-only 跳过**
  - 输入：
    - 只有 `<|object_ref_start|>...<|object_ref_end|>`、无 box
    - 只有 `<|box_start|>...<|box_end|>`、无 ref
  - 断言：均不产出 objects/queries（安全跳过）

- **UT-A1d：多轮对话重复/冲突组合（当前不去重）**
  - 输入覆盖：
    - 不同轮次出现 **同 ref 同 box**
    - 不同轮次出现 **不同 ref 同 box**
    - 不同轮次出现 **同 ref 不同 box**
  - 断言：当前实现不做去重/合并，按出现次数展开为多个 queries/objects

- **UT-A2：CLI 调用 adapter 不回归**
  - 运行现有 framework CLI 测试
  - 断言：输出仍包含 `aux.record_ref`

### 执行命令

- `python -m pytest metadata/tests -q`

### 通过标准

- 所有测试通过
- adapter 与 CLI 集成有效（UT-A1 覆盖核心解析路径）

