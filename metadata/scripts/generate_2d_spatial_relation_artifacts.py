#!/usr/bin/env python3
"""
Generate on-disk metadata + QA preview artifacts from grounding fixtures.

Writes under: metadata/tests/fixtures/generated/spatial_relation_2d/

Usage (from repo root):

  set PYTHONPATH=metadata\\src
  python metadata/scripts/generate_2d_spatial_relation_artifacts.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "metadata" / "src"))
    sys.path.insert(0, str(repo_root / "metadata" / "tests"))

    import spatial_relation_2d_artifacts as art  # noqa: PLC0415

    art.write_dense_and_complex_artifacts()
    print(f"Wrote artifacts under: {art.GENERATED_DIR}")


if __name__ == "__main__":
    main()
