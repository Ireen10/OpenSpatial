from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union


PathLike = Union[str, Path]


@dataclass(frozen=True)
class RecordRef:
    input_file: str
    input_index: int


def iter_jsonl(path: PathLike) -> Iterator[Tuple[Dict, RecordRef]]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            yield json.loads(line), RecordRef(input_file=str(path), input_index=idx)


def iter_json_file(path: PathLike) -> Iterator[Tuple[Dict, RecordRef]]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        yield json.load(f), RecordRef(input_file=str(path), input_index=0)


class JsonlWriter:
    def __init__(self, path: PathLike, *, append: bool = False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        self._f = self.path.open(mode, encoding="utf-8")

    def write_records(self, records: Sequence[Dict]) -> None:
        for r in records:
            self._f.write(json.dumps(r, ensure_ascii=False))
            self._f.write("\n")

    def flush(self) -> None:
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

