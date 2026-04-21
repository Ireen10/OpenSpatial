## 执行计划（Plan）：viz I/O 优化（减少全量扫描）

依据：`design.md`。

## 交付物清单

- 文档：本目录 `design.md`、`plan.md`、`test_plan.md`；实现后补 `change_log.md`。
- 代码：
  - `metadata/src/openspatial_metadata/viz/paths.py`
  - `metadata/src/openspatial_metadata/viz/server.py`
  - `metadata/src/openspatial_metadata/viz/static/index.html`
- 测试：
  - 增加/更新 `metadata/tests/test_viz_*` 中与 `training_lines`、计数逻辑相关用例
  - 必要时补充针对缓存失效与分页行为的单测

## 任务拆解

### 任务 1：为 JSONL 行数统计增加缓存

- 在 `viz/paths.py` 为 `count_lines_jsonl` 增加进程内缓存：
  - 缓存键：`(resolved_path, stat.st_mtime_ns, stat.st_size)`
  - 缓存值：`line_count`
- 文件变化时自动失效（键变化即失效），避免返回过期计数。
- 保持原函数签名，确保调用方无感升级。

### 任务 2：`/api/training_lines` 默认不强制总行数

- 在 `viz/server.py` 的 `/api/training_lines` 支持 `with_count` 参数（布尔，默认 `false`）。
- 当 `with_count=false`：
  - 仅返回分页记录、`offset/limit`、以及 `has_more`（通过 `len(records)` 与窗口边界推断）。
  - 不触发完整行数统计。
- 当 `with_count=true`：
  - 复用 `count_lines_jsonl`（带缓存）返回 `line_count`。

### 任务 3：前端 training 视图适配新返回结构

- 调整 `viz/static/index.html`：
  - training 模式默认请求 `with_count=false`
  - 状态栏从“强依赖 total”改为“分页信息优先”
  - 若后端返回 `line_count` 再显示 total；无则不阻塞 UI
- 保持现有翻页与 offset 行为一致，避免交互回归。

### 任务 4：测试与回归

- 覆盖点：
  - `count_lines_jsonl` 缓存命中/失效（文件内容变更后重新统计）
  - `/api/training_lines` 在 `with_count=false` 时不要求 `line_count`
  - `/api/training_lines` 在 `with_count=true` 时返回 `line_count`
- 回归验证：
  - metadata 浏览不受影响（`/api/tree`、`/api/record`、`/api/image`）
  - training 浏览首屏更快，分页不依赖完整计数

## 完成条件

1. 大 JSONL 下 training 分页请求不再每次做全量计数扫描。
2. 有需要时仍可通过 `with_count=true` 获取总行数。
3. 现有 viz 功能与 API 兼容，测试通过。

