## 方案设计（Design）

### 背景与目标

- 背景：
  - `metadata` 子工程当前已经能够基于现有 Grounding 数据抽取对象指代表达、2D 几何信息，并计算 `image_plane` 下的 2D 空间关系。
  - OpenSpatial 主工程已有 annotation pipeline 与 `sub_tasks` 机制，适合承载多种问法的 QA 生成任务。
  - 当前尚缺少一条从 metadata sample 直接进入 annotation task，并在 sample 粒度生成 2D 空间关系 QA 的标准链路。
- 目标（必须可验证）：
  - 设计一个全新的 annotation task，用于从单个 metadata sample 生成三类 2D 空间关系 QA：
    - 完整句方位描述
    - 单轴选项判断
    - 关系判断与纠正
  - 明确 metadata 到 annotation task 的输入契约，保证 task 能直接消费 sample 级 metadata，而不依赖对象对展平输入。
  - 明确 task 的输出格式，保证每条 QA 至少包含最终 `question`、`answer` 与可追溯的 `meta`。
  - 明确 relation 选样、数量控制、消歧、图像标记和 edge 不复用等关键规则，为后续 `plan.md` 与实现提供单一事实来源。
- 非目标（明确不做什么）：
  - 本文档不定义实现步骤、代码拆分、测试映射与交付顺序；这些内容属于后续 `plan.md` 与 `test_plan.md`。
  - 本文档不展开 prompt 模板的完整示例库；三类 QA 的具体例子与模板细节将在后续设计补充。
  - 本文档不讨论训练配方、模型参数或评测执行流程。

### 术语与约束

- 术语：
  - `sample`：一条 metadata 记录，对应单张图像及其 objects / relations / aux。
  - `relation edge`：`sample.relations` 中的一条真实关系边，作为单条 QA 的真值来源。
  - 三类 QA：
    - 完整句方位描述
    - 单轴选项判断
    - 关系判断与纠正
  - 可唯一指代：anchor / target 能仅通过文本稳定定位到对应对象。
  - 最小标记原则：仅在消歧确有需要时才在图像上增加框标记。
- 输入约束：
  - task 输入粒度是 `sample`，不做对象对展平。
  - 默认使用所有 `image-plane` relation 作为候选 relation 池，不限制 relation 来源。
  - 同类对象对仅在可可靠消歧时允许出题。
  - annotation task 不重新计算 relation truth，而是消费 metadata 中已有的真实关系与证据。
- 输出约束：
  - task 输出采用自定义 QA 结构，而不是仅依赖现有 annotation 默认输出形态。
  - 每条 QA 必须保留最终 `question`、`answer` 和 `meta`。
  - `meta` 中以 `relation_id` 作为 relation 追溯主键。
- 兼容性要求（与 OpenSpatial 主工程的边界）：
  - 新功能采用一个全新的 annotation task，仅复用现有 pipeline 的加载与运行机制。
  - 三类问法对应三个 `sub_task`，通过配置控制每类问法的生成数量上限。
  - 仍需与 annotation pipeline 的 sample 处理、图像标记和 task 调度方式兼容。

### 数据结构 / 接口契约

- 输入数据样例（最小字段集）：
  - 顶层必须至少提供：
    - `sample.sample_id`
    - `sample.image.path`
    - `sample.image.coord_scale`
    - `objects`
    - `relations`
    - `aux`
  - `objects` 中必须至少提供：
    - `object_id`
    - 用于生成指代表达的文本信息（如 `phrase` / `category`）
    - 2D 几何信息（bbox 或 point）
  - `relations` 中必须至少提供：
    - `relation_id`
    - `anchor_id`
    - `target_id`
    - `predicate`
    - `ref_frame`
    - 复合关系信息（如存在）
    - 关系证据
  - `aux` 中应保留对象过滤与 relation 过滤的留痕，以支撑追溯与质检。
- 输出数据样例（最小字段集）：
  - 一个 sample 输出 0 到 N 条 QA。
  - 每条 QA 至少包含：
    - `question`
    - `answer`
    - `meta`
  - `meta` 至少包含：
    - `relation_id`
    - `qa_type`
    - `qa_style`
    - 与图像标记/指代表达选择相关的追溯信息
- 错误处理与降级策略：
  - `sub_tasks` 中配置的 QA 数量表示上限，不要求每个 sample 全部达成。
  - 若当前 sample 在 relation edge 数量、消歧约束或题型构造条件下只能生成部分 QA，则保留已生成部分。
  - 若当前 sample 一条 QA 都生成不出，则跳过该 sample。
  - edge 不足时，按既定优先级递减各类 QA 的数量，并引入少量随机性，避免某一类 QA 长期被系统性压缩。
  - 为支撑上述输出追溯，metadata schema 需要新增统一的 `relation_id` 字段，适用于所有 relation，命名格式为 `relation#{id}`。

### 核心流程

- 流程概览（可用伪代码/步骤）：
  1. 读取一个 metadata sample。
  2. 从 sample 中收集可用的 `image-plane` relation，形成 relation 池。
  3. 基于同类对象、可消歧性、题型适配条件等规则筛选出每类 QA 的可用 edge 候选。
  4. 在 sample 内为三类 `sub_task` 分配互不重复的真实 relation edge。
  5. 若 edge 不足，则按优先级与小比例随机性缩减各类 QA 数量。
  6. 对每条被选中的 edge，按对应问法生成 `question`、`answer` 与 `meta`。
  7. 根据唯一指代与否，决定使用纯文本指代还是“文本 + 标记备注”，并按最小标记原则选择是否画框。
  8. 输出当前 sample 的 QA 列表；若列表为空，则跳过该 sample。
- 关键算法/规则：
  - relation edge 不复用：
    - 同一个 sample 内，所有生成的 QA 都必须使用不同的真实 relation edge。
    - 若配置为 `2,2,2`，则最多需要 6 条不同 edge。
  - 数量递减规则：
    - 默认优先级为：
      - 单轴选项判断
      - 完整句方位描述
      - 关系判断与纠正
    - edge 不足时，优先减少高难度问法数量，同时加入少量随机性。
  - 判断题分布：
    - 默认错误 / 部分正确 / 正确约为 50% / 15% / 35%。
  - 部分正确构造：
    - 使用比 relation 计算更严格的显著性比值阈值。
    - 仅在两轴显著性差异较小、确有“部分正确”语义空间时构造此类题。
  - 单轴题轴向选择：
    - 若某一轴显著性明显更强，则固定使用该轴。
    - 若两轴显著性接近，则按两轴差值大小做概率采样。
  - 指代表达与图像标记：
    - 可唯一指代时，按 7:3 在“纯文本指代”与“文本 + 标记备注”之间采样。
    - 不可唯一指代时，固定使用框标记消歧。
    - 采用最小标记原则，不强制限制为最多一个框；若两端都无法唯一指代，允许两端都使用框标记。
- 可配置项：
  - 三类 `sub_task` 的数量上限
  - 判断题三种断言类型的分布
  - 单轴题横轴 / 纵轴采样参数
  - 唯一指代下文本 / 标记的采样比例
  - 部分正确判定的显著性比值阈值
  - edge 不足时的优先级与随机性强度

### 风险与未决问题

- 风险：
  - 当前 metadata 的 relation 语义已经足够支持 QA 生成，但若 `relation_id` 未统一引入，将直接影响 QA 追溯与后续质检。
  - 同类对象和复杂场景中，唯一指代与最小标记原则可能相互冲突，需要在实现阶段仔细验证。
  - 判断题中的“部分正确”高度依赖显著性阈值设计，阈值不稳会直接影响题目质量。
  - 三类 QA 的数量上限、edge 不复用约束与 sample 内 relation 稀缺同时存在时，可能导致某些样本产出率较低。
- 未决问题（需要和你确认的点）：
  - 无。本轮 design 所需的关键设计约束已经对齐；后续若有新增问题，应在 `plan.md` 前继续补充。

