## 执行计划（Plan）：`metadata/` 子项目工程框架（v0）

> 前置：`design.md` 已对齐确认。本计划只覆盖“工程框架落地（可运行骨架 + config 驱动批处理 + JSON/JSONL I/O + utils 归一化）”，适配器/enrich/viz/annotation-parquet 均以占位为主，不做业务实现。

### 交付物清单

- **工程骨架（代码）**
  - `metadata/pyproject.toml`：子项目依赖与打包信息（含 pydantic）
  - `metadata/src/openspatial_metadata/`：
    - `schema/metadata_v0.py`：v0 schema 最小骨架（pydantic），含 id 生成内部方法占位
    - `schema/validate.py`：最小校验接口占位（可先返回空错误列表）
    - `config/schema.py`：转换配置结构（多数据集、多 split、多分片模式、dataset meta）
    - `config/loader.py`：加载 config + 展开文件清单（支持 `data_{000000..}.jsonl` 这类分片）
    - `io/json.py`：JSON/JSONL 读写（流式）
    - `utils/normalize.py`：归一化/反归一化函数（参数化 `w/h/scale`；`scale` 默认 1000；可选 `clip/rounding` 策略）
    - `adapters/*.py`：占位（仅定义函数签名/接口，不实现转换）
    - `enrich/*.py`：占位（仅定义函数签名/接口，不实现增强）
    - `viz/__init__.py`：占位
    - `cli.py`：CLI 骨架（解析 config，枚举输入文件，读→写通路先打通）
  - `metadata/tests/`：最小单测（JSONL I/O、normalize 工具、config loader）

- **样例与约定（文档/配置）**
  - `metadata/configs/datasets/demo_dataset.yaml`：最小 demo（1 个 dataset、1 个 split、1~N 个 jsonl 文件；演示“一个数据集一个 config”）
  - `metadata/configs/global.yaml`：（可选）全局默认配置（output_root、scale、batch_size、num_workers、resume 策略等）

### 任务拆解（按顺序执行）

1. **创建子项目打包骨架**
   - 新增：`metadata/pyproject.toml`、`metadata/src/.../__init__.py`
   - 完成条件：`pip install -e ./metadata` 成功；`python -m openspatial_metadata.cli --help` 可运行

2. **落 schema 最小骨架（pydantic）**
   - 新增：`schema/metadata_v0.py`
   - 要求：
     - 只实现最小字段集合（与 wiki 顶层模块一致：dataset/sample/camera/objects/relations/aux），其余字段后续扩展
     - 提供 `@staticmethod`/`@classmethod` 的 id 生成方法：v0 单视角默认只要求 **sample 内唯一/稳定**（例如 `{category}#{index}`），不要求跨数据集全局统一；后续如有需要再扩展
   - 完成条件：可从 dict 构造与导出 dict；不做强校验也可工作

3. **实现 JSON/JSONL 流式 I/O**
   - 新增：`io/json.py`
   - 目标：支持大规模数据在**常数内存**下处理（流式读取、批量写出、可断点续跑）
   - 设计细化（流式批量读写）
     - **输入类型（两种常见形态）**
       - **JSONL 分片**：一个输入文件包含多条 sample（每行一个 JSON）
       - **单 JSON 文件**：一个输入文件对应一条 sample（一个文件一个 JSON 对象）
       - 说明：两者都要支持；优先实现 JSONL 分片（更常见、也更适合大规模流式处理），单 JSON 文件作为同一框架下的另一种 reader

     - **Record 流抽象（用于对齐输入↔输出/断点/错误定位）**
       - 统一把任意输入读成 record 流：`Iterator[(record_dict, record_ref)]`
       - `record_ref` 建议至少包含：
         - `input_file`（必选）
         - `input_index`（JSONL 为行号；单 JSON 文件可固定为 0）
       - checkpoint 与错误日志一律记录 `record_ref`，保证可追溯与可重放

     - **流式读取（JSONL）**
       - API 形态（示意）：`iter_jsonl(path) -> Iterator[(dict, record_ref)]`
       - 行为：
         - 逐行读取、逐行解析（不把文件整体读入内存）
         - 遇到空行跳过；遇到 JSON 解析失败：记录错误并可选跳过/终止（策略由 config 控制）
         - 可选支持 `.jsonl.gz`（后续需要再加）

     - **读取（单 JSON 文件：一个文件一个 sample）**
       - API 形态（示意）：`iter_json_files(paths) -> Iterator[(dict, record_ref)]`
       - 行为：
         - 每个文件读取一个 JSON 对象，产出一条 record
         - 并行时按“文件粒度”天然适配

     - **批量写出（JSONL）**
       - API 形态（示意）：`write_jsonl(path, items, append=False)` 或 `JsonlWriter(path, append=...)`
       - 行为：
         - batch 内按行写入，写完 `flush()`；必要时 `fsync()`（默认不做，避免性能损失；可配置）
         - 支持按 batch 切分输出文件：`part-000000.jsonl`、`part-000001.jsonl`…
         - 输出路径组织建议：`<output_root>/<dataset>/<split>/...`

     - **输出命名与输入对齐（默认策略）**
       - 当输入为 **JSONL 分片** 时，默认采用 **1:1 对齐**：
         - 输入：`data_000123.jsonl`
         - 输出：`data_000123.out.jsonl`（或 `.metadata.jsonl`）
         - 约束：输出 record 的顺序默认保持与输入行顺序一致（即使内部用 batch，也仅影响 flush，不跨文件/不重排）
       - 当输入为 **单 JSON 文件（一个文件一个 sample）** 时，默认采用 **按 dataset/split 聚合**：
         - 输出：`part-000000.jsonl`、`part-000001.jsonl`…
         - 命名只需与 dataset/split 对齐；每条输出 record 通过 `record_ref.input_file` 追溯来源

     - **批处理（batch）策略**
       - `batch_size`：默认 1000（可配置）；按“行数”控制 batch
       - 若单行过大导致 batch 内存过高：允许配置 `max_batch_bytes`（后续再加；本阶段先仅行数）
       - 每个 batch 处理完立即释放临时对象（避免累计到 list 里）
     - **断点续跑（checkpoint）**
       - 选择一个默认策略（v0）：**按输入文件粒度 checkpoint**
         - JSONL 分片输入：每个输入文件一个 checkpoint，记录：
           - `input_file`
           - `next_input_index`（下一个要处理的行号；即已成功写出的最大行号 + 1）
           - `errors_count`（可选）
         - 单 JSON 文件输入（一个文件一个 sample）：每个输入文件一个 checkpoint，记录：
           - `input_file`
           - `done: true|false`（完成标记）
           - `errors_count`（可选）
       - 策略：每完成一个 batch（JSONL）或完成一个文件（单 JSON）就更新 checkpoint（写临时文件再原子 rename，避免损坏）
       - 允许 `resume=true`：
         - JSONL：从 `next_input_index` 继续（顺序跳过前 N 行）
         - 单 JSON：跳过所有 `done=true` 的文件
   - 并行策略（在数据量大时启用）
     - **并行单位**：按“输入分片文件粒度”并行（而非按行并行），避免跨进程共享大对象与锁竞争
     - **并行实现建议**：
       - Python `multiprocessing` / `concurrent.futures.ProcessPoolExecutor`
       - 每个 worker：
         - 读取一个输入文件（流式）
         - 写出到独立输出文件（避免多进程写同一文件；JSONL 分片场景下天然 1:1 对齐）
         - 维护该文件自己的 checkpoint
     - **顺序与确定性**
       - JSONL 分片输入采用 1:1 输出时：每个输出文件内部顺序与输入一致；文件之间完成先后不影响对齐
       - 单 JSON 文件聚合输出时：并行会导致 part 内顺序不确定；若下游需要稳定顺序，可在单线程 merge 阶段按 `(input_file, input_index)` 排序后再写最终 part
     - **资源控制**
       - `num_workers` 默认取 `min(物理核数, 分片文件数)`，并留出余量避免 IO 饱和
       - 同一块磁盘上并发过高会变慢（尤其 HDD）；SSD 也需控制
   - 注意事项 / 常见坑
     - 不要用 `pandas.read_json(lines=True)` 读超大 JSONL（会把整文件读进内存）
     - 不要把全量样本 accumulate 在 list 再统一写出
     - 解析/校验要“按需”：本阶段 schema 校验可以轻量或可关闭（避免成为瓶颈）
     - 错误处理要可配置：`strict`（遇错即停） vs `best_effort`（记录后跳过）
   - 完成条件：可写 jsonl；可迭代读取 jsonl；batch + checkpoint 机制可跑通一个 demo 分片文件

4. **实现 config schema + loader（一个数据集一个 config；支持 config-root 批量处理）**
   - 新增：`config/schema.py`、`config/loader.py`、`metadata/configs/datasets/demo_dataset.yaml`
   - 完成条件：
     - 配置组织：
       - **一个数据集一个 config 文件**（dataset config）
       - CLI 支持传入一个 `--config-root <dir>`，自动发现并处理目录下所有 dataset config（并支持可选的 dataset 白名单过滤）
       - （可选）支持 `global.yaml` 作为全局默认值，dataset config 可覆盖
     - dataset config 内容能力：
       - 支持输入 dataset 级 meta 信息（例如数据源信息、版本、备注等），并能在转换时写入到输出 metadata 的 `dataset` / `aux`（本阶段只打通字段透传，不做强校验）
       - 每个 dataset 支持多个 split
       - split 支持 glob 或分片 pattern 展开为文件列表
       - 支持为该 dataset 显式指定“处理策略/适配器”的实现位置（对齐 OpenSpatial 的配置风格）：
         - 例如使用 `file_name` + `class_name`（或 `module` + `class`）定位到 `src/openspatial_metadata/` 下的某个适配器类
         - loader 只负责解析与校验“能否 import 到该类”（本阶段不要求真正跑通转换逻辑）

5. **实现 utils/normalize（归一化/反归一化）**
   - 新增：`utils/normalize.py`
   - 归一化策略（与当前团队约定对齐）：
     - 像素 → norm_1000：先按 `u = round(x / w * scale)`、`v = round(y / h * scale)`（bbox 同理对 4 个坐标做该映射），再将结果 **clamp 到 `[0, scale)`**（即 `0..scale-1`，不含 `scale`）
     - norm_1000 → 像素：按反向映射并 round（细节在实现时固定）
   - 完成条件：单测覆盖典型 case（像素↔norm_1000；边界值如 x=0、x=w、以及 round 后落到 1000 的情况应被 clamp 回 999）

6. **实现 CLI 骨架（以 config 驱动批处理）**
   - 新增：`cli.py`
   - 行为：
     - 读取 config → 展开输入文件
     - 逐行读取 JSONL → 解析为 schema（或原样 dict passthrough）
     - 按 batch 写出 JSONL（先实现“重新归档/透传”，后续再接适配器/enrich）
     - 支持 `--resume`（基于 checkpoint 断点续跑）
     - 支持 `--num-workers`（按分片文件并行）
   - 完成条件：demo config 跑通“读→写”闭环

7. **补齐占位模块（adapters/enrich/viz/parquet）**
   - 新增：对应文件，内容只包含接口签名与 `NotImplementedError`（或空实现）
   - 完成条件：import 不报错，便于后续扩展

### 完成定义（DoD）

- 子项目可安装、可运行 CLI
- config 驱动能处理多数据集/多 split/多分片 jsonl
- JSONL I/O 与 normalize 工具有单测
- adapters/enrich/viz/annotation-parquet 仅占位，不引入错误承诺

