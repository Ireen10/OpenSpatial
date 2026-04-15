# OpenSpatial Metadata（子项目 v0）

`metadata/` 是 OpenSpatial 仓库里的**独立 Python 包**：用 YAML 配置驱动批量处理数据集，对 JSON / JSONL 做流式读写与 checkpoint，并提供 v0 metadata 的 Pydantic 模型与少量工具函数。

## 当前已实现 vs 规划中

**已实现（本阶段工程框架）：**

- 数据集配置：`configs/` 下一数据集一 YAML；`openspatial-metadata` 支持 `--config-root`（目录或单个文件）。
- JSONL：按输入文件 1:1 写出 `.out.jsonl`；checkpoint（`next_input_index`）；可选**文件级**并行（`global.num_workers` / `--num-workers`，`ThreadPoolExecutor`）。
- 单 JSON 多文件：聚合成 `part-*.jsonl`；checkpoint（`done`）；可选并行（worker 只读 JSON，**主线程单写者**，flush 后写 checkpoint）。
- Schema：`schema/metadata_v0.py`（Pydantic v1）；配置模型：`config/schema.py`、`config/loader.py`。
- I/O：`io/json.py`；占位适配器：`adapters/passthrough.py`；归一化：`utils/normalize.py`。
- **2D 关系增强（`image_plane`）**：`enrich.enrich_relations_2d` 在 **`MetadataV0` 副本**上根据框/点代表点计算 `relations`（单原子或 `components` 复合），与 adapter 解耦；详见 `metadata/plans/2026-04-16_0300_metadata_next/design.md`。

**仍为占位 / 未接入 CLI（与 `plans/`、wiki 文档对齐的后续工作）：**

- OpenSpatial Parquet 行 ↔ metadata 的专用转换、metadata / annotation 的 Parquet 导出（`pyarrow`）。
- **3D** 关系 enrich、可视化等。

**库用法（2D enrich）**（在已 `pip install -e ./metadata` 的环境中）：

```python
from openspatial_metadata.enrich import enrich_relations_2d
from openspatial_metadata.schema.metadata_v0 import MetadataV0

md_out = enrich_relations_2d(metadata)  # 不修改入参，返回新对象
```

**已实现（并行子集，见 `metadata/docs/config_yaml_zh.md`）：** `num_workers` / `--num-workers` 文件级线程并行、`strict=True` 遇错即停与 stderr / 退出码 1；**未实现** `ProcessPoolExecutor` 与 `strict=False`。

## 环境要求

- **Python**：`>=3.9`（见 `pyproject.toml`）。本地开发推荐使用 **3.10+** 或 **3.11** 虚拟环境。
- **依赖**：`pydantic` v1、`pyyaml`、`typing_extensions`；开发可选 `pytest`。

## 安装

在仓库根目录（或你的项目根）执行：

```bash
pip install -e ./metadata
pip install -e "./metadata[dev]"
```

## 命令行

安装后使用入口脚本：

```bash
openspatial-metadata --help
```

也可在已安装包的环境下：

```bash
python -m openspatial_metadata.cli --help
```

**示例**（在 OpenSpatial 仓库根目录执行；配置里的相对路径相对于**当前工作目录**）：

```bash
openspatial-metadata --config-root metadata/configs/datasets/demo_dataset.yaml --global-config metadata/configs/global.yaml --output-root metadata_out_demo
```

并行示例（覆盖 global 中的 `num_workers`）：

```bash
openspatial-metadata --config-root metadata/configs/datasets/demo_dataset.yaml --global-config metadata/configs/global.yaml --output-root metadata_out_demo --num-workers 4
```

## 源码布局

```
metadata/
├── pyproject.toml
├── setup.py
├── configs/                 # 示例 global + dataset YAML
├── plans/                   # design / plan / test_plan（文档先行）
├── tests/                   # 单元测试与 fixtures
└── src/openspatial_metadata/
    ├── __init__.py
    ├── cli.py
    ├── config/
    │   ├── loader.py
    │   └── schema.py
    ├── schema/
    │   ├── metadata_v0.py
    │   └── validate.py      # 占位校验
    ├── io/
    │   └── json.py
    ├── adapters/
    │   └── passthrough.py
    ├── enrich/
    │   ├── relation2d.py
    │   ├── filters.py
    │   └── constants.py
    └── utils/
        └── normalize.py
```

## 测试

```bash
python -m pytest metadata/tests -q
```

无 `pytest` 时可用标准库：

```bash
python -m unittest discover -s metadata/tests -p "test_*.py"
```

## 编辑器里「转到定义」没反应时

仓库里已用 **`pyrightconfig.json`**（根目录与 `metadata/` 各一份）把分析路径指到 `metadata/src`，无需把 `.vscode` 提交进 Git。若 **F12 / Ctrl+点击** 仍无效，请逐项检查：

1. **用「文件夹」打开工程**：在 Cursor 里打开的是 **`OpenSpatial` 仓库根目录**，而不是只打开单个文件；否则语言服务可能找不到配置。
2. **右下角语言模式**：当前文件必须是 **Python**，不能是 Plain Text。
3. **已安装并启用 Python 扩展**（自带 **Pylance**）。`Ctrl+Shift+P` → **Python: Select Interpreter**，选一个本机存在的解释器。
4. **重载窗口**：改完 `pyrightconfig.json` 后执行 **Developer: Reload Window**。
5. **看 Pylance 日志**：`Ctrl+Shift+U` 打开输出面板，右上角下拉选 **Pylance**，看是否有报错或崩溃。
6. **右键菜单**：在符号上右键，看是否有 **Go to Definition**；若完全没有，多半是语言服务未加载。

若 **`metadata/tests/` 曾被根目录 `.gitignore` 里的 `tests/` 误匹配**，语言服务可能一直不把该目录当正常源码分析；仓库已改为只忽略 **`/tests/`**（仅仓库根下的 `tests/`）。改完后 **Reload Window**。

若 **`import openspatial_metadata` 仍红线**：仓库根已有 **`pyproject.toml`** 的 `[tool.pyright]` / `[tool.basedpyright]`，以及 **`pyrightconfig.json`**。另提供 **`.vscode/settings.json`**（根目录 `.vscode/` 已在 `.gitignore` 中，不会进 Git），内写 `python.analysis.extraPaths`；若你删过该文件，可从同仓库同事处复制或按其中两行自行建回。然后 **Reload Window**，并在命令面板执行 **Python: Select Interpreter** 指向已执行过 `pip install -e ./metadata` 的环境（推荐，可少依赖编辑器路径 hacks）。

## 更多文档

- 规格与说明：`metadata/docs/`（如 `metadata_spec_v0_zh.md`）。
- **Global / Dataset YAML 配置字段说明**：`metadata/docs/config_yaml_zh.md`。
- **文档如何与代码同步（合并前自检）**：`metadata/docs/docs_sync_convention_zh.md`。
- **子项目全局进展 / 里程碑**（每完整一轮：设计→计划→测试计划→开发→**自测通过**→`change_log` 后再更新）：`metadata/docs/project_progress_zh.md`。
- 本阶段设计与测试方案：`metadata/plans/2026-04-14_0100_metadata_framework/`。
