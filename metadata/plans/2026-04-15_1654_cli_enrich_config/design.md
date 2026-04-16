## 设计：在 dataset.yaml 中配置关系增强（enrich）

### 背景

当前 CLI 流程是：读取输入 record →（可选）adapter.convert → 写出 jsonl/json_files。  
关系增强（2D/3D）尚未接入 CLI，因此无法用“真实数据完整链路”跑通：config→读取→转换→增强→保存。

### 目标

- 在每个数据集的 `dataset.yaml` 中允许配置是否执行关系增强：
  - `enrich.relations_2d: bool`
  - `enrich.relations_3d: bool`
- CLI 在写出前按开关执行增强：
  - `relations_2d=true`：对每条 record 解析为 `MetadataV0` 并运行 `enrich_relations_2d`
  - `relations_3d=true`：当前仓库尚无 3D enrich 实现，本次先落配置与解析，执行时给出清晰错误或跳过策略
- 保持向后兼容：不写 `enrich` 时默认全关，不影响现有 demo 测试

### 配置形状

在 `dataset.yaml` 顶层新增：

```yaml
enrich:
  relations_2d: true
  relations_3d: false
```

### 执行位置与数据形状

- 执行时机：`adapter.convert(record)` 之后、写出前。
- 输入/输出：以 dict 形态在 CLI 内流转；当启用 enrich 时：
  - `MetadataV0.parse_obj(out_dict)`
  - `md2 = enrich_relations_2d(md1)`
  - `out_dict = md2.dict()`
- `aux.record_ref`：仍由 CLI 注入；应确保 enrich 后仍保留。

### 错误策略

- `relations_2d=true`：
  - 若 record 不满足 `MetadataV0` 或缺少几何，`enrich_relations_2d` 可能抛错；当前 CLI 的 `strict` 预留但未实现 per-record 策略，本次保持“异常即失败并退出”（与现有 worker 异常策略一致）。
- `relations_3d=true`：
  - 本次落配置解析，但由于缺少实现，先在 CLI 启动时直接 `ValueError("relations_3d enrich not implemented")`，避免用户误以为已生效。

### 测试

- **UT-E1（默认兼容）**：demo_dataset 不配置 enrich 或显式关闭 → framework CLI 测试仍通过
- **UT-E2（开关生效）**：构造一个最小 `DatasetConfig`（或最小 record）走 `_apply_enrich_if_enabled`，断言当 `relations_2d=true` 时产出 `aux.enrich_2d` 与可能的 relations

