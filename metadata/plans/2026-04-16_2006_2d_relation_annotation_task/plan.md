## 执行计划（Plan）

### 交付物清单

- 文档：
  - `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/design.md`
  - `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/plan.md`
  - `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/test_plan.md`
  - `metadata/docs/qa_2d_spatial_relation_strategy_zh.md`（若需补充与实现一致的说明）
- 代码：
  - metadata schema 中新增统一的 `relation_id`
  - metadata enrich / adapter / bridge 层补齐 relation_id 生成与传递
  - 新增 2D spatial relation annotation task
  - 新增 prompt 模板与 task 配置
  - 必要的桥接/加载逻辑，使 annotation task 能直接消费 sample 级 metadata
- 配置：
  - 新 task 对应的 annotation 配置示例
  - 与采样比例、标记策略、阈值相关的配置项或常量
- 样例/fixtures：
  - 至少补充一组可用于验证 sample 级 QA 生成的测试样例或 fixture

### 文档同步（与本变更一并交付）

列出**必须随本变更更新或显式声明「无需更新」**的用户可见说明（路径写全，便于 reviewer 勾选）：

- [x] `metadata/docs/config_yaml_zh.md`（**无需更新**：未改 global/dataset schema、loader、CLI 语义）
- [ ] `metadata/docs/metadata_spec_v0_zh.md`（**推迟**：须补 `RelationV0.relation_id` 与样例；见 `change_log.md`）
- [x] `metadata/README.md`（**无需更新**：未改安装/命令/目录结构说明）
- [x] `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/test_plan.md`（本变更必写）
- [x] `metadata/docs/project_progress_zh.md`（整轮结束已更新）
- [x] 其他：`metadata/docs/qa_2d_spatial_relation_strategy_zh.md`（**无需更新**：与首轮实现无冲突表述）

约定：占位/未接线能力在文档中用明确措辞标出；**实现或删除该能力时，同一变更内**同步改写对应段落（见 `metadata/docs/docs_sync_convention_zh.md`）。

### 任务拆解

#### 任务 1：补齐 relation schema 与 sample 级输入契约

- 目标：
  - 为所有 relation 引入统一的 `relation_id` 字段。
  - 明确并实现 annotation task 需要消费的 sample 级 metadata 输入契约。
- 修改/新增的文件：
  - `metadata/src/openspatial_metadata/schema/metadata_v0.py`
  - relation 产生/传递相关的 metadata 代码
  - 必要时补充 schema / validate / docs
- 完成条件：
  - 所有 relation 均可稳定携带 `relation_id`
  - annotation task 在 sample 粒度下所需的最小字段已能从 metadata 中直接读取
  - 对外 schema 变化已在文档中同步说明

#### 任务 2：建立 relation 池筛选与 edge 分配逻辑

- 目标：
  - 在 sample 内收集可用的 `image-plane` relation
  - 为三类问法构建可用 edge 候选池
  - 实现“同 sample 内 QA 不复用 relation edge”的分配约束
  - 实现 edge 不足时的数量递减策略与小比例随机性
- 修改/新增的文件：
  - 新 annotation task 主文件
  - 如有必要，新增 task 内部 helper
  - 相关测试文件
- 完成条件：
  - `sub_tasks` 数量被解释为上限
  - 在 sample 内，不同 QA 不会复用同一真实 edge
  - edge 不足时，数量削减符合已确认优先级与随机性原则

#### 任务 3：实现三类 QA 的 sample 级生成逻辑

- 目标：
  - 分别实现：
    - 完整句方位描述
    - 单轴选项判断
    - 关系判断与纠正
  - 每类问法都基于真实 relation edge 生成 `question`、`answer` 与 `meta`
- 修改/新增的文件：
  - 新 annotation task 主文件
  - 对应 prompt 模板文件
  - 必要的 task 配置示例
- 完成条件：
  - 三类问法均能独立生成
  - 判断题的正确 / 部分正确 / 错误分布符合设计
  - 单轴题的轴向采样符合显著轴优先、接近时按比例随机的规则

#### 任务 4：实现指代表达与图像标记策略

- 目标：
  - 实现唯一指代与非唯一指代的分流策略
  - 实现 7:3 的文本 / 文本+标记采样
  - 实现最小标记原则
- 修改/新增的文件：
  - 新 annotation task 主文件
  - 可能需要的指代表达辅助函数
  - 配置或常量文件
- 完成条件：
  - 可唯一指代与不可唯一指代场景都能稳定处理
  - 图像标记策略与设计一致
  - 相关概率或阈值可统一管理

#### 任务 5：定义并接线自定义 QA 输出格式

- 目标：
  - 为每条 QA 产出稳定的 `question` / `answer` / `meta`
  - `meta` 中以 `relation_id` 为 relation 主追溯键
  - 明确与现有 annotation pipeline 的接线方式
- 修改/新增的文件：
  - 新 annotation task 主文件
  - 如有必要，annotation pipeline 的接线位置
  - 测试与文档
- 完成条件：
  - 输出结构稳定可序列化
  - 每条 QA 都带完整的最终答案文本与必要追溯信息
  - sample 完全无法出题时会被跳过；部分可生成时保留部分

#### 任务 6：补齐配置、测试与文档同步

- 目标：
  - 提供可运行的 annotation 配置示例
  - 编写覆盖 sample 粒度、edge 分配、题型生成、输出格式的测试
  - 同步更新对外文档
- 修改/新增的文件：
  - `config/annotation/` 下的新配置文件
  - `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/test_plan.md`
  - 相关测试文件 / fixture
  - 需要更新的 docs
- 完成条件：
  - 测试计划与实现项一一对应
  - 配置示例可表达三类 `sub_task`
  - 文档同步项已逐项勾选完成或明确声明无需更新

### 里程碑与回滚

- 里程碑：
  - M1：`relation_id` 与输入契约打通
  - M2：sample 内 relation 池筛选与 edge 分配完成
  - M3：三类 QA 生成逻辑完成
  - M4：输出格式、配置、测试与文档同步完成
- 回滚策略（如何撤销、如何验证恢复）：
  - 若 schema 变更导致下游不兼容，优先回滚 `relation_id` 相关改动，并验证现有 metadata enrich / 读取逻辑恢复原状。
  - 若新 task 影响 annotation pipeline，回滚新 task 与新配置文件，并验证现有 annotation task（例如 `position`）仍可正常运行。
  - 若输出格式接线引入兼容问题，回滚自定义输出接线，仅保留不影响现有任务的 schema/文档改动，再逐步重上。

---

## 收束说明（首轮实现，2026-04-17）

本轮按 **Design → Plan → Test plan → 实现 → 自测** 已收口：**可交付的首版** 2D 空间关系 annotation task 与 `relation_id` 链路已落地；细节与偏差见同目录 **`change_log.md`**。

### 文档同步勾选（本轮结论）

- [x] `metadata/plans/2026-04-16_2006_2d_relation_annotation_task/test_plan.md`（测试项与实现对齐；gate 为聚焦单测，见 `change_log.md`）
- [x] `metadata/docs/project_progress_zh.md`（整轮收束后已更新）
- [ ] `metadata/docs/metadata_spec_v0_zh.md`：**推迟**——需补 `RelationV0.relation_id` 与对外示例，非阻塞发布本 task
- [ ] `metadata/docs/config_yaml_zh.md`：**无需更新**（未改 dataset/global loader 语义）
- [ ] `metadata/README.md`：**无需更新**（未改安装/CLI 目录说明）
- [x] `metadata/docs/qa_2d_spatial_relation_strategy_zh.md`：**无需随代码改**（策略层与实现无冲突表述）

### 里程碑对照

- M1 `relation_id` 与输入契约：**已完成**（见 `change_log.md`）
- M2 relation 池与 edge 分配：**已完成**（含 tier 排序与不复用边）
- M3 三类 QA：**已完成**（首轮模板与规则；后续可迭代润色）
- M4 配置、测试、文档：**已完成**（对外 spec 补档单列推迟项）

