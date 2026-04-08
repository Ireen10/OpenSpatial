"""
Base class for singleview annotation tasks.

Extracts the shared run/apply_transform/create_messages patterns
from all 8 singleview annotation files.
"""

import threading

from .scene_graph import SceneGraph
from .visual_marker import VisualMarker, MarkConfig
from .message_builder import create_singleview_messages
from .prompt_template import PromptTemplate, TemplateRegistry

from task.base_task import BaseTask
from utils.point_cloud_utils import clean_point_cloud
from utils.image_utils import convert_pil_to_bytes

# Trigger template registration on first import of any annotation task
import task.prompt_templates  # noqa: F401


class BaseAnnotationTask(BaseTask):
    """
    Base class for all singleview annotation tasks.

    Subclasses must implement:
        - process(self, example) -> (prompts, processed_images, question_tags, question_types)

    Optionally override:
        - get_mark_config() -> MarkConfig
        - check_example(example) -> bool
        - create_messages_from_prompts(prompts, processed_images) -> list
    """

    QUESTION_TAG = "Unknown"
    SUB_TASKS = {}  # Subclass override: {"name": {"default": N, "handler": "_method_name"}}

    def __init__(self, args):
        super().__init__(args)
        self._thread_local = threading.local()
        self.scaling_factor = args.get("scaling_factor", 1)
        self.filter_tags = args.get("filter_tags", None)
        self._sub_tasks_config = self._parse_sub_tasks(args.get("sub_tasks", None))

    def _parse_sub_tasks(self, raw):
        """Parse sub_tasks config from YAML.

        Supports:
            None             → use all defaults
            "all"            → use all defaults
            ["a", "b"]       → enable only these sub_tasks, use default counts
            {"a": 3, "b": 5} → enable these sub_tasks with specified counts

        Returns:
            None (use defaults) or dict {sub_task_name: count_or_None}
        """
        if raw is None or raw == "all":
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            return {k: None for k in raw}
        # Handle SimpleNamespace from YAML dict_to_namespace conversion
        if hasattr(raw, '__dict__'):
            return vars(raw)
        raise ValueError(f"Invalid sub_tasks config: {raw}")

    def get_sub_task_count(self, sub_task, default=1):
        """Get how many prompts to generate for a given sub_task.

        Returns:
            int: number of prompts. 0 means skip this sub_task.
        """
        if self._sub_tasks_config is None:
            return default
        if sub_task not in self._sub_tasks_config:
            return 0
        count = self._sub_tasks_config[sub_task]
        return default if count is None else int(count)

    @property
    def marker(self):
        """Thread-local VisualMarker. Each thread gets its own instance."""
        tl = self._thread_local
        if not hasattr(tl, 'marker'):
            tl.marker = VisualMarker(self.get_mark_config())
        return tl.marker

    @marker.setter
    def marker(self, value):
        self._thread_local.marker = value

    def get_mark_config(self) -> MarkConfig:
        """Override to provide task-specific mark configuration."""
        return MarkConfig()

    @staticmethod
    def _get_cloud(marked):
        """Extract (desc, pointcloud) from a marked result (desc, node)."""
        desc, node = marked
        cloud = node.view_appearances[0].pointcloud_camera
        return desc, cloud

    @staticmethod
    def _clean_cloud(cloud):
        """Remove statistical outliers from a pointcloud."""
        return clean_point_cloud(cloud)

    @staticmethod
    def _shuffle_mcq(candidates, correct_idx=0):
        """Shuffle candidates into A/B/C/D, return (shuffled, answer_letter)."""
        import random
        order = list(range(len(candidates)))
        random.shuffle(order)
        answer = "ABCD"[order.index(correct_idx)]
        return [candidates[j] for j in order], answer

    def mark_and_prompt(self, nodes, image, prompt_func, *,
                        each=False, mark_prob=1.0, prompt_args=None):
        """Mark nodes on image and generate prompts.

        Args:
            each: If True, call prompt_func(marked) per node → return list.
                  If False, call prompt_func(*all_marked, **prompt_args) → return single.
            mark_prob: Probability of applying visual marks (default 1.0 = always).
                       When skipped, uses (node.tag, node) as unmarked fallback.
            prompt_args: Extra kwargs forwarded to prompt_func.

        Returns:
            (prompt_or_prompts, processed_image)
        """
        import random

        if prompt_args is None:
            prompt_args = {}

        if random.random() < mark_prob:
            processed_image, marked = self.marker.mark_objects(image, nodes)
        else:
            processed_image = {"bytes": convert_pil_to_bytes(image)}
            marked = [(n.tag, n) for n in nodes]

        if each:
            prompts = [prompt_func(m, **prompt_args) for m in marked]
            return prompts, processed_image
        else:
            prompt = prompt_func(*marked, **prompt_args)
            return prompt, processed_image

    def check_example(self, example) -> bool:
        """Pre-check common required fields. Subclasses should call super() first."""
        if "image" not in example:
            return False
        if "obj_tags" not in example or len(example["obj_tags"]) == 0:
            return False
        return True

    def build_scene_graph(self, example) -> SceneGraph:
        """Build a SceneGraph from the example dict. Override for custom logic."""
        return SceneGraph.from_singleview_example(example)

    def process(self, graph, example):
        """Generic sub_task dispatch loop.

        Iterates over SUB_TASKS, calls each handler with count from config.
        Handler signature: _generate_xxx(self, graph) -> (prompt, image, qtype) | list | None

        Subclasses with special logic can override this method.
        """
        prompts, images, qtypes = [], [], []
        for name, meta in self.SUB_TASKS.items():
            count = self.get_sub_task_count(name, default=meta["default"])
            if count == 0:
                continue
            handler = getattr(self, meta["handler"])
            for _ in range(count):
                result = handler(graph)
                if result is None:
                    continue
                if isinstance(result, list):
                    for p, img, qt in result:
                        prompts.append(p)
                        images.append(img)
                        qtypes.append(qt)
                else:
                    p, img, qt = result
                    prompts.append(p)
                    images.append(img)
                    qtypes.append(qt)
        tags = [[self.QUESTION_TAG]] * len(prompts)
        return prompts, images, tags, qtypes

    def get_template(self, name: str) -> PromptTemplate:
        """Get a template from the registry. Subclass can override for customization."""
        return TemplateRegistry.get(name)

    def render_prompt(self, template_name: str, condition: bool = None, *,
                      shared: dict = None, q_args: dict = None, a_args: dict = None) -> str:
        """One-step: get template → sample → fill → return 'question Answer: answer'."""
        tpl = self.get_template(template_name)
        return tpl.render(condition=condition, shared=shared, q_args=q_args, a_args=a_args)

    def create_messages_from_prompts(self, prompts, processed_images=None):
        """
        Default singleview message creation.
        Splits on "Answer: ", prepends "<image>" tag.
        """
        return create_singleview_messages(prompts)

    def apply_transform(self, example, idx=None):
        """Standard transform pipeline: check → build graph → process → create_messages → set fields.

        Thread-safe: each thread gets its own VisualMarker via the thread-local
        `self.marker` property, avoiding shared mutable color_queue state.
        """
        if not self.check_example(example):
            return None, False

        # Reset thread-local marker for this example
        self.marker = VisualMarker(self.get_mark_config())

        graph = self.build_scene_graph(example)
        prompts, processed_images, question_tags, question_types = self.process(graph, example)
        if len(prompts) == 0:
            return None, False

        messages = self.create_messages_from_prompts(prompts, processed_images)

        example["messages"] = messages
        example["QA_images"] = processed_images
        example["question_tags"] = question_tags
        example["question_types"] = question_types
        return example, True
