## 测试计划：2D relation containment 过滤

### 测试项

- **UT-C1（containment 过滤）**
  - 构造：一个大框 + 一个小框，小框几乎完全位于大框内部（覆盖率 ≥70%）
  - 期望：
    - `relations` 不产生
    - `aux.enrich_2d.dropped_relation_candidates` 中包含 `reason == "containment"`
  - 额外约束：选择位置让 `near_center` 不成为主要原因（避免测试不稳定）

### 执行命令

- `python -m pytest metadata/tests -q`

### 通过标准

- 所有测试通过
- UT-C1 稳定触发 containment 丢弃

