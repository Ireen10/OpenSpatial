# metadata 子项目 · 全局进展与里程碑

> **维护约定**：**不要**在「只做了一步文档」或「刚写完 test_plan 尚未开发」这类中间节点就改本文件。仅在完整走完 **设计 → 计划 → 测试计划 → 开发 → 自测通过**（并已写 `change_log.md`）之后，**一次性**更新本文件：刷新「当前阶段」、在「已完成」追加本轮交付、重写「下一步 TODO」、必要时调整「活跃计划」链接。合并进 `main` 可与该节点同日或稍后，以你团队习惯为准。  
> 与 `metadata/plans/<时间戳>_<主题>/change_log.md` 的关系：**change_log** 记**单轮**细节；本文件提供**跨轮次**总览，便于新人与协作者一眼看到「做到哪、接下来做什么」。

---

## 当前阶段（一句话）

**adapter→enrich→写出** 的最小端到端链路已跑通（dataset.yaml 可控 2D enrich / per-dataset 输出目录 / meta 注入）；后续重点是将真实数据集规模化接入与补齐 3D enrich、严格/容错策略与 CI。

---

## 已完成（从新到旧，里程碑粒度）

| 时间 / 轮次 | 交付摘要 |
|-------------|----------|
| **2026-04-15** | **E2E（小样例）**：新增 `GroundingQAAdapter` + CLI 调用 `adapter.convert`；dataset.yaml 支持 `enrich.relations_2d` 并在写出前执行 enrich；输出命名统一为 `*.metadata.jsonl`；支持 dataset.yaml 配置 `output_root`（多数据集隔离输出）；将 dataset.yaml 的 `meta` 注入到输出 `dataset.source` 与 `dataset.meta`；RefCOCO grounding 小样例（1 行 JSONL）可走完整链路并有 E2E 测试覆盖。 |
| **2026-04-15** | **2D enrich 增强**：增加 containment 过滤（小框被覆盖 ≥70% 跳过），避免“大包小但 IoU 小”场景漏过；并增加“已有 relation triple 则跳过重算”去重逻辑。 |
| **2026-04-15** | **schema / configs 组织**：`MetadataV0` 增加 `queries`（支持单/多实例与多指代表达）；datasets 配置改为“一数据集一文件夹”（`datasets/*/dataset.yaml`），并更新 loader/测试。 |
| **2026-04-16** | **2D 关系增强**：`openspatial_metadata.enrich`（`enrich_relations_2d`、`filters`、`constants`）、`test_enrich_relation2d.py`；设计/计划见 `metadata/plans/2026-04-16_0300_metadata_next/`；`change_log.md` 已写。 |
| **2026-04-15** | **并行 metadata CLI**：`effective_parallel_workers`、JSONL / `json_files` 文件级线程并行、flush 后 checkpoint、`--num-workers` 接线、strict 失败 stderr + 退出码 1；测试 `test_parallel_cli.py`（含 resume 场景）；文档 `config_yaml_zh.md`、`README.md`；详见 `metadata/plans/2026-04-15_0200_parallel_metadata_cli/change_log.md`。**步骤验收已通过；Linux 回归已通过。** |
| **2026-04-14 ~ 15** | **metadata 框架 v0**：`openspatial-metadata` CLI（JSONL 1:1、`json_files`→`part-*.jsonl`、checkpoint）、YAML 配置、Pydantic v0 schema、fixtures、`pytest`/`unittest` 测试（含多 JSONL 分片 IT）、示例 `configs/`。 |
| **同期** | 用户文档：`config_yaml_zh.md`、`docs_sync_convention_zh.md`；`README.md`；根目录 `pyproject.toml` / `pyrightconfig.json`；`.gitignore` 修正（`/tests/`、`egg-info`、临时目录）；plan **模板**补充「文档同步」与 **change_log** 模板。 |

---

## 下一步 TODO（按建议优先级，随实现勾选）

- [ ] **CI**：在 Linux 上跑 `pytest metadata/tests`（若仓库尚无 workflow，可在 OpenSpatial 根或子项目加一条）。  
- [ ] **规模化接入真实数据**：为每个真实数据集补齐 `datasets/<name>/dataset.yaml`（含 inputs/glob、output_root、meta、enrich 开关），并补“样例+解析约束”的 plans。  
- [ ] **3D enrich**：定义 `relations_3d` 的 enrich 入口与实现，打通 `enrich.relations_3d` 开关。  
- [ ] **长期**：`ProcessPoolExecutor`、best-effort（`strict=False`）等 **另开 design 轮次**，不混在本文件旧条目里删除历史。

---

## 活跃计划目录（索引）

| 目录 | 状态 |
|------|------|
| `metadata/plans/2026-04-16_0300_metadata_next/` | **已交付（首轮库+测）**：2D enrich；细节见该目录 `change_log.md` |
| `metadata/plans/2026-04-15_0200_parallel_metadata_cli/` | **已交付**（实现 + 自测 + `change_log.md`；细节见该目录） |
| `metadata/plans/2026-04-14_0100_metadata_framework/` | **已交付**（框架 v0；细节见该目录内文档与仓库历史） |

---

## 更新本文件时的检查清单

- [ ] 「当前阶段」是否仍准确（一句话）。  
- [ ] 「已完成」是否已为**刚结束的一整轮**（含自测与 `change_log.md`）追加一行（不写冗长实现细节，可链到 PR 或 `change_log.md`）。  
- [ ] 「下一步 TODO」是否已去掉已完成项、是否反映最新优先级。  
- [ ] 「活跃计划」目录表是否与实际 `metadata/plans/` 一致。
