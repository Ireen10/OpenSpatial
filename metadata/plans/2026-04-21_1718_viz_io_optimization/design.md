## 设计（Design）：viz 避免全量扫描导致的慢加载

### 背景

当前 `openspatial-metadata-viz` 虽然不是“一次性把全文件读入内存”，但在关键 API 上存在多处 **每次请求都线性扫完整个 JSONL** 的路径：

- `/api/record`：读取目标行后，还会再次全量扫描统计 `line_count`
- `/api/training_lines`：为返回 `line_count`，会遍历整文件
- `/api/seek`：按 `sample_id` 查找时逐行解析 JSON（O(N)）

在大文件场景下，这会表现为页面长时间无响应或“像卡住”。

### 目标

在不改变现有数据格式（JSONL / tar / tarinfo）和现有 API 语义的大前提下，优先落地低风险优化：

1. **减少重复全量扫描**（先做）
2. **避免接口强依赖总行数**（先做）
3. 后续可演进到索引化随机访问（本轮不实现）

### 范围（本轮实施）

#### A. 行数缓存（line_count cache）

- 在 `viz/paths.py` 增加轻量缓存（基于 `path + mtime + size`）
- 命中缓存时，`count_lines_jsonl` 直接返回缓存值，不再重扫文件
- 文件变更后自动失效（mtime/size 变化）

#### B. `training_lines` 降级为“分页优先”

- `/api/training_lines` 增加可选参数（例如 `with_count`，默认 `false`）
- 默认只返回：
  - `records`
  - `offset / limit`
  - `has_more`
- 仅在显式请求 `with_count=true` 时才返回 `line_count`（可能触发扫描）
- 前端 training 面板默认不依赖总行数，避免每次翻页都触发全量计数

### 不在本轮范围

- 不改 metadata `/api/record` 的响应结构（仍兼容现有 UI）
- 不实现 `sample_id -> line` 索引 sidecar
- 不改训练 tar 读取逻辑（当前按 offset/size 切片已是按需读取）

### 兼容性与风险

- **向后兼容**：默认行为保持可用；若前端仍读取 `line_count`，后端可返回 `null` 或仅在 `with_count=true` 提供
- **风险点**：
  - 缓存键设计不当可能返回过期值（通过 mtime+size 规避）
  - 前后端字段变更需要一起调整（重点回归 training 分页状态栏）

### 验收标准

1. 大 JSONL 下，training 翻页不再因重复计数而明显卡顿
2. 同一文件重复访问时，`line_count` 计算可复用缓存
3. 功能语义不变：记录读取、图片读取、路径安全校验均保持原行为

