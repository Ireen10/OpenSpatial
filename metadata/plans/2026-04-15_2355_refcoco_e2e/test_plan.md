## 测试计划：RefCOCO grounding 最小 E2E

### 测试项

- **E2E-1：config→read→convert→enrich→write**
  - 输入：`refcoco_grounding_aug_en_250618/sample_small.jsonl`
  - 配置：`enrich.relations_2d=true`
  - 断言：输出 jsonl 中 `aux.enrich_2d` 存在，且 `relations`/`objects`/`queries` 字段存在

- **E2E-2：global.yaml.scale 注入 adapter**
  - global.yaml: `scale=777`
  - 断言：输出 `sample.image.coord_scale == 777`

### 执行命令

- `python -m pytest metadata/tests -q`

