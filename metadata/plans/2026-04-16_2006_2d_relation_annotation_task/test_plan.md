## 测试方案（Test Plan）

### 测试范围

- 覆盖范围：
  - relation schema 新增 `relation_id` 后的生成、传递与读取行为
  - sample 级 metadata 输入契约是否满足新 annotation task 的消费要求
  - sample 内 relation edge 池筛选、edge 不复用与数量递减逻辑
  - 三类 QA（完整句方位描述、单轴选项判断、关系判断与纠正）的生成正确性
  - 指代表达与图像标记策略
  - 自定义输出格式（`question` / `answer` / `meta`）
  - 配置样例与文档同步项
- 不覆盖范围：
  - 训练效果、模型指标提升与大规模数据分布分析
  - 完整 prompt 模板库的语言润色与人工主观优选
  - 非本任务相关的已有 annotation task 全量回归

### 单元测试

- 用例列表：
  - `relation_id` 生成与透传
    - 所有 relation 均带 `relation_id`
    - 不同来源 relation 的 `relation_id` 生成格式一致
  - sample 级 relation 池筛选
    - 仅收集 `image-plane` relation
    - 同类对象在不可可靠消歧时不会进入 QA 候选池
  - edge 不复用
    - 同一个 sample 内多个 QA 不会复用同一真实 relation edge
  - 数量上限与递减策略
    - `sub_tasks` 数量被解释为上限
    - edge 不足时按优先级递减
    - 小比例随机性不会打破“不复用 edge”约束
  - 单轴题轴向采样
    - 显著轴明显时固定选主轴
    - 两轴显著性接近时按差值比例采样
  - 判断题构造
    - 正确 / 部分正确 / 错误三类断言构造符合规则
    - “部分正确”仅在更严格的显著性比值条件下允许出现
  - 指代表达与图像标记
    - 可唯一指代时支持文本与“文本+标记备注”两种路径
    - 不可唯一指代时强制走框标记路径
    - 最小标记原则生效
  - 输出格式
    - 每条 QA 至少包含 `question`、`answer`、`meta`
    - `meta` 中包含 `relation_id`、`qa_type`、`qa_style`
  - sample 跳过逻辑
    - 一条 QA 都生成不出时跳过
    - 能生成部分时保留部分

- 输入构造：
  - 最小 sample 级 metadata fixture
  - 至少 1 个 relation 足够支撑单类题的样例
  - relation 数量不足、无法满足 `1,1,1` 的样例
  - 可唯一指代 / 不可唯一指代 / 同类对象可消歧与不可消歧样例
  - 横纵显著性明显与接近的样例
  - 判断题可构造“正确 / 部分正确 / 错误”三类断言的样例

- 断言点：
  - 关系主键与追溯字段正确
  - 题型、数量、edge 分配符合设计
  - 输出结构完整且稳定
  - 跳过 / 保留部分的降级行为符合设计

### 集成测试

- 与 OpenSpatial 的对接点：
  - 新 annotation task 可被 pipeline 正常加载
  - `config/annotation/` 中的新示例配置可以表达三类 `sub_task`
  - sample 级 metadata 输入能被 task 正常消费
  - task 输出能在当前 annotation 流程中被正确写出或包装

- 需要的样例 Parquet / JSON：
  - 至少一份小规模 sample 级 metadata 测试输入
  - 至少一份包含多条 `image-plane` relation 的样例，用于验证 `1,1,1` 或更高上限下的 edge 分配
  - 至少一份 relation 边不足的样例，用于验证递减策略

- 预期输出与检查方式：
  - 新 task 能成功运行，不因输入契约变化报错
  - 当 relation 足够时，三类 QA 都可生成
  - 当 relation 不足时，仅减少数量，不复用 edge
  - 每条 QA 都带正确的 `relation_id` 和对应 `meta`
  - 示例配置运行结果与 `design.md` / `plan.md` 约束一致

### 质量门槛（Gate）

- 通过条件：
  - `plan.md` 中 6 个任务包均有对应测试项
  - relation schema、edge 分配、三类 QA 生成、指代表达策略、输出格式都有可执行验证
  - 新 task 的关键路径（加载、运行、输出）至少通过一条集成验证
  - 文档同步项中需更新的文档完成更新或明确声明无需更新

- 失败时如何定位：
  - 若 relation 追溯失败，优先检查 `relation_id` 的生成与传递链路
  - 若 QA 数量异常，优先检查 relation 池筛选、edge 不复用与数量递减逻辑
  - 若判断题行为异常，优先检查断言构造与显著性比值阈值
  - 若指代或画框异常，优先检查唯一指代判定与最小标记策略
  - 若输出结构异常，优先检查 QA 结构化输出与 pipeline 接线位置

