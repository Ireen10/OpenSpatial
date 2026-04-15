## 执行计划：RefCOCO grounding 最小 E2E

### 1) 新增数据集配置与样例输入

- 新增目录：`metadata/configs/datasets/refcoco_grounding_aug_en_250618/`
- 新增 `dataset.yaml`：
  - `adapter.file_name: grounding_qa`
  - `adapter.class_name: GroundingQAAdapter`
  - `enrich.relations_2d: true`
  - split 输入指向 `sample_small.jsonl`
- 新增 `sample_small.jsonl`：一行即你提供的真实 record（不涉及 images 解包）

### 2) 让 global.yaml 生效（注入 adapter）

- 更新 `openspatial_metadata.cli`：
  - adapter factory 在 split 循环中构造，注入 `split.name` 与 `g.scale`
  - 仅当 adapter 构造函数支持对应参数时才传入（保证 passthrough 不受影响）

### 3) 端到端测试

- 新增 `metadata/tests/test_cli_e2e_refcoco_small.py`：
  - 用临时目录作为 output_root
  - 写一个临时 global.yaml，设置 `scale=777`、`batch_size=1`、`resume=false`
  - 用 CLI 跑该 dataset.yaml
  - 读取输出 jsonl，断言：
    - `sample.image.coord_scale == 777`
    - `aux.enrich_2d.stats` 存在
    - `objects/queries` 非空

### 4) 自测

- `python -m pytest metadata/tests -q`

### 5) 变更记录

- 本目录补 `change_log.md`

