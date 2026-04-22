from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..config.loader import load_global_config
from .config_index import build_dataset_index
from .server import create_server, serve_forever


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="openspatial-metadata-viz")
    p.add_argument(
        "--output-root",
        default=None,
        help="Root directory containing {dataset}/{split}/data_*.jsonl (or legacy *.metadata.jsonl) (default: global metadata_output_root).",
    )
    p.add_argument(
        "--config-root",
        default=None,
        required=True,
        help="Directory of dataset configs (…/datasets with */dataset.yaml) or a single dataset.yaml.",
    )
    p.add_argument(
        "--global-config",
        default=None,
        help="Optional global.yaml for default metadata_output_root and scale.",
    )
    p.add_argument(
        "--qa-config",
        default=None,
        help="Optional qa_tasks.yaml (overrides global.yaml.qa_config). Used for display only.",
    )
    p.add_argument("--host", default="127.0.0.1", help="Bind address.")
    p.add_argument("--port", type=int, default=8765, help="Bind port.")
    p.add_argument("--verbose", action="store_true", help="Enable per-request server logs in console.")
    args = p.parse_args(argv)

    g = load_global_config(args.global_config)
    out = args.output_root or g.metadata_output_root
    output_root = Path(out).resolve()
    if not output_root.is_dir():
        print(f"[openspatial-metadata-viz] warning: output_root is not a directory: {output_root}", file=sys.stderr)

    config_root = Path(args.config_root)
    idx = build_dataset_index(config_root)

    qa_cfg = args.qa_config or getattr(g, "qa_config", None)
    tor = getattr(g, "training_output_root", None)
    training_root = Path(tor).resolve() if isinstance(tor, str) and tor else None
    httpd = create_server(
        args.host,
        args.port,
        output_root=output_root,
        dataset_index=idx,
        default_scale=int(g.scale),
        qa_config_path=str(qa_cfg) if qa_cfg else None,
        training_output_root=training_root,
        verbose=bool(args.verbose),
    )
    print(
        f"[openspatial-metadata-viz] serving http://{args.host}:{args.port}/  "
        f"output_root={output_root} datasets={len(idx)}",
        file=sys.stderr,
    )
    try:
        serve_forever(httpd)
    except KeyboardInterrupt:
        print("\n[openspatial-metadata-viz] stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
