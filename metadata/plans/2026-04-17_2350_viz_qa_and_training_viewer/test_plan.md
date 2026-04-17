## 测试计划（Test Plan）：viz 兼容 QA metadata 与 training bundle

对应 `plan.md` 任务拆解。

## T0 配置接线

- **T0a**：启动 viz 时传入 `--qa-config`，访问 `/api/config` 能看到 `qa_config_path` 回显。

## T1 tree 枚举

- **T1a**：`/api/tree` 的 metadata 列表包含：
  - `{dataset}/{split}/metadata_noqa/*.metadata.jsonl`
  - `{dataset}/{split}/metadata_qa/*.metadata.jsonl`
- **T1b**：`/api/tree` 的 training 列表包含 `{dataset}/{split}` 下的 `part_000000`（若 bundle 存在）。

## T2 training API

- **T2a**：`/api/training_record` 返回 JSON 可解析，且包含 `data[0].content[0].image.relative_path`。
- **T2b**：`/api/training_image` 能返回 200，且浏览器可显示为图片（content-type 合理）。
- **T2c**：`/api/training_lines` 在 `limit=50` 时响应体大小可控（不随 part 全量线性增长），且能返回 `line_count`。

## T3 UI 回归（手测）

- **T3a**：Metadata 模式下，Objects/Relations overlay 正常；新增 QA tab 能显示 `qa_items`。
- **T3b**：Training 模式下，能按行 Prev/Next，能显示对话文本与图片。
- **T3c**：Training 模式下切换 part 时不出现明显卡顿/内存爆涨（不一次性渲染整 part 的所有行）。

## 执行命令

使用测试配置产物（或你本地跑出来的 `.tmp_pipeline_out`）：

```powershell
$env:PYTHONPATH="metadata/src"
python -m openspatial_metadata.viz --config-root metadata/tests/configs/e2e_training_pipeline/datasets --global-config metadata/tests/configs/e2e_training_pipeline/global.yaml --qa-config metadata/tests/configs/e2e_training_pipeline/qa_tasks.yaml --output-root metadata/tests/.tmp_pipeline_out/metadata
```

然后在浏览器打开 `http://127.0.0.1:8765/`，并用 Network/Console 验证上述接口。

