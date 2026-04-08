from enum import Enum


class QuestionType(str, Enum):
    """Question type enum. Inherits str so serialization to parquet is transparent."""
    OPEN_ENDED = "open_ended"
    MCQ = "MCQ"
