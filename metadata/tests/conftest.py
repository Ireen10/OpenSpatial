from __future__ import annotations

import sys
from pathlib import Path
import os


# Ensure `src/` is importable when running tests without editable install.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

# Most tests use paths like "metadata/..." and assume cwd is repo root.
_REPO_ROOT = _ROOT.parent
try:
    os.chdir(_REPO_ROOT)
except Exception:
    pass


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    config.addinivalue_line("markers", "e2e: end-to-end tests (can be slower)")

