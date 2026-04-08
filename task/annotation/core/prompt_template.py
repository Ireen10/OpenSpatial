import random
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PromptTemplate:
    """A group of question/answer templates."""
    questions: List[str]
    answers: List[str] = field(default_factory=list)
    true_answers: Optional[List[str]] = None
    false_answers: Optional[List[str]] = None

    def sample(self, condition: bool = None) -> Tuple[str, str]:
        """Randomly sample a (question_template, answer_template) pair.

        When ``condition`` is not None, the template **must** have both
        ``true_answers`` and ``false_answers`` populated (non-empty).
        If either list is empty or None the call raises ``ValueError``
        rather than silently falling back to ``self.answers``.
        """
        q = random.choice(self.questions)
        if condition is not None:
            if self.true_answers and self.false_answers:
                a = random.choice(self.true_answers if condition else self.false_answers)
            else:
                raise ValueError(
                    "sample(condition=...) requires both true_answers and "
                    "false_answers to be non-empty. Got "
                    f"true_answers={self.true_answers!r}, "
                    f"false_answers={self.false_answers!r}"
                )
        elif self.answers:
            a = random.choice(self.answers)
        else:
            a = ""
        return q, a

    @staticmethod
    def _fill(text: str, mapping: dict) -> str:
        for key, val in mapping.items():
            text = text.replace(f"[{key}]", str(val))
        return text

    def render(self, condition: bool = None, *,
               shared: dict = None, q_args: dict = None, a_args: dict = None) -> str:
        """Sample + fill placeholders + join as 'question Answer: answer'.

        Args:
            shared:  Placeholders applied to both Q and A (same value both sides).
                     Typical keys: A/B/C (object names), T (type label), D (disclaimer).
            q_args:  Question-only placeholders (applied after shared).
            a_args:  Answer-only placeholders (applied after shared).
                     Use q_args/a_args when a key (e.g. X) has different meaning
                     in question vs answer.
        """
        q, a = self.sample(condition)
        if shared:
            q = self._fill(q, shared)
            a = self._fill(a, shared)
        if q_args:
            q = self._fill(q, q_args)
        if a_args:
            a = self._fill(a, a_args)
        return q + " Answer: " + a

    def render_qa(self, condition: bool = None, *,
                  shared: dict = None, q_args: dict = None, a_args: dict = None) -> Tuple[str, str]:
        """Sample + fill placeholders, return (question, answer) separately."""
        q, a = self.sample(condition)
        if shared:
            q = self._fill(q, shared)
            a = self._fill(a, shared)
        if q_args:
            q = self._fill(q, q_args)
        if a_args:
            a = self._fill(a, a_args)
        return q, a


class TemplateRegistry:
    """Global template registry keyed by 'task.variant' names.

    Thread-safe: a lock protects ``register()`` so concurrent imports
    from different threads cannot corrupt ``_store``.  Read-only methods
    (``get`` / ``keys``) do not need the lock because Python's GIL
    guarantees dict reads are atomic once the write is complete.
    """
    _store: Dict[str, PromptTemplate] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, name: str, tpl: PromptTemplate):
        with cls._lock:
            cls._store[name] = tpl

    @classmethod
    def get(cls, name: str) -> PromptTemplate:
        if name not in cls._store:
            raise KeyError(f"Template '{name}' not registered. Available: {list(cls._store.keys())}")
        return cls._store[name]

    @classmethod
    def keys(cls) -> list:
        return list(cls._store.keys())
