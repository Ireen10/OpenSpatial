## Change Log：viz I/O 优化（减少全量扫描）

### 本轮交付摘要

- **JSONL 行数缓存**：`count_lines_jsonl` 增加基于 `(resolved_path, mtime_ns, size)` 的缓存，避免同一文件重复计数时反复全量扫描。
- **training_lines 按需计数**：
  - `/api/training_lines` 新增 `with_count`（默认 `false`）。
  - 默认返回分页记录与 `has_more`，不再每次强制返回 `line_count`。
  - 仅 `with_count=true` 时返回 `line_count`（复用缓存计数）。
- **前端适配**：Training 视图默认请求 `with_count=false`，状态栏以分页信息为主；若后端返回总数则附加显示，不再阻塞首屏。
- **测试补强**：
  - `test_viz_paths.py` 新增行数缓存失效场景。
  - `test_viz_server.py` 新增 `training_lines` 在 `with_count=false/true` 两种模式下的行为验证。

### 自测

- `PYTHONPATH=metadata/src pytest -q metadata/tests/test_viz_paths.py metadata/tests/test_viz_server.py metadata/tests/test_viz_training_api.py`
- 结果：`7 passed`。

