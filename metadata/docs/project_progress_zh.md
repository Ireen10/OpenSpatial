# metadata 子项目 · 全局进展与里程碑

> **维护约定**：**不要**在「只做了一步文档」或「刚写完 test_plan 尚未开发」这类中间节点就改本文件。仅在完整走完 **设计 → 计划 → 测试计划 → 开发 → 自测通过**（并已写 `change_log.md`）之后，**一次性**更新本文件：刷新「当前阶段」、在「已完成」追加本轮交付、重写「下一步 TODO」、必要时调整「活跃计划」链接。合并进 `main` 可与该节点同日或稍后，以你团队习惯为准。  
> 与 `metadata/plans/<时间戳>_<主题>/change_log.md` 的关系：**change_log** 记**单轮**细节；本文件提供**跨轮次**总览，便于新人与协作者一眼看到「做到哪、接下来做什么」。

---

## 当前阶段（一句话）

已完成 **LLM 刷新链路 + 小批量验证能力**：在 grounding→LLM refresh→dedup→QA→training 的端到端上补齐可复用模板与调试/验证开关；下一步继续完善 viz 的 QA 交互与更强的大数据体验（例如更严格的分页/索引策略）。

---

## 已完成（从新到旧，里程碑粒度）

| 时间 / 轮次 | 交付摘要 |
|-------------|----------|
| **2026-04-21** | **pipeline（从 metadata 起步不再重写 metadata_noqa）**：当 `pipelines.to_metadata=false` 时，默认不再写出 `{split}/metadata_noqa/`（只产出 `metadata_qa/` 与 training）；新增 `pipelines.persist_noqa: true` 可强制写回以兼容旧脚本；E2E-B/E2E-C 模板显式设为 `false`；补 UT 覆盖。收束见 `metadata/plans/2026-04-21_1540_skip_rewrite_metadata_noqa/change_log.md`。 |
| **2026-04-21** | **图像读取兼容 tar（按分片 image_archive_pattern）**：`SplitSpec.image_archive_pattern` 支持按 shard 解析 `part_{shard:06d}.tar`，训练导出与部分 vision adapter 可直接从 tar 读取 `sample.image.path` 对应成员；同步补模板注释与测试覆盖。 |
| **2026-04-21** | **viz 稳定性**：对未配置 `viz.image_root` 的数据集在 viz 列表中默认跳过（避免浏览时触发 `/api/image` 报错）；同时修复 export 包 import-time re-export 引起的循环导入问题（`load_pil_for_metadata` partially initialized）。 |
| **2026-04-20** | **小批量验证与调试体验**：CLI 新增 `--max-records-total`（跨所有 dataset/split 总量上限）与 `--max-records-per-split`（每 split 上限），便于快速抽样验证；`ExpressionRefreshQwenAdapter` 支持 `print_llm_output` 将模型 JSON 输出直接打印到 stderr（不落盘）；文档同步更新 `config_yaml_zh.md`/`metadata/README.md` 并新增 UT 覆盖。 |
| **2026-04-20** | **去重 adapter 接入模板**：新增 `ObjectDedupExactAdapter`（按 `bbox_xyxy_norm_1000` + `phrase` 完全一致去重并重写 queries），并将其作为推荐步骤接入 E2E-D 模板（`e2e_d_grounding_refresh_qa_training`）放在 LLM refresh 之后。 |
| **2026-04-20** | **指代表达刷新（Qwen VL / OpenAI 兼容 API）**：`OpenAICompatibleChatClient`（`POST …/v1/chat/completions`）；`ExpressionRefreshQwenAdapter`（按 bbox 刷新 `phrase`/`category`，禁止位置词，`phrase` 为 null 时丢弃 object 并重写 queries）；`AdapterSpec.params` + CLI 传入 `dataset_config_path` 解析 `image_root`；文档与测试见 `metadata/plans/2026-04-20_1700_expression_refresh_qwen_llm/change_log.md`。 |
| **2026-04-20** | **多 Adapter 串联**：`dataset.yaml` 支持 `adapters:` 列表（顺序串联 `convert`）；与单个 `adapter` 兼容（非空 `adapters` 优先）；`ChainedAdapter` + `adapter_specs_for_dataset`；文档 `config_yaml_zh.md`；测试 `test_adapter_chain.py`。收束见 `metadata/plans/2026-04-20_1430_multi_adapter_chain/change_log.md`。 |
| **2026-04-20** | **Adapter 链契约（可选）**：`adapter_chain.strict_dict` + `validate_metadata_from_adapter_index`（推荐 `1`：第二段起要求 `MetadataV0`）；仅多适配器时生效。收束见 `metadata/plans/2026-04-20_1515_adapter_chain_strict_metadata/change_log.md`。 |
| **2026-04-17** | **viz（配置化 + 兼容 QA/training）**：`/api/tree` 同时枚举 metadata（含 `metadata_noqa/metadata_qa` stage）与 training parts（只到 part 粒度）；training JSONL 支持分页读取 `/api/training_lines`（limit 封顶）+ tarinfo 切片读图 `/api/training_image`；UI 增加 Training 模式展示对话与图片。收束见 `metadata/plans/2026-04-17_2350_viz_qa_and_training_viewer/change_log.md`。 |
| **2026-04-17** | **训练导出 pipeline（并行/断点续跑，最小 E2E）**：CLI 支持 `pipelines` 串联 `to_metadata/ensure_qa/export_training`；新增 `training_output_root`、global `qa_config` + `--qa-config`；训练 bundle 产出 `images/*.tar` + `*_tarinfo.json` + `jsonl/*.jsonl`，并支持 tar member 冲突去重 `__r{input_index}`；含测试配置与 E2E UT。收束见 `metadata/plans/2026-04-17_1059_training_export_parallel_io/change_log.md`。 |
| **2026-04-17** | **2D 空间关系 annotation（首轮）**：`RelationV0.relation_id`（解析自动补齐）+ `enrich_relations_2d` 统一 id；新 task `task/annotation/spatial_relation_2d.py`、demo 配置、`relation_2d_prompt_templates`；同指代短槽位、双框 tier 排序 + `dual_box_keep_prob`、artifact 生成脚本与聚焦 UT。收束见 `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/change_log.md`。 |
| **2026-04-16** | **断点续传体验优化**：checkpoint 目录改为按 `output_root/{dataset}/{split}/.checkpoints` 隔离，支持只重跑某个 dataset/split；兼容读取旧的 `output_root/.checkpoints`（只读 fallback）；新增 UT 覆盖并通过。 |
| **2026-04-16** | **CLI 可用性/可观测性**：`inputs` 支持绝对路径 glob（修复 `Path.glob` 对非相对 pattern 的限制）；进度展示默认使用 `tqdm`（多 worker 多进度条，每个 worker/文件一个 bar），若环境无 tqdm 自动回退到 log；仍保留 stderr 日志用于关键事件。 |
| **2026-04-16** | **schema & 追溯信息**：`dataset.dataset_path` 加入 schema，并由 CLI 自动注入当前 dataset.yaml 路径；`GroundingQAAdapter` 补齐 `objects[].phrase` 与 `queries[].query_type` 默认值（并支持 `ds.meta.query_type` 覆盖）；`ds.meta` 注入时过滤掉 dataset 保留字段避免臃肿；同步更新 wiki 文档对齐 `query_type` 推荐取值。 |
| **2026-04-15** | **E2E（小样例）**：新增 `GroundingQAAdapter` + CLI 调用 `adapter.convert`；dataset.yaml 支持 `enrich.relations_2d` 并在写出前执行 enrich；输出命名统一为 `*.metadata.jsonl`；支持 dataset.yaml 配置 `output_root`（多数据集隔离输出）；将 dataset.yaml 的 `meta` 注入到输出 `dataset.source` 与 `dataset.meta`；RefCOCO grounding 小样例（1 行 JSONL）可走完整链路并有 E2E 测试覆盖。 |
| **2026-04-15** | **2D enrich 增强**：增加 containment 过滤（小框被覆盖 ≥70% 跳过），避免“大包小但 IoU 小”场景漏过；并增加“已有 relation triple 则跳过重算”去重逻辑。 |
| **2026-04-15** | **schema / configs 组织**：`MetadataV0` 增加 `queries`（支持单/多实例与多指代表达）；datasets 配置改为“一数据集一文件夹”（`datasets/*/dataset.yaml`），并更新 loader/测试。 |
| **2026-04-15** | **2D 关系增强**：`openspatial_metadata.enrich`（`enrich_relations_2d`、`filters`、`constants`）、`test_enrich_relation2d.py`；设计/计划见 `metadata/plans/2026-04-15_1658_metadata_next/`；`change_log.md` 已写。 |
| **2026-04-15** | **并行 metadata CLI**：`effective_parallel_workers`、JSONL / `json_files` 文件级线程并行、flush 后 checkpoint、`--num-workers` 接线、strict 失败 stderr + 退出码 1；测试 `test_parallel_cli.py`（含 resume 场景）；文档 `config_yaml_zh.md`、`README.md`；详见 `metadata/plans/2026-04-15_0948_parallel_metadata_cli/change_log.md`。**步骤验收已通过；Linux 回归已通过。** |
| **2026-04-14 ~ 15** | **metadata 框架 v0**：`openspatial-metadata` CLI（JSONL 1:1、`json_files`→`part-*.jsonl`、checkpoint）、YAML 配置、Pydantic v0 schema、fixtures、`pytest`/`unittest` 测试（含多 JSONL 分片 IT）、示例 `configs/`。 |
| **同期** | 用户文档：`config_yaml_zh.md`、`docs_sync_convention_zh.md`；`README.md`；根目录 `pyproject.toml` / `pyrightconfig.json`；`.gitignore` 修正（`/tests/`、`egg-info`、临时目录）；plan **模板**补充「文档同步」与 **change_log** 模板。 |

---

## 下一步 TODO（按建议优先级，随实现勾选）

- [ ] **viz（完善 QA 交互 + 更强大数据体验）**：
  - metadata 模式新增明确的 `qa_items` 面板（过滤/搜索/跳转）与必要的轻量分页（若单文件特别大）
  - training 模式支持更稳定的“随机跳转/定位”能力（例如行号索引或 sidecar index），并限制 `line_count` 的计算成本
- [ ] **metadata_spec_v0**：在 `metadata/docs/metadata_spec_v0_zh.md` 补一节 `RelationV0.relation_id`（格式、自动生成、与 QA `meta` 追溯对齐）；与首轮 annotation 交付对齐。  
- [ ] **CI**：在 Linux 上跑 `pytest metadata/tests`（若仓库尚无 workflow，可在 OpenSpatial 根或子项目加一条）。  
- [ ] **规模化接入真实数据**：为每个真实数据集补齐 `datasets/<name>/dataset.yaml`（含 inputs/glob、output_root、meta、enrich 开关），并补“样例+解析约束”的 plans。  
- [ ] **3D enrich**：定义 `relations_3d` 的 enrich 入口与实现，打通 `enrich.relations_3d` 开关。  
- [ ] **严格/容错策略**：落地 `strict` 的 per-record error policy（记录失败样本、统计、可选继续），并补 UT/IT。  
- [ ] **长期**：`ProcessPoolExecutor`、best-effort（`strict=False`）等 **另开 design 轮次**，不混在本文件旧条目里删除历史。

---

## 活跃计划目录（索引）

| 目录 | 状态 |
|------|------|
| `metadata/plans/2026-04-21_1540_skip_rewrite_metadata_noqa/` | **已交付（实现 + 自测 + 收束）**：从 metadata 起步时默认不重写 `metadata_noqa/`（可用 `persist_noqa` 覆盖）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-17_2350_viz_qa_and_training_viewer/` | **已交付（实现 + 自测 + 收束）**：viz 配置化 + 兼容 QA/training（分页 + tar 切片读图）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-17_1059_training_export_parallel_io/` | **已交付（实现 + 自测 + 收束）**：dataset-level pipeline（ensure_qa + training export）、并行与 resume；见该目录 `change_log.md` |
| `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/` | **已交付（首轮实现 + 收束）**：2D 空间关系 annotation task + `relation_id`；见该目录 `change_log.md`、`plan.md` 收束节 |
| `metadata/plans/2026-04-15_2152_checkpoint_scoped/` | **已交付**：checkpoint 按 dataset/split 隔离 + 旧位置兼容读取；见该目录 `change_log.md` |
| `metadata/plans/2026-04-15_1658_metadata_next/` | **已交付（首轮库+测）**：2D enrich；细节见该目录 `change_log.md` |
| `metadata/plans/2026-04-15_0948_parallel_metadata_cli/` | **已交付**（实现 + 自测 + `change_log.md`；细节见该目录） |
| `metadata/plans/2026-04-14_1737_metadata_framework/` | **已交付**（框架 v0；细节见该目录内文档与仓库历史） |

---

## 更新本文件时的检查清单

- [ ] 「当前阶段」是否仍准确（一句话）。  
- [ ] 「已完成」是否已为**刚结束的一整轮**（含自测与 `change_log.md`）追加一行（不写冗长实现细节，可链到 PR 或 `change_log.md`）。  
- [ ] 「下一步 TODO」是否已去掉已完成项、是否反映最新优先级。  
- [ ] 「活跃计划」目录表是否与实际 `metadata/plans/` 一致。
