## 测试计划（Test Plan）：viz I/O 优化（减少全量扫描）

对应 `plan.md`。

## T1 行数缓存

- **T1a**：同一 JSONL 文件重复调用 `count_lines_jsonl`，结果正确且可复用缓存。
- **T1b**：文件内容变更后（mtime/size 变化），`count_lines_jsonl` 能自动失效并返回新行数。

## T2 training_lines 分页行为

- **T2a**：`/api/training_lines` 在默认（`with_count=false`）下返回：
  - `records`
  - `offset` / `limit`
  - `has_more`
  且不依赖 `line_count`。
- **T2b**：`/api/training_lines?with_count=true` 返回 `line_count`，并与实际行数一致。
- **T2c**：翻页请求（仅 offset 变化）响应稳定，不因总数统计导致明显变慢。

## T3 前端训练视图回归

- **T3a**：Training 模式默认加载成功，即使响应中无 `line_count` 也可正常浏览。
- **T3b**：状态栏显示分页信息；当后端返回 `line_count` 时可附加显示 total。
- **T3c**：Prev/Next 与 offset 输入跳转行为保持不变。

## T4 基础回归

- **T4a**：Metadata 模式接口不回归：`/api/tree`、`/api/record`、`/api/image` 正常。
- **T4b**：Training 图片读取接口 `/api/training_image` 行为不变。

## 执行命令

```powershell
$env:PYTHONPATH="metadata/src"
pytest -q metadata/tests/test_viz_paths.py metadata/tests/test_viz_server.py metadata/tests/test_viz_training_api.py
```

必要时补充手测：

```powershell
$env:PYTHONPATH="metadata/src"
python -m openspatial_metadata.viz --config-root metadata/tests/configs/e2e_training_pipeline/datasets --global-config metadata/tests/configs/e2e_training_pipeline/global.yaml --output-root metadata/tests/.tmp_pipeline_out/metadata
```

