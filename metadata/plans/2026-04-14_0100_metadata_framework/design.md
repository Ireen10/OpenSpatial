## 方案设计（Design）：`metadata/` 子项目工程框架（v0）

### 背景与目标

当前 `metadata/docs/` 已定义了 OpenSpatial Metadata v0（单视角）的核心概念与字段。我们需要把 `metadata/` 作为 OpenSpatial 的一个**子项目**工程化落地，使其能承载：

- **数据 → metadata 格式**：把来自不同数据源的样本转换为 metadata v0（JSON 结构）。
- **公司内部留档**：仅使用 `json` / `jsonl` 进行归档与交换（每 sample 一条 JSON/JSONL）。
- **（后续）对接 OpenSpatial**：当我们后续新增 QA 生产管线（annotation task）时，提供将 metadata 转为 OpenSpatial 所需 Parquet 的能力（本阶段仅预留接口，不实现具体字段映射）。
- **空间关系增强（enrichment）**：在 metadata 上派生/补全 2D/3D 空间关系字段，记录 evidence/source/score，便于回溯与筛选。

### 非目标（本次“工程框架”阶段不做）

- 不实现所有数据源的完整适配（仅定义接口与可扩展点）。
- 不承诺 3D 关系一定可几何复算（遵循 v0：允许人工标注 label 为主，几何证据可缺省）。
- 不在本阶段直接改动 OpenSpatial 主流水线；也不实现 metadata→OpenSpatial Parquet 的完整映射（仅保留导出接口占位）。

### 术语与约束

- **范围**：v0 仅单视角（singleview）。
- **参照系**：
  - 2D：`ref_frame=image_plane`
  - 3D：`ref_frame=egocentric`（front/behind 按“相机扶正后深度次序”定义；above/below 尽量重力意义）
- **工程约束**：
  - 子项目应可独立安装/运行（便于单测与复用）。
  - 与主工程边界清晰：metadata 子项目以“JSON 归档结构”为中心；如需与 OpenSpatial 工程对接，应通过可选适配器/映射实现（文档中属于建议，不是强依赖）。
- **工作流约束**：
  - 任何实现前必须先完成该目录下的 `plan.md` 与 `test_plan.md` 并对齐确认。

### 工程框架（目录与模块）

建议在 `metadata/` 下创建一个独立 Python 包（可编辑安装），并约定下列模块边界：

- `metadata/`
  - `docs/`：规范与 wiki（已存在）
  - `plans/`：方案/计划/测试/变更（已存在）
  - `configs/`：数据集转换配置（YAML/JSON），用于批量处理多个数据集与多分片文件
  - `src/openspatial_metadata/`（建议的包名，可调整）
    - `config/`
      - `schema.py`：配置结构定义（dataset 列表、split、分片文件模式、meta 信息等）
      - `loader.py`：加载/合并 config，展开 data_{000000..}.jsonl 之类的文件清单
    - `schema/`
      - `metadata_v0.py`：以“文档为准”的 v0 schema 定义（使用 pydantic；可逐步扩充字段，当前阶段仅建立框架与最小骨架）
      - `validate.py`：校验与一致性检查（必填字段、类型、id 引用一致性等）
    - `io/`
      - `json.py`：json/jsonl 读写（utf-8，确保可流式处理）
      - `parquet.py`：（预留）用于后续 OpenSpatial annotation task 的 Parquet 导出（本阶段不实现）
    - `adapters/`（数据源适配层）
      - `label_boxes_points.py`：（占位）面向一类常见“label + 区域/点集合 + 计数”等上游结构的 objects/queries 展开适配器。spec 3.3.1 给出的 `{label, boxes, points, count}` 仅作为**可支持的参考样例**，不将输入/输出结构限制死（后续实现）
      - `json_archive.py`：（占位）从“每 sample 一条 JSON/JSONL”的归档形式读入/写出（wiki 的主叙事；后续实现）
      - `openspatial_parquet_map.py`：（占位）metadata → OpenSpatial Parquet 的映射层（后续 QA/annotation 设计明确后实现）
    - `enrich/`
      - `relations_2d.py`：（占位）从 bbox/point/mask 生成 2D relations（image_plane）
      - `relations_3d.py`：（占位）从几何/人工标注生成或补全 3D relations（egocentric）
      - `provenance.py`：统一写入 `source/evidence/score` 与版本信息（可选）
    - `utils/`
      - `normalize.py`：坐标归一化/反归一化（以 w/h/scale 为参数）
      - `text.py`：空间词过滤/提取等工具（可选）
    - `viz/`
      - `__init__.py`：可视化模块占位（后续讨论实现）
    - `cli.py`：命令行入口（只做编排：读→转→增强→写）
  - `tests/`：单元测试与小样例 fixtures（用最小样本覆盖接口契约）

### 核心接口契约（框架级）

#### 1) 统一内部表示

- 内部统一使用 metadata v0 的 Python 对象（或 dict），其字段语义与 `metadata/docs/metadata_spec_v0_zh.md` 对齐。
- `source/evidence/score` 属于**可选字段**：增强结果“推荐”写入以便追溯，但不是强制要求（允许缺省）。
- `object_id/query_id` 的生成与稳定性：建议在 schema 内提供统一的内部方法（类方法/静态方法）生成 id，避免散落在 utils 中，风格类似 OpenSpatial 中的 `_format_task_ref(...)`（见 `pipeline/base_pipeline.py`）。v0 单视角阶段默认只要求 **sample 内唯一/稳定**，不要求跨数据集全局统一。

#### 2) 导入（Ingest）

- `from_json(sample: dict) -> MetadataV0`（wiki：每 sample 一条 JSON/JSONL）
- `from_label_boxes_points(item: dict) -> (objects, query)`（spec 3.3.1：明确给出的上游结构；或直接返回一个 MetadataV0 片段）
- （可选）`from_openspatial_parquet_row(example: dict) -> MetadataV0`（spec 第 5 节：与 OpenSpatial parquet 工程形态的“映射建议”，非强依赖）

#### 3) 增强（Enrich）

- `enrich_relations_2d(md) -> md'`
- `enrich_relations_3d(md) -> md'`
- 支持配置：
  - 阈值/平局处理（tie）
  - 证据计算方法选择（bbox center / point / mask centroid）

#### 4) 导出（Persist / Export）

- `write_json / write_jsonl`
- （占位）`export_openspatial_annotation_parquet(...)`
  - 仅保留接口；暂不实现。等待后续 QA/annotation 管线设计时明确所需字段与表结构。

### 错误处理与降级策略（框架级约定）

- **输入字段缺失**：
  - 导入阶段：允许缺失几何字段（camera/depth/obb/pointcloud），但必须保留 `objects` 与最小 `sample.image.path`。
- **关系增强条件不足**：
  - 2D：无 bbox/point 时跳过该对象的 2D 关系生成。
  - 3D：无几何证据时仅保留人工标注关系（若存在）；否则不生成 computed 3D 关系。
- **一致性**：
  - `relations.anchor_id/target_id` 必须引用存在的 `object_id`；不满足则作为验证错误（是否 hard-fail 待定）。

### 风险与未决问题（需要你确认）

1. **schema 实现方式（dataclass vs pydantic）**：需要选型（见下文“评估”）。
2. **内部留档格式**：已确定仅 `json/jsonl`（parquet 不用于内部留档）。
3. **Parquet 导出形态（用于后续 OpenSpatial annotation）**：你已选择方案 B（拆列；object 和 relation 不耦合在同一列中）。本阶段仅保留导出接口占位，不实现。
4. **坐标归一化**：需要在 `utils` 内置归一化与反归一化方法，`w/h/scale` 以及归一化范围作为参数传入（已确定）。

### dataclass vs pydantic 评估（已决策：选择 pydantic）

**dataclass（+手写 validate）**
- 优点：依赖轻；结构直观；运行快；适合“内部表示 + 轻量约束”。
- 风险：校验与序列化细节需要自己维护；字段可选/默认/类型转换更容易不一致；错误信息可读性一般。

**pydantic**
- 优点：对 JSON/JSONL 输入更稳健（类型转换、默认值、错误定位）；可更方便地做校验（例如引用一致性、字段范围）；更适合“多数据源脏输入”场景。
- 风险：引入依赖；模型层可能更“重”；需要约束版本与配置以避免行为漂移。

**决策**：选择 **pydantic**，以获得更稳健的 JSON/JSONL 导入、类型转换与错误报告能力，适配多数据集、多分片、数据质量参差的现实输入。

