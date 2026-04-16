#!/usr/bin/env python3
"""
Batch-extract ``part_*.tar`` archives so **member paths** land directly under a single
output root — **no** intermediate ``part_XXXXXX/`` directory.

Intended for **Linux** (e.g. remote training / data servers). Paths below use POSIX
style.

This matches metadata ``sample.image.path`` (tar-internal relative paths such as
``type7/train2014/COCO_....jpg``) with visualization mode **A**::

    image_root / sample.image.path  ->  regular file read

Example (bash, from the OpenSpatial repo root)::

    python metadata/scripts/extract_part_tars_to_root.py \\
        --source-dir /data/datasets/refcoco_grounding_aug_en_250618/images \\
        --output-root /data/images/refcoco_flat

One line::

    python metadata/scripts/extract_part_tars_to_root.py --source-dir /data/.../images --output-root /data/.../image_root

Each archive is extracted as ``extractall(output_root)``: paths inside the tar are
preserved relative to ``output_root`` (standard tar behavior).
"""
from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path


def _find_tars(source_dir: Path, pattern: str) -> list[Path]:
    tars = sorted(source_dir.glob(pattern))
    return [p for p in tars if p.is_file()]


def _scan_member_paths(tar_path: Path) -> list[str]:
    with tarfile.open(tar_path, "r:*") as tf:
        return [m.name for m in tf.getmembers() if m.isfile() or m.isdir()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Extract part_*.tar files into one tree under --output-root (no part_XXXX wrapper dirs).",
        epilog="Linux example: python metadata/scripts/extract_part_tars_to_root.py "
        "--source-dir /data/.../images --output-root /data/.../image_root",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing part_*.tar (e.g. .../refcoco_.../images).",
    )
    p.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Root folder where tar member paths are merged (your image_root for the viewer).",
    )
    p.add_argument(
        "--pattern",
        default="part_*.tar",
        help="Glob for tar files under source-dir (default: part_*.tar).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List archives and member counts only; do not extract.",
    )
    p.add_argument(
        "--check-overlap",
        action="store_true",
        help="Before extracting, scan all tars and warn if the same member path appears in more than one archive.",
    )
    args = p.parse_args(argv)

    source_dir = args.source_dir.resolve()
    output_root = args.output_root.resolve()

    if not source_dir.is_dir():
        print(f"error: --source-dir is not a directory: {source_dir}", file=sys.stderr)
        return 1

    tars = _find_tars(source_dir, args.pattern)
    if not tars:
        print(f"error: no files matching {args.pattern!r} under {source_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(tars)} tar(s) under {source_dir}")

    path_to_tars: dict[str, list[str]] = {}
    if args.check_overlap or args.dry_run:
        for tp in tars:
            try:
                names = _scan_member_paths(tp)
            except (OSError, tarfile.TarError) as e:
                print(f"error: cannot read {tp}: {e}", file=sys.stderr)
                return 1
            for name in names:
                # normalize: strip leading ./ for dedup
                key = name[2:] if name.startswith("./") else name
                path_to_tars.setdefault(key, []).append(tp.name)

    if args.check_overlap:
        dups = {k: v for k, v in path_to_tars.items() if len(v) > 1}
        if dups:
            print("warning: overlapping member paths across archives (later extract may overwrite):")
            for k in sorted(dups.keys())[:50]:
                print(f"  {k!r} -> {dups[k]}")
            if len(dups) > 50:
                print(f"  ... and {len(dups) - 50} more")
        else:
            print("No overlapping member paths detected across archives.")

    if args.dry_run:
        for tp in tars:
            n = len(_scan_member_paths(tp))
            print(f"  would extract {n} entries from {tp.name}")
        return 0

    output_root.mkdir(parents=True, exist_ok=True)

    for tp in tars:
        print(f"Extracting {tp.name} -> {output_root} ...")
        try:
            with tarfile.open(tp, "r:*") as tf:
                # Python 3.12+: filter='data' mitigates path issues; older: plain extractall.
                try:
                    tf.extractall(output_root, filter="data")  # type: ignore[call-arg]
                except TypeError:
                    tf.extractall(output_root)
        except (OSError, tarfile.TarError) as e:
            print(f"error: failed {tp}: {e}", file=sys.stderr)
            return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
