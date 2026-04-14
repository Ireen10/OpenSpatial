# OpenSpatial 标注（Annotations）专题教程

本文面向需要在 OpenSpatial 中**新增标注任务**、做**QA 数据生产与质检**、以及设计 **Prompt 模板**的开发者。内容与仓库内 [Development Guide](development_guide.md)、[Quick Start](quick_start.md) 对齐，并补充「数据结构」与实操方法论。

---

## 一、标注在流水线中的位置

- **入口**：`python run.py --config <yaml> --output_dir <dir>`（参见 Quick Start）。
- **阶段**：完整流水线一般为 `filter_stage → localization_stage → scene_fusion → group_stage（多视角）→ annotation_stage`。仅生成标注时，可使用 `config/annotation/demo_*.yaml`，将 `data_dir` 指向上游阶段已写好的 Parquet。
- **任务解析**：`annotation_stage` 中的 `file_name` 映射到 `task.annotation.<file_name>`，YAML 里的 `method` 必须是该模块中的**类名**（惯例为 `AnnotationGenerator`）。详见 Development Guide §1、§9。

---

## 二、三类数据结构（输入 / 运行时 / 输出）

标注任务的本质是：**读入一行 Parquet（Python 里为 `dict` 形式的 sample）→ 构建 `SceneGraph` → 子任务 handler 产出若干条 `(prompt, QA_image(s), QuestionType)` → 转成 `messages` 等字段写回**。下面分三层说明字段类型与约定。

### 2.1 数据结构 ①：标注阶段的输入（Parquet 行 / `example`）

输入即上一阶段（或预处理）写入的**一行样本**，在代码中多为 `pandas` 行转成的字典。单视角与多视角在字段「标量 vs 列表」上不同（与 [Quick Start §2.2](quick_start.md) 一致）。

**单视角（每行一图）——常见字段与类型**

| 字段 | 典型类型 | 说明 |
|------|-----------|------|
| `image` | `str` | RGB 图像路径 |
| `depth_map` | `str` | 深度图路径 |
| `pose` | `str` | 相机外参 4×4，`txt` 路径 |
| `intrinsic` | `str` | 内参 4×4，`txt` 路径 |
| `obj_tags` | `list[str]` | 实例标签，与 masks/boxes 对齐 |
| `bboxes_3d_world_coords` | `list[list[float]]` | 每物体 9 维 OBB：`[cx,cy,cz,xl,yl,zl,roll,pitch,yaw]`（世界系，Z-up，欧拉 zxy） |
| `depth_scale` | `int` / `float` | 深度量化缩放 |
| `is_metric_depth` | `bool` | 是否为米制深度（部分任务会跳过非米制） |
| `masks` | `list[str]` | 由定位等阶段产生的 mask 路径 |
| `bboxes_2d` | `list[list[int]]` | `[x1,y1,x2,y2]` |
| `pointclouds` | `list[str]` | 场景融合后每物体点云路径（如 `.pcd`） |

**多视角（每行一场景）——与单视角的差异**

| 字段 | 典型类型 |
|------|-----------|
| `image` | `list[str]`（每视角一路径） |
| `obj_tags` | `list[list[str]]`（每视角一列表） |
| `bboxes_3d_world_coords` | `list[list[list[float]]]` |
| 其余 `depth_map`、`pose`、`intrinsic`、`masks` 等 | 与视角数对齐的 `list[...]` |

**基类层面的最低要求**

- `BaseAnnotationTask.check_example`：至少要求存在 `image` 与非空 `obj_tags`。
- `BaseMultiviewAnnotationTask.check_example`：要求 `image, pose, intrinsic, obj_tags, masks, depth_map, bboxes_3d_world_coords` 均存在且**各列表长度一致**。

不同子任务依赖不同子集（例如距离类依赖点云与米制深度）；若条件不足，handler 应返回 `None`，该行可能被丢弃或产生 0 条 QA（取决于上层是否过滤空 `prompts`）。

---

### 2.2 数据结构 ②：运行时（`SceneGraph` 与 handler 契约）

**`SceneGraph`（`task/annotation/core/scene_graph.py`）**

- 由 `build_scene_graph(example)` 得到：单视角用 `SceneGraph.from_singleview_example`，多视角用 `SceneGraph.from_multiview_example`。
- **不落盘**：仅内存对象，封装 `views`、`nodes`、每物体在各视角下的 `view_appearances`（含 lazy 加载的 `mask`、相机系点云等）、`primary_view` 等。详见 Development Guide §6。

**`SUB_TASKS` 与 handler 返回值**

- 在任务类上声明 `SUB_TASKS = {"name": {"default": N, "handler": "_method"}}`；`BaseAnnotationTask.process` 按 YAML 里的 `sub_tasks` 次数调用 handler。
- **Handler 签名**：`_generate_xxx(self, graph)`。
- **返回值（单条）**：`(prompt, processed_image(s), QuestionType)`，其中 `QuestionType` 为 `open_ended` 或 `MCQ`（`task/annotation/core/question_type.py`）。
- **返回值（多条）**：`list` of `(prompt, image(s), QuestionType)`；或 `None` 表示跳过本次采样。

**`prompt` 字符串格式（硬约束）**

- 必须经过 `render_prompt()` 或等价逻辑，得到**恰好一段**可拆分的文本：  
  `"<question text> Answer: <answer text>"`  
  消息构建器用子串 **`"Answer: "`** 切分问与答；缺少该子串则该条会被丢弃。

**`processed_image` 形状**

- **单视角**：`{"bytes": <PNG bytes>}`（惯例来自 `convert_pil_to_bytes`）。
- **多视角**：`list[{"bytes": ...}, ...]`，与 `create_multiview_messages` 中 `<image>` 个数一致。

**多视角辅助返回值**

- 常见模式：`result = self._find_chain_and_mark(graph, num_views=N)` → `(meta, processed_images, marked_infos)`，再组 prompt。视角选择受 YAML 中 `max_num_views`、`min_rot_angle`、`min_translation` 等约束（Development Guide §4）。

---

### 2.3 数据结构 ③：标注产出（写入 Parquet 的字段与 flatten）

`BaseAnnotationTask.apply_transform` 在成功时向 `example` **就地**写入：

| 字段 | 类型（逻辑） | 说明 |
|------|----------------|------|
| `messages` | `list[list[dict]]` | 每条 QA 对应一组对话；元素为 `{"from": "human"|"gpt", "value": str}`。首条 human 的 `value` 以前缀 `"<image> "` 或 `"<image> <image> ..."` 开头（由 `message_builder` 负责） |
| `QA_images` | `list` | 与 `messages` 对齐；单视角为 `list[dict]`，多视角为 `list[list[dict]]` |
| `question_tags` | `list[list[str]]` | 与每条 QA 对齐；内容通常为 `[[QUESTION_TAG], ...]` |
| `question_types` | `list`（元素为 `QuestionType` 或可序列化为字符串） | 与每条 QA 对齐 |

**Flatten（一行多样本 → 多行）**

- `utils/data_utils.flatten_annotations(data, keep_keys)` 将 `keep_keys` 中**等长列表**列按索引拆开，**每行保留同一原始 `image` 列**（与 Development Guide §10.2 一致）。
- 管线中可通过配置 `keep_data_columns`（如 `messages`, `QA_images`, `question_tags`, `question_types`）控制展开列。
- 大批量时可按 `save_batch_size` 切成 `data_part_*.parquet`。

**`messages` 中单条对话的直观例子（单视角、单轮）**

```text
[
  {"from": "human", "value": "<image> How many chairs are visible?"},
  {"from": "gpt", "value": "3"}
]
```

多轮时 `prompt` 可为 `list[str]`，每条子串仍须含 `Answer: `；仅第一轮带 `<image>`（见 Development Guide §11）。

---

## 三、新增 Annotation Task（实操清单）

### 3.1 单视角任务

1. **新建任务类** `task/annotation/<your_task>.py`：继承 `BaseAnnotationTask`，类名匹配 YAML 的 `method`（推荐 `AnnotationGenerator`），设置 `QUESTION_TAG`、`SUB_TASKS`，实现各 `_generate_*` handler。
2. **可选覆盖**：`check_example`、`get_mark_config`、`build_scene_graph`、`create_messages_from_prompts`（默认单视角已够用）。
3. **注册模板**：在 `task/prompt_templates/<name>_prompt_templates.py` 中 `TemplateRegistry.register(...)`，并在 `task/prompt_templates/__init__.py` 中 `import` 该模块（Development Guide §3.2）。
4. **新增配置** `config/annotation/demo_<your_task>.yaml`：`annotation_stage` 中填写 `file_name`、`method`、`sub_tasks`、`filter_tags`、`scaling_factor`、`output_dir` 等。
5. **运行与检查**：`python run.py --config ...`；用 `visualize_server.py` 浏览（Development Guide §13）。

### 3.2 多视角任务

1. 继承 `BaseMultiviewAnnotationTask`，使用 `_find_overlapping_views` / `_find_view_chain` / `_find_chain_and_mark` 等工具组合视角与标记（Development Guide §4 表格）。
2. **必须**让 `processed_images` 与视角数一致，以便 `create_multiview_messages` 插入正确数量的 `<image>`。
3. YAML 中增加多视角参数：`max_num_views`、`min_rot_angle`、`min_translation`。

### 3.3 常见实现要点

- **视觉标记**：`VisualMarker` + `MarkConfig`；`mark_and_prompt` 可统一处理「是否画框/ mask」与 prompt 参数（见 `BaseAnnotationTask.mark_and_prompt`）。
- **MCQ**：可参考现有任务用 `_shuffle_mcq` 生成选项与正确答案字母。
- **线程安全**：多线程时 `VisualMarker` 已按线程隔离；避免在 handler 里共享可变全局状态。

---

## 四、QA 生产与质检（QA Production）

### 4.1 生产流程建议

1. **明确输入契约**：单视角还是多视角、是否米制深度、是否已有点云与 mask（见 §2.1）。
2. **小配置试跑**：`sub_tasks` 各设为 1，`use_multi_processing: false`，缩短迭代周期。
3. **全量跑**：打开多线程（注意 `num_workers` 与内存），必要时调 `save_batch_size`。
4. **Flatten**：若训练侧需要「一行一条对话」，在管线配置中启用对 `messages` 等列的 flatten（与仓库默认约定一致即可）。

### 4.2 质检维度（建议抽样表）

| 维度 | 检查什么 |
|------|-----------|
| **视觉对齐** | 标记颜色/框是否对应题干中的物体；多视角是否同一物体 |
| **可解析性** | 原始 `prompt` 是否均含 `Answer: `；`messages` 是否与预期轮数一致 |
| **答案可验证性** | 数值类是否与几何计算一致；比较类是否与深度/点云关系一致 |
| **语言与歧义** | 标签是否重复导致指代不明；是否需加 `filter_tags` 去掉 wall/floor 等 |
| **题型分布** | `question_types` 中 OE/MCQ 比例是否符合数据设计 |
| **分布与泄漏** | 模板句型是否过度单一；是否意外复制了仅内部可见的字段到 `value` |

### 4.3 工具

- **`python visualize_server.py --data_dir <output> --port 8888`**：按任务浏览 Parquet，查看图与多轮对话（Development Guide §13）。
- **对拍输入输出**：对同一 `image` 路径，比对上游 Parquet 与标注输出中的 `question_tags` / `messages` 条数是否满足 `sub_tasks` 配置。

---

## 五、Prompt 设计方法论

### 5.1 与框架强约束对齐

1. **一律产出** `"... Answer: ..."`** 形态**，否则无法进入 `messages`。
2. **占位符**：模板中用 `[A]`、`[B]`、`[X]` 等；`render_prompt(..., shared=..., q_args=..., a_args=...)` 会替换为字符串（Development Guide §7.3）。同一键在问句与答句中可分工时用 `q_args` / `a_args`。
3. **是非 / 条件题**：使用 `PromptTemplate(..., true_answers=[...], false_answers=[...])`，并调用 `render_prompt(..., condition=True/False)`；缺一侧列表会触发 `ValueError`（见 `prompt_template.py`）。

### 5.2 设计原则（建议）

- **先定义可计算的真值**：几何量、序关系、计数规则先在后端算清，再写「问法」；避免先写华丽问句再硬凑答案。
- **问法与视觉一致**：若题干引用「带标记的物体」，标记策略（mask/box/point）应与读者理解一致；`mark_prob` 小于 1 时需考虑「无标记」下的语言是否仍自洽。
- **模板多样化、语义等价**：同一语义多句 paraphrase，减少过拟合；用列表随机 `questions` / `answers`。
- **单位与数值格式**：与 `scaling_factor`、米/厘米随机策略等保持一致，避免答案精度漂移。
- **MCQ 干扰项**：干扰项应来自同场景、同类几何关系，避免「一眼假」；注意标签大小写与描述统一（现有任务多用 `lower()` 统一描述）。

### 5.3 模板注册与命名

- 注册名建议 **`"<task>.<variant>"`**（如 `distance.absolute_m`），与文件、任务模块一一对应，便于检索与 Code Review。
- 新增文件勿忘在 `task/prompt_templates/__init__.py` 中 import；`BaseAnnotationTask` 已依赖包级 import 触发注册。

---

## 六、与主文档的对应关系

| 主题 | 详见 |
|------|------|
| 流水线与任务解析、输出目录 | Development Guide §1、§9、§10 |
| SceneGraph、模板系统、Message Builder | Development Guide §6–§7、§11 |
| 预处理输出列、坐标系 | Development Guide §8；Quick Start §2 |
| 可视化调试 | Development Guide §13；Quick Start §4 |

---

## 七、自检清单（提交 PR 前）

- [ ] YAML 中 `file_name` / `method` 与 Python 模块、类名一致  
- [ ] 所有模板已注册且 `__init__.py` 已 import  
- [ ] 每条 prompt 含 `Answer: `；多轮子串同样满足  
- [ ] 单/多视角 `QA_images` 结构与 `create_*_messages` 预期一致  
- [ ] 小样本跑通 + `visualize_server` 目检通过  
- [ ] 文档或配置中说明本任务**强依赖的输入字段**（便于数据组备数）

---

*文档版本与仓库代码同步维护；若与源码行为不一致，以 `task/annotation/` 与 `task/annotation/core/` 下实现为准。*
