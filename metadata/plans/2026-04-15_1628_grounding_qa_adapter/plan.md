## 执行计划：实现 `GroundingQAAdapter`

### 修改范围

- **新增 adapter**
  - `metadata/src/openspatial_metadata/adapters/grounding_qa.py`
- **CLI 集成 adapter**（当前 CLI 只 passthrough record，不调用 adapter）
  - `metadata/src/openspatial_metadata/cli.py`
  - （可选）小幅调整 `metadata/src/openspatial_metadata/config/loader.py`/`schema.py` 不需要
- **测试**
  - 新增 `metadata/tests/test_adapter_grounding_qa.py`
  - 更新 `metadata/tests/test_framework_unittest.py`（如果 CLI 输出结构因调用 adapter 而变化）

### 实施步骤

1. **实现 `GroundingQAAdapter`**
   - `convert(record: Dict) -> Dict` 输出满足 `MetadataV0` 形状
   - 解析：
     - 从 `data[*].content[*]` 抽取第一张 image 的 `relative_path/width/height`
     - 从 assistant 的 text 中解析 `<|object_ref_start|>...<|object_ref_end|>` 与紧随的 `<|box_start|>(x1,y1),(x2,y2)<|box_end|>`（支持多个 box）
   - 跳过规则：ref 无 box / box 无 ref → 跳过
   - `aux` 写入 `adapter_name`、`adapter_stats`、`adapter_warnings`

2. **在 CLI 中调用 adapter**
   - 根据 `ds.adapter` 动态 import 并实例化 adapter（无参构造）
   - 对每条输入 record：
     - `out = adapter.convert(record)`（若无 adapter 则 `out = dict(record)`）
     - 统一补齐 `aux.record_ref`（保持现有测试/审计能力）
   - 保持与现有输出写入/批处理/检查点逻辑兼容

3. **测试**
   - **UT-A1（adapter 解析）**：用 README 真实样例裁剪出的最小 record dict：
     - 断言解析出 `sample.image.*`，`queries` 数量与 bbox 数量正确
     - 断言 bbox 数值与文本一致
   - **UT-A2（CLI 不回归）**：跑 `TestFramework.test_cli_io` 确认仍能输出并带 `aux.record_ref`

4. **自测**
   - `python -m pytest metadata/tests -q`

5. **变更记录**
   - 补 `change_log.md`（实现与测试结果）

### 完成标准

- CLI 能真正使用 `adapter` 将输入转为 `MetadataV0` shape
- `GroundingQAAdapter` 单测通过
- `pytest metadata/tests -q` 全绿

