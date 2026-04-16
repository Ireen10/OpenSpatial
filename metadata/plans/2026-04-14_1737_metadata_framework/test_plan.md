## 测试方案（Test Plan）：`metadata/` 子项目工程框架（v0）

> 要求：每一项测试都要能在 `plan.md` 中找到对应的功能点。本测试方案只覆盖“框架能力”（安装/CLI/config/I-O/checkpoint/并行/normalize），不覆盖适配器/enrich/viz/parquet 的业务正确性（它们当前为占位）。

### 测试范围

- 覆盖范围：
  - 子项目可安装、CLI 可运行（Plan §1、§6）
  - schema 最小骨架可 parse/serialize（Plan §2）
  - JSONL 分片输入的 record 流读取/写出、1:1 输出对齐（Plan §3）
  - 单 JSON 文件输入的 record 流读取、聚合写出 JSONL part（Plan §3）
  - checkpoint 断点续跑（JSONL: `next_input_index`；单 JSON: `done`）（Plan §3）
  - 并行策略：按输入文件粒度并行、避免多进程写同一文件（Plan §3）
  - config loader：dataset config（一个数据集一个 config）+ 可选 global + glob/pattern 展开 + adapter import 校验（Plan §4）
  - normalize：round + clamp 到 `[0, scale)` 的规范化与反规范化基本正确性（Plan §5）
- 不覆盖范围：
  - label/boxes/points 等具体数据源适配器逻辑（占位）
  - relations/enrich 正确性（占位）
  - 可视化（占位）
  - OpenSpatial annotation parquet 导出（占位）

### 测试数据与夹具（fixtures）

建议在 `metadata/tests/fixtures/` 放最小样例：

- `jsonl_shard_small.jsonl`：10 行，包含最小 sample（含 `sample_id`、`image.path`、`objects` 最小字段）
- `json_files_small/`：10 个 JSON 文件（每文件 1 条 sample）
- `configs/global.yaml`：最小 global（output_root、scale=1000、batch_size=3、num_workers=2）
- `configs/datasets/demo_dataset.yaml`：指向上述 fixtures 的输入路径与 split 定义，包含 dataset meta 与 adapter 定位字段（指向一个占位类）

### 测试执行方式（脚本/命令）

推荐使用 **`pytest`**（已在 `metadata/pyproject.toml` 的 `dev` 可选依赖中声明；`pip install -e ./metadata[dev]`）。`pytest` 可直接运行基于 `unittest.TestCase` 的测试文件，无需先改写测试风格。

- **运行全部测试**（从仓库根目录）：
  - `python -m pytest metadata/tests -q`
- **兜底**（仅标准库，无外网/无 pytest 时）：
  - `python -m unittest discover -s metadata/tests -p "test_*.py"`

### 单元测试（unittest）

#### UT-1 子项目可导入（Plan §1）
- **步骤**：`python -c "import openspatial_metadata"`
- **断言**：不报错

#### UT-2 schema round-trip（Plan §2）
- **输入**：最小 dict（dataset/sample/objects/relations/aux）
- **步骤**：pydantic model parse → dump → 再 parse
- **断言**：关键字段一致；可选字段缺省不影响

#### UT-3 normalize 像素↔norm_1000（Plan §5）
- **输入**：`w=640,h=480,scale=1000`
  - 点：`(0,0)`、`(w, h)`、`(w-1, h-1)`、随机点
  - bbox：包含边界与越界（若实现 clip）
- **断言**：
  - round 后结果落在 `0..999`
  - `x=w` 这类 case round 可能得到 1000，必须 clamp 回 999
  - 反归一化后坐标在像素范围内（并满足基本单调性）

### 集成测试（以 CLI/loader/I-O 为主）

#### IT-1 config loader 展开输入文件列表（Plan §4）
- **步骤**：加载 `--config-root metadata/tests/fixtures/configs/datasets`
- **断言**：
  - 发现并解析 dataset config
  - split 的 glob/pattern 能展开到预期文件集合（数量、排序规则在实现中固定）
  - dataset meta 可读取
  - adapter 定位字段能成功 import（占位类存在）

#### IT-2 JSONL 分片：1:1 输出对齐 + batch flush（Plan §3）
- **输入**：`jsonl_shard_small.jsonl`，设置 `batch_size=3`
- **步骤**：CLI 透传模式运行一次（不启用适配器/增强，仅重写输出）
- **断言**：
  - 输出文件名与输入 1:1 对齐（如 `jsonl_shard_small.out.jsonl` 或约定的后缀）
  - 输出行数=输入行数
  - 输出第 k 行的 `record_ref.input_index == k`（若写入 aux）或至少能从日志/sidecar 对应到输入行号

#### IT-2b 同一 split 下列多个 JSONL 切分（Plan §3）
- **背景**：数据集中常见多个 shard 文件（如 `part-000.jsonl`、`part-001.jsonl`）。当前实现按文件**顺序**逐个处理；**按文件并行（`num_workers`）尚未实现**，本项只覆盖多文件下的正确性与隔离性。
- **输入**：`metadata/tests/fixtures/jsonl_shard_alpha.jsonl`（3 行）与 `jsonl_shard_beta.jsonl`（4 行）；dataset config 的 `inputs` 中列出两条绝对路径。
- **步骤**：CLI 一次运行，`batch_size=2`（触发分批 flush）。
- **断言**：
  - 生成两个输出：`jsonl_shard_alpha.out.jsonl`、`jsonl_shard_beta.out.jsonl`，行数分别等于对应输入行数
  - 各行 `sample_id` 与来源 shard 一致（互不串档）
  - `output_root/.checkpoints/` 下至少存在两个 checkpoint 文件（每输入文件独立）

#### IT-3 JSONL 分片：checkpoint 断点续跑（Plan §3）
- **输入**：同 IT-2
- **步骤**：
  1) 运行处理，但在处理中途模拟中断（实现上可用“只处理前 N 行”的参数或在测试里直接调用处理函数限制步数）
  2) 第二次带 `--resume` 继续
- **断言**：
  - 第二次不会重复写已完成的行
  - 最终输出行数正确
  - checkpoint 的 `next_input_index` 单调递增且最终等于输入行数

#### IT-4 单 JSON 文件输入：聚合输出 part（Plan §3）
- **输入**：`json_files_small/`，设置 `batch_size=4`
- **步骤**：CLI 运行（聚合写出）
- **断言**：
  - 输出为 `part-000000.jsonl`、`part-000001.jsonl`…（数量符合 batch_size）
  - 每个输入文件对应输出中恰好一条记录（可通过 `record_ref.input_file` 校验）

#### IT-5 单 JSON 文件输入：done checkpoint（Plan §3）
- **步骤**：先处理一部分文件生成若干 `done=true`，再 `--resume`
- **断言**：resume 后只处理未 done 的文件；最终每个输入文件只输出一次

#### IT-6 并行：按输入文件粒度并行（Plan §3）
- **输入**：至少 2 个 JSONL 分片文件或 10 个 JSON 文件；`num_workers=2`
- **断言**：
  - 不出现多个进程写同一输出文件的冲突
  - 输出数量正确
  - checkpoint 文件为“按输入文件粒度”生成

### 质量门槛（Gate）

- 所有单元测试 + 集成测试通过
- 在小样例上验证：
  - 内存不随样本数线性增长（观察性验证：处理 10 行/10 文件与 1000 行/1000 文件时无明显累计；性能基准后续再补）
  - 断点续跑不会重复写出

