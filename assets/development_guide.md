# OpenSpatial Development Guide

This guide covers how to extend OpenSpatial with new annotation tasks, pipeline stages, prompt templates, and data preprocessing scripts.

---

## 1. Architecture Overview

```
run.py  (CLI entry)
  │
  ▼
BasePipeline  (pipeline/base_pipeline.py)
  │  Reads YAML config → builds task queue → executes stages sequentially
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage execution order (defined in YAML):                   │
│                                                             │
│  flatten_stage ─► filter_stage ─► localization_stage        │
│       ─► scene_fusion_stage ─► group_stage                  │
│       ─► annotation_stage                                   │
│                                                             │
│  Each stage contains one or more tasks.                     │
│  Each task is a Python class loaded via file_name + method. │
└─────────────────────────────────────────────────────────────┘
```

**Task resolution**: `get_task_instance()` in `utils/common.py` maps YAML config to Python classes:

```
stage_name: annotation_stage  →  module: task.annotation.<file_name>
task method: AnnotationGenerator  →  class: AnnotationGenerator
```

The convention strips `_stage` suffix from stage name to get the package path:
`task.{stage_name[:-6]}.{file_name}.{method}`

---

## 2. Class Hierarchy

```
BaseTask                              (task/base_task.py)
├── run(dataset) / _run_multi_processing(dataset)
├── apply_transform(example, idx) → (example, bool)   [abstract]
│
├── BaseAnnotationTask                (task/annotation/core/base_annotation_task.py)
│   ├── Singleview annotation base
│   ├── SUB_TASKS dispatch, SceneGraph, VisualMarker, PromptTemplate
│   ├── process(graph, example) → (prompts, images, tags, types)
│   │
│   └── BaseMultiviewAnnotationTask   (task/annotation/core/base_multiview_task.py)
│       ├── Multiview annotation base
│       ├── View selection with pose diversity check
│       ├── 2D ↔ 3D projection utilities
│       └── _find_view_chain / _find_overlapping_views / _build_view_meta
│
├── BoxFilter3D                       (task/filter/3dbox_filter.py)
├── SampleFlattener                   (task/flatten/flatten.py)
├── SampleGrouper                     (task/group/group.py)
├── DepthBackProjection               (task/scene_fusion/depth_back_projection.py)
└── Localizer / SAM2Refiner           (task/localization/*.py)
```

---

## 3. Adding a New Singleview Annotation Task

### 3.1 Create the task file

Create `task/annotation/my_task.py`:

```python
import random
from .core.base_annotation_task import BaseAnnotationTask
from .core.question_type import QuestionType
from utils.image_utils import convert_pil_to_bytes


class AnnotationGenerator(BaseAnnotationTask):

    QUESTION_TAG = "MyTask"           # Tag stored in output parquet
    SUB_TASKS = {
        "my_sub_task_oe":  {"default": 1, "handler": "_generate_oe"},
        "my_sub_task_mcq": {"default": 1, "handler": "_generate_mcq"},
    }

    def check_example(self, example) -> bool:
        """Optional: add task-specific validation on top of the base check."""
        if not super().check_example(example):
            return False
        # e.g. require at least 2 objects
        return len(example["obj_tags"]) >= 2

    def get_mark_config(self):
        """Optional: customize visual marker types."""
        from .core.visual_marker import MarkConfig
        return MarkConfig(mark_types=["mask", "box"])

    # ── Handlers (dispatched by SUB_TASKS) ────────────────────

    def _generate_oe(self, graph):
        """Generate one open-ended QA sample.

        Args:
            graph: SceneGraph built from the current example.

        Returns:
            (prompt_str, image_bytes_dict, QuestionType) or None to skip.
        """
        nodes = list(graph.nodes.values())
        if len(nodes) < 2:
            return None

        a, b = random.sample(nodes, 2)
        prompt = self.render_prompt(
            "my_task.open_ended",
            shared={"A": a.tag, "B": b.tag},
        )
        image_bytes = {"bytes": convert_pil_to_bytes(graph.primary_view.image)}
        return prompt, image_bytes, QuestionType.OPEN_ENDED

    def _generate_mcq(self, graph):
        # Similar to _generate_oe but returns QuestionType.MCQ
        ...
```

**Key points**:
- Class **must** be named to match the `method` field in YAML (typically `AnnotationGenerator`)
- `SUB_TASKS` dict maps sub-task names to handler methods; the pipeline calls each handler N times based on YAML `sub_tasks` config
- Handlers return `(prompt, image, QuestionType)` or `None` to skip
- `graph` is a `SceneGraph` object with `.nodes`, `.views`, `.primary_view`, `.obj_tags`, etc.

### 3.2 Register prompt templates

Create `task/prompt_templates/my_task_prompt_templates.py`:

```python
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

my_task_questions_oe = [
    "What is the relationship between [A] and [B]?",
    "Describe how [A] relates to [B].",
]

my_task_answers_oe = [
    "[X]",
    "The relationship is [X].",
]

TemplateRegistry.register("my_task.open_ended", PromptTemplate(
    questions=my_task_questions_oe,
    answers=my_task_answers_oe,
))
```

**Template placeholders**: Use `[X]`, `[A]`, `[B]`, etc. These are filled by `render_prompt()` via `shared`, `q_args`, `a_args` parameters.

**Conditional templates**: For true/false style QA, use `true_answers` / `false_answers`:

```python
TemplateRegistry.register("my_task.yesno", PromptTemplate(
    questions=["Is [A] bigger than [B]?"],
    true_answers=["Yes, [A] is bigger."],
    false_answers=["No, [B] is bigger."],
))
# Call with: self.render_prompt("my_task.yesno", condition=True/False, ...)
```

**Auto-registration**: Templates are loaded via `import task.prompt_templates` in `BaseAnnotationTask.__init__`. Add your file to `task/prompt_templates/__init__.py`:

```python
from . import my_task_prompt_templates  # noqa: F401
```

### 3.3 Create YAML config

Create `config/annotation/demo_my_task.yaml`:

```yaml
dataset:
  modality: image
  dataset_name: image_base
  data_dir: /path/to/singleview_processed.parquet

pipeline:
  file_name: base_pipeline
  class_name: BasePipeline

  stages:
    annotation_stage:
      -
        file_name: my_task
        method: AnnotationGenerator
        scaling_factor: 1
        filter_tags: ["ceiling", "floor", "wall", "object"]
        sub_tasks:
          my_sub_task_oe: 1
          my_sub_task_mcq: 1
        use_multi_processing: false
        num_workers: 8
        output_dir:
```

### 3.4 Run

```bash
python run.py --config config/annotation/demo_my_task.yaml --output_dir output/
```

---

## 4. Adding a New Multiview Annotation Task

Multiview tasks extend `BaseMultiviewAnnotationTask` which provides view selection and 2D-3D projection utilities.

Create `task/annotation/multiview_my_task.py`:

```python
import random
from .core.base_multiview_task import BaseMultiviewAnnotationTask
from .core.visual_marker import MarkConfig
from .core.question_type import QuestionType


class AnnotationGenerator(BaseMultiviewAnnotationTask):

    QUESTION_TAG = "MyMultiviewTask"
    SUB_TASKS = {
        "pair_comparison": {"default": 1, "handler": "_generate_pair"},
    }

    def get_mark_config(self):
        return MarkConfig(mark_types=["mask", "box"])

    def _generate_pair(self, graph):
        """Find 2 objects across 2 views and compare them."""
        # _find_chain_and_mark handles: view selection → meta building → marking
        result = self._find_chain_and_mark(graph, num_views=2)
        if result is None:
            return None

        meta, processed_images, marked_infos = result
        prompt = self.render_prompt(
            "my_multiview.pair",
            shared={"A": marked_infos[0][0], "B": marked_infos[1][0]},
        )
        return prompt, processed_images, QuestionType.OPEN_ENDED
```

**Multiview-specific config** (YAML):

```yaml
max_num_views: 400         # Max views to load per scene
min_rot_angle: 15.0        # Min rotation angle (degrees) between selected views
min_translation: 0.0       # Min camera distance between selected views
```

**Multiview helper methods** (inherited from `BaseMultiviewAnnotationTask`):

| Method | Description |
|---|---|
| `_find_overlapping_views(graph, N)` | Find one object visible in N diverse views |
| `_find_view_chain(graph, N)` | Find N different objects, each in a different view, connected by shared views |
| `_find_chain_and_mark(graph, N)` | Chain + build meta + mark objects (most common entry point) |
| `_build_view_meta(graph, node_views)` | Extract image/mask/tag/pointcloud/bbox per view |
| `_mark_per_view(meta, mark_type)` | Apply visual markers to each view image |
| `backproject_2d_to_3d(...)` | Depth map → 3D world coordinates |
| `project_3d_to_2d(...)` | 3D world → 2D pixel coordinates |
| `_check_pose_diversity(...)` | Verify rotation/translation diversity |

---

## 5. Adding a New Pipeline Stage

Pipeline stages are non-annotation processing steps (filter, localize, fuse, etc.).

### 5.1 Create the task file

Create `task/<stage_type>/my_stage.py`:

```python
from task.base_task import BaseTask


class MyProcessor(BaseTask):

    def __init__(self, args):
        super().__init__(args)
        self.my_param = args.get("my_param", "default_value")

    def apply_transform(self, example, idx):
        """Process one DataFrame row.

        Args:
            example: dict from one parquet row.
            idx: row index.

        Returns:
            (modified_example, True) to keep, or (None, False) to drop.
        """
        # Your processing logic here
        example["new_field"] = compute_something(example)
        return example, True
```

### 5.2 Register in YAML

```yaml
pipeline:
  stages:
    my_custom_stage:           # Stage name must end with '_stage'
      -
        file_name: my_stage    # Maps to task/<stage_type>/my_stage.py
        method: MyProcessor    # Class name
        my_param: value
        output_dir:
```

**Stage naming convention**: The stage name in YAML must end with `_stage`. The pipeline strips this suffix to resolve the Python package: `my_custom_stage` → `task.my_custom.my_stage`.

---

## 6. SceneGraph Data Model

`SceneGraph` (`task/annotation/core/scene_graph.py`) is the runtime representation of a scene, built from one parquet row. It is never serialized.

```
SceneGraph
├── views: Dict[int, ViewMeta]         # Camera views (image, pose, intrinsic, depth)
├── nodes: Dict[str, SceneNode]        # Objects (tag, 3D box, view appearances)
│   └── view_appearances: Dict[int, ViewAppearance]  # Per-view mask, bbox_2d, pointcloud
├── obj_tags: List[str]                # All object tags
├── duplicate_tags: Dict[str, int]     # Tags appearing more than once
├── primary_view: ViewMeta             # First view (singleview shortcut)
└── box_to_view_proj: Dict[str, List[int]]  # Node → visible view indices
```

**Factory methods**:
- `SceneGraph.from_singleview_example(example)` — for singleview tasks
- `SceneGraph.from_multiview_example(example, max_num_views=400)` — for multiview tasks

**Lazy loading**: `ViewMeta.image`, `ViewMeta.pose`, `ViewAppearance.mask`, `ViewAppearance.pointcloud_camera` are `@cached_property` — loaded on first access only.

---

## 7. Prompt Template System

Templates decouple QA text from task logic.

### 7.1 Core classes

- **`PromptTemplate`**: Holds question/answer template lists with `[X]` placeholders
- **`TemplateRegistry`**: Global thread-safe registry keyed by `"task.variant"` names

### 7.2 Usage in tasks

```python
# Register (in prompt_templates/xxx.py):
TemplateRegistry.register("task.variant", PromptTemplate(
    questions=["Is [A] near [B]?"],
    answers=["[X]"],
))

# Use (in annotation task):
prompt = self.render_prompt("task.variant", shared={"A": "chair", "B": "table", "X": "Yes"})
# → "Is chair near table? Answer: Yes"
```

### 7.3 Placeholder conventions

| Placeholder | Typical usage |
|---|---|
| `[A]`, `[B]`, `[C]` | Object names/descriptions |
| `[X]` | Answer value or target object |
| `[Y]` | MCQ option list |
| `[T]` | Comma-separated tag list |
| `[D]` | Distance/measurement value |

---

## 8. Adding a New Dataset Preprocessor

Dataset preprocessors convert raw dataset formats into the OpenSpatial parquet schema.

### 8.1 Create preprocessor

Create `data_preprocessing/<dataset_name>/prepare_<dataset_name>.py`.

**Required output schema** (per-image row for singleview, per-scene row for multiview):

| Column | Type | Description |
|---|---|---|
| `image` | str / list[str] | Image file path(s) |
| `obj_tags` | list[str] / list[list[str]] | Object tag names |
| `bboxes_2d` | list[list] / list[list[list]] | 2D bounding boxes `[x1,y1,x2,y2]` |
| `bboxes_3d` | list[list] / list[list[list]] | 3D OBB `[cx,cy,cz,xl,yl,zl,roll,pitch,yaw]` |
| `masks` | list[str] / list[list[str]] | Mask file paths |
| `depth_map` | str / list[str] | Depth map file path(s) |
| `depth_scale` | float / list[float] | Depth scaling factor(s) |
| `pose` | str / list[str] | 4x4 camera-to-world extrinsic matrix (txt) |
| `intrinsic` | str / list[str] | 4x4 intrinsic matrix (txt) |

### 8.2 Coordinate conventions

- **World coordinate system**: Z-up, ground parallel to XY plane
- **Camera coordinate system**: OpenCV convention (X-right, Y-down, Z-forward)
- **Pose**: 4x4 camera-to-world matrix, saved as `.txt` via `np.savetxt()`
- **Intrinsic**: 4x4 matrix (3x3 K expanded with identity row/col), saved as `.txt`
- **3D OBB Euler angles**: `[roll, pitch, yaw]` in **zxy** intrinsic order

### 8.3 Create preprocessing config

Create `config/preprocessing/demo_preprocessing_<dataset_name>.yaml` with the full pipeline:
filter → localize → scene_fusion → (optionally group for multiview).

---

## 9. Config System

### 9.1 YAML loading and namespace conversion

`run.py` loads YAML configs with `DuplicateKeySafeLoader`, which preserves duplicate mapping keys as ordered list entries (used for multiple tasks in the same stage). The raw dict is then recursively converted to `SimpleNamespace` via `dict_to_namespace()`, enabling dot-access (`config.pipeline.stages`).

```
YAML file  ─►  DuplicateKeySafeLoader  ─►  Python dict  ─►  dict_to_namespace()  ─►  SimpleNamespace
```

### 9.2 `data_dir` supports `str | list[str]`

When `data_dir` is a single path, the pipeline runs once. When it is a list of paths, `run.py` iterates over each parquet file and runs a separate pipeline instance per file, outputting to `part_1/`, `part_2/`, etc.:

```yaml
# Single file
data_dir: /data/batch_0.parquet

# Multiple files — pipeline runs once per file
data_dir:
  - /data/batch_0.parquet
  - /data/batch_1.parquet
  - /data/batch_2.parquet
```

### 9.3 Config validation

`validate_config()` checks:
- `pipeline` and `pipeline.stages` fields exist
- Each stage value is a list of dicts
- Each task dict contains `method` and `output_dir` fields

### 9.4 Output directory resolution

```
output_dir (CLI arg)
  └── {pipeline.file_name}_{config_file_stem}/     # e.g. base_pipeline_demo_counting/
        └── {stage_name}/                           # e.g. annotation_stage/
              └── {task_name}/                      # e.g. counting/
                    └── data.parquet
```

If a task specifies `output_dir` in YAML, that path is used instead of the auto-generated one.

---

## 10. Output Format

### 10.1 Annotation output schema

After annotation, each output parquet row contains:

| Column | Type | Description |
|---|---|---|
| `image` | str / list[str] | Original image path(s) |
| `messages` | list[dict] | QA conversation: `[{"from": "human", "value": ...}, {"from": "gpt", "value": ...}]` |
| `QA_images` | dict / list[dict] | Annotated image(s) as `{"bytes": <png_bytes>}` |
| `question_tags` | list[str] | Task category tags (e.g. `["Counting"]`, `["Distance"]`) |
| `question_types` | str | `"open_ended"` or `"MCQ"` |

### 10.2 Annotation flattening

A single input row may generate multiple QA pairs (e.g. 3 counting questions). The `flatten_annotations()` function in `utils/data_utils.py` explodes list-valued columns into one row per QA pair:

```
Before:  1 row with messages=[msg1, msg2, msg3]
After:   3 rows, each with messages=msg1 / msg2 / msg3
```

The `keep_data_columns` config controls which columns are flattened (default: `messages`, `QA_images`, `question_tags`, `question_types`). The `image` column is always preserved.

### 10.3 Batch saving

When flattened output exceeds `save_batch_size` (default 1000), the pipeline splits it into multiple parquet part files:

```
data.parquet          → data_part_0.parquet, data_part_1.parquet, ...
```

Configure via YAML:

```yaml
save_batch_size: 1000
keep_data_columns: ["messages", "QA_images", "question_tags", "question_types"]
```

---

## 11. Message Builder

The message builder (`task/annotation/core/message_builder.py`) converts raw prompt strings into structured conversation format.

### 11.1 Prompt format

`render_prompt()` produces a string in the format:

```
<question text> Answer: <answer text>
```

The message builder splits on `"Answer: "` to separate question and answer.

### 11.2 Singleview messages

`create_singleview_messages()` prepends a single `<image>` tag to the question:

```python
# Input prompt:  "How many chairs? Answer: 3"
# Output message:
[
    {"from": "human", "value": "<image> How many chairs?"},
    {"from": "gpt",   "value": "3"},
]
```

### 11.3 Multiview messages

`create_multiview_messages()` prepends N `<image>` tags (one per view image):

```python
# 3-view input:
[
    {"from": "human", "value": "<image> <image> <image> Which object is largest?"},
    {"from": "gpt",   "value": "The chair in view 1."},
]
```

### 11.4 Multi-turn conversations

When a prompt is a `list[str]` instead of `str`, the builder creates a multi-turn conversation. Only the first turn gets `<image>` tags:

```python
# Input: ["What color is [A]? Answer: Red", "Is it bright? Answer: Yes"]
# Output:
[
    {"from": "human", "value": "<image> What color is [A]?"},
    {"from": "gpt",   "value": "Red"},
    {"from": "human", "value": "Is it bright?"},
    {"from": "gpt",   "value": "Yes"},
]
```

---

## 12. Model Reuse

When multiple tasks in the same pipeline use the same heavy model (e.g. SAM2), loading it once and sharing across tasks saves memory and startup time.

The pipeline supports this via the `reuse_model` class attribute:

```python
class SAM2Refiner(BaseTask):
    reuse_model = "localization_stage"   # Reuse model from first task in this stage

    def __init__(self, args):
        super().__init__(args)
        if not hasattr(self, 'model'):   # Not yet assigned by pipeline
            self.model = self._load_model()
```

In `BasePipeline.__init__`, after building the task queue, the pipeline checks each task for `reuse_model`. If set, it copies `.model` from the first task in the referenced stage:

```python
# Pipeline logic (automatic):
reuse_stage = getattr(task["task"], "reuse_model", None)
if reuse_stage and reuse_stage in first_task_by_stage:
    task["task"].model = first_task_by_stage[reuse_stage]["task"].model
```

---

## 13. Visualization Server

`visualize_server.py` provides a web UI for inspecting annotation outputs.

### 13.1 Launch

```bash
python visualize_server.py --data_dir output/ --port 8888
```

### 13.2 How it works

1. Scans `--data_dir` recursively for all `data.parquet` files
2. Serves a single-page web UI with a task dropdown
3. Each task loads parquet rows paginated (10 per page)
4. Displays for each row:
   - QA images (with visual markers) — click to open lightbox
   - Question / Answer pairs (supports multi-turn)
   - Task tags and question type badges

### 13.3 Keyboard shortcuts

| Key | Action |
|---|---|
| Left Arrow | Previous page |
| Right Arrow | Next page |
| Escape | Close lightbox |

### 13.4 Using for debugging

During development, point `--data_dir` at your pipeline output directory. The server auto-discovers all task outputs and labels them as `[Single]` or `[Multi]` based on task name. This is the fastest way to verify:
- Visual markers are placed correctly
- Prompts and answers make sense
- Image quality after processing

---

## 14. Common Patterns and Tips

### Config parameter access

Task parameters come from the YAML config dict passed to `__init__`:

```python
def __init__(self, args):
    super().__init__(args)
    self.my_param = args.get("my_param", default_value)
```

### Multi-threading

Enable via YAML:

```yaml
use_multi_processing: true   # Uses ThreadPoolExecutor (not multiprocessing)
num_workers: 8
```

`BaseAnnotationTask` uses thread-local `VisualMarker` instances to ensure thread safety.

### Visual markers

`VisualMarker` draws colored overlays (mask, box, point) on images to identify objects in QA prompts. Configure via `get_mark_config()`:

```python
from .core.visual_marker import MarkConfig

def get_mark_config(self):
    return MarkConfig(
        mark_types=["mask", "box", "point"],  # Available types
        mark_weights=[0.4, 0.4, 0.2],         # Sampling weights
    )
```

### Sub-task count control

Users control how many QA pairs each sub-task generates via YAML:

```yaml
sub_tasks:
  count_oe: 3    # Generate 3 open-ended counting QAs
  count_mcq: 0   # Skip MCQ counting
```

In code, `self.get_sub_task_count("count_oe", default=1)` returns 3 (from config) or 1 (default).

### Pipeline dependency resolution

Tasks can depend on outputs of previous stages via `depends_on`:

```yaml
stages:
  annotation_stage:
    -
      file_name: my_task
      method: AnnotationGenerator
      depends_on: scene_fusion_stage/depth_back_projection
      output_dir:
```

The pipeline resolves `depends_on` to a parquet file path and loads it as input.
