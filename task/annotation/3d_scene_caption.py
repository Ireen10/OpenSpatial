"""
3D scene caption annotation task: generate spatial scene descriptions via LLM.

Uses an external LLM API to produce 100-200 word spatial captions.
Prompts are assembled from modular components (role, task, subject, technical,
text, constraint, style) with per-module dropout for diversity.

Required config keys: api_key, base_url, model.
"""

import random
import time
import base64
from PIL import Image
from openai import OpenAI

from .core.base_annotation_task import BaseAnnotationTask
from .core.question_type import QuestionType
from ..prompt_templates.caption_prompt_templates import (
    CAPTION_MODULES, CAPTION_DEFAULT_DROPOUT,
)
from utils.image_utils import convert_pil_to_bytes

REQUIRED_KEYS = ("api_key", "base_url", "model")
QUESTION_KEYS = {"role", "task"}


class CaptionGenerator(BaseAnnotationTask):

    QUESTION_TAG = "3D Scene Caption"

    def __init__(self, args):
        super().__init__(args)
        missing = [k for k in REQUIRED_KEYS if k not in args]
        if missing:
            raise ValueError(f"Missing required config keys: {', '.join(missing)}")
        self.client = OpenAI(api_key=args["api_key"], base_url=args["base_url"])
        self.model = args["model"]
        self.max_retries = args.get("max_retries", 5)
        self.retry_delay = args.get("retry_delay", 5)

    def check_example(self, example) -> bool:
        return "image" in example

    # ── helpers ──────────────────────────────────────────────────────

    def _call_api(self, prompt, image_path):
        """Call LLM API with retry. Returns caption string or None."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    stream=False,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpg;base64,{b64}",
                            }},
                        ],
                    }],
                )
                return resp.choices[0].message.content
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return None

    # ── prompt function ──────────────────────────────────────────────

    @staticmethod
    def sample_prompt(dropout=None):
        """Assemble a (system_prompt, question_prompt) pair with random module dropout."""
        if dropout is None:
            dropout = CAPTION_DEFAULT_DROPOUT
        system_parts, question_parts = [], []

        for name, pool in CAPTION_MODULES.items():
            if random.random() < dropout.get(name, 0.0):
                continue
            choice = random.choice(pool)
            system_parts.append(choice)
            if name in QUESTION_KEYS:
                question_parts.append(choice)

        if not system_parts:
            system_parts = [random.choice(CAPTION_MODULES["role"]),
                            random.choice(CAPTION_MODULES["task"])]
            question_parts = list(system_parts)

        return " ".join(system_parts), " ".join(question_parts)

    # ── apply_transform override ─────────────────────────────────────

    def apply_transform(self, example):
        """Skip scene graph / marker — directly call LLM API for caption."""
        if not self.check_example(example):
            return None, False

        image_path = example["image"]
        system_prompt, question_prompt = self.sample_prompt()
        caption = self._call_api(system_prompt, image_path)
        if caption is None:
            return None, False

        example["messages"] = [[
            {"from": "human", "value": question_prompt},
            {"from": "gpt", "value": caption},
        ]]
        example["QA_images"] = [{"bytes": convert_pil_to_bytes(Image.open(image_path))}]
        example["question_tags"] = [[self.QUESTION_TAG]]
        example["question_types"] = [QuestionType.OPEN_ENDED]
        return example, True
