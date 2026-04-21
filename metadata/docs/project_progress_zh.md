# metadata 子项目 · 全局进展与里程碑

> **维护约定**：**不要**在「只做了一步文档」或「刚写完 test_plan 尚未开发」这类中间节点就改本文件。仅在完整走完 **设计 → 计划 → 测试计划 → 开发 → 自测通过**（并已写 `change_log.md`）之后，**一次性**更新本文件：刷新「当前阶段」、在「已完成」追加本轮交付、重写「下一步 TODO」、必要时调整「活跃计划」链接。合并进 `main` 可与该节点同日或稍后，以你团队习惯为准。  
> 与 `metadata/plans/<时间戳>_<主题>/change_log.md` 的关系：**change_log** 记**单轮**细节；本文件提供**跨轮次**总览，便于新人与协作者一眼看到「做到哪、接下来做什么」。

---

## 当前阶段（一句话）

已连续完成八轮 **pipeline 内部重构加固（batch-1 / batch-2 / batch-3 / batch-4 / strict_cleanup / batching_perf / perf_timing_nonintrusive / resume_perf_tqdm_stability）**：在不改核心产物语义前提下持续收口兼容逻辑并优化 pipeline 运行时开销；最新一轮修复了 resume 跳过阶段不必要 JSON 解析与 tqdm 并行显示干扰问题。下一步继续完善 viz 的 QA 交互与更强的大数据体验（例如更严格的分页/索引策略）。

---

## 已完成（从新到旧，里程碑粒度）

| 时间 / 轮次 | 交付摘要 |
|-------------|----------|
| **2026-04-21** | **resume 性能与 tqdm 稳定性修复（resume_perf_tqdm_stability）**：`iter_jsonl` 支持 `start_index` 并在 resume 跳过阶段避免无效 `json.loads`；并在 `progress=tqdm` 下抑制并行 worker 高频 done 日志，缓解控制台排版错乱。新增回归测试覆盖。收束见 `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/change_log.md`。 |
| **2026-04-21** | **非侵入性能埋点（perf_timing_nonintrusive）**：为 pipeline 增加 `checkpoint_write/metadata_dump/persist_noqa_write/persist_qa_write` phase 聚合，埋点仅进入 `--timing` 汇总，不新增运行中日志，不影响进度条显示。收束见 `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/change_log.md`。 |
| **2026-04-21** | **training pipeline 批量写盘性能修正（batching_perf）**：`batch_size` 正式接入 training pipeline 的 `metadata_noqa/metadata_qa` 持久化与 checkpoint 频率控制（从逐条改为按批）；同时去除 `persist_noqa=false` 分支下 `noqa` 冗余 dump。新增回归测试覆盖。收束见 `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/change_log.md`。 |
| **2026-04-21** | **strict 参数冗余清理**：移除 CLI 内部 `strict` 透传链路并固化严格模式；`strict=false` 由“隐式无效”改为“显式报错”；同步更新说明文档与测试签名。收束见 `metadata/plans/2026-04-21_1428_strict_cleanup/change_log.md`。 |
| **2026-04-21** | **pipeline 内部重构加固（batch-4）**：`qa_tasks` 分发层从硬编码单分支升级为“显式 builder + 约定式 fallback”的可扩展机制，保持 `spatial_relation_2d` 现有行为不变。收束见 `metadata/plans/2026-04-21_1423_pipeline_refactor_batch4/change_log.md`。 |
| **2026-04-21** | **pipeline 内部重构加固（batch-3）**：补齐 `loader/training_pack/chained` 的 Pydantic 兼容入口收口，移除源码内剩余 `parse_obj` 直接调用点；全量测试通过并显著减少 deprecation warnings。收束见 `metadata/plans/2026-04-21_1421_pipeline_refactor_batch3/change_log.md`。 |
| **2026-04-21** | **pipeline 内部重构加固（batch-2）**：在 `cli.py` 的 training pipeline 中抽取 `_build_metadata_views` 与 `_persist_payloads`，统一串行与并行路径的 metadata 构建与 shard 持久化逻辑，保持 checkpoint/保序写语义不变。收束见 `metadata/plans/2026-04-21_1418_pipeline_refactor_batch2/change_log.md`。 |
| **2026-04-21** | **pipeline 内部重构加固（batch-1）**：新增 `utils/pydantic_compat.py` 统一 v1/v2 兼容；`export_metadata_to_training_bundle` 复用 `build_training_members_and_rows` 去重实现；`ObjectDedupExactAdapter` 收窄异常捕获；`_instantiate_one_adapter` 增加异常路径诊断日志并保持 fallback 兼容。收束见 `metadata/plans/2026-04-21_1301_pipeline_refactor_batch1/change_log.md`。 |
| **2026-04-21** | **pipeline（从 metadata 起步不再重写 metadata_noqa）**：当 `pipelines.to_metadata=false` 时，默认不再写出 `{split}/metadata_noqa/`（只产出 `metadata_qa/` 与 training）；新增 `pipelines.persist_noqa: true` 可强制写回以兼容旧脚本；E2E-B/E2E-C 模板显式设为 `false`；补 UT 覆盖。收束见 `metadata/plans/2026-04-21_1540_skip_rewrite_metadata_noqa/change_log.md`。 |
| **2026-04-21** | **图像读取兼容 tar（按分片 image_archive_pattern）**：`SplitSpec.image_archive_pattern` 支持按 shard 解析 `part_{shard:06d}.tar`，训练导出与部分 vision adapter 可直接从 tar 读取 `sample.image.path` 对应成员；同步补模板注释与测试覆盖。 |
| **2026-04-21** | **viz 稳定性**：对未配置 `viz.image_root` 的数据集在 viz 列表中默认跳过（避免浏览时触发 `/api/image` 报错）；同时修复 export 包 import-time re-export 引起的循环导入问题（`load_pil_for_metadata` partially initialized）。 |
| **2026-04-21** | **配置模板归并**：`metadata/templates/configs_minimal/datasets/` 下多份 e2e/demo 数据集模板合并为 `unified/dataset.yaml`（默认上游起点；metadata_noqa / metadata_qa / grounding+LLM 等场景以文件内分块注释说明），并更新 `metadata/README.md` 示例路径。 |
| **2026-04-20** | **小批量验证与调试体验**：CLI 新增 `--max-records-total`（跨所有 dataset/split 总量上限）与 `--max-records-per-split`（每 split 上限），便于快速抽样验证；`ExpressionRefreshQwenAdapter` 支持 `print_llm_output` 将模型 JSON 输出直接打印到 stderr（不落盘）；文档同步更新 `config_yaml_zh.md`/`metadata/README.md` 并新增 UT 覆盖。 |
| **2026-04-20** | **去重 adapter 接入模板**：新增 `ObjectDedupExactAdapter`（按 `bbox_xyxy_norm_1000` + `phrase` 完全一致去重并重写 queries），并将其作为推荐步骤接入 grounding+LLM 刷新链（见 `metadata/templates/configs_minimal/datasets/unified/dataset.yaml` 底部注释块）放在 LLM refresh 之后。 |
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
- [ ] **长期**：`ProcessPoolExecutor` 等并行能力增强另开 design 轮次，不与当前 strict 固化混改。

---

## 活跃计划目录（索引）

| 目录 | 状态 |
|------|------|
| `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/` | **已交付（实现 + 自测 + 收束）**：resume 跳过阶段性能优化 + tqdm 并行显示稳定性修复；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/` | **已交付（实现 + 自测 + 收束）**：新增非侵入性能埋点（仅 `--timing` 汇总，不影响进度条）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/` | **已交付（实现 + 自测 + 收束）**：training pipeline 批量写盘/批量 checkpoint + 冗余 dump 清理；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1428_strict_cleanup/` | **已交付（实现 + 自测 + 收束）**：strict 冗余参数清理与行为固化（仅支持 true）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1423_pipeline_refactor_batch4/` | **已交付（实现 + 自测 + 收束）**：QA task 分发可扩展化（显式 builder + 约定 fallback）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1421_pipeline_refactor_batch3/` | **已交付（实现 + 自测 + 收束）**：Pydantic 兼容入口收口补齐（loader/training_pack/chained）；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1418_pipeline_refactor_batch2/` | **已交付（实现 + 自测 + 收束）**：`cli` training pipeline 串并行流程去重（helper 收口），语义不变；见该目录 `change_log.md` |
| `metadata/plans/2026-04-21_1301_pipeline_refactor_batch1/` | **已交付（实现 + 自测 + 收束）**：内部重构加固（兼容收口、export 去重、异常与诊断增强）；见该目录 `change_log.md` |
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
