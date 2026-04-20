from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from .config_index import DatasetIndexEntry, resolved_image_root, resolved_training_root
from .paths import (
    count_lines_jsonl,
    enumerate_metadata_jsonl,
    enumerate_training_parts,
    find_sample_line,
    is_under_root,
    read_line_jsonl,
    read_lines_jsonl,
    read_tar_member_by_tarinfo,
    safe_file_under_root,
    guess_content_type_from_name,
)


def _send_json(handler: BaseHTTPRequestHandler, obj: Any, status: int = 200) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_bytes(handler: BaseHTTPRequestHandler, data: bytes, content_type: str, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_static_index() -> bytes:
    here = Path(__file__).resolve().parent / "static" / "index.html"
    return here.read_bytes()


class VizRequestHandler(BaseHTTPRequestHandler):
    server_version = "OpenSpatialMetadataViz/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quieter default
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        output_root: Path = self.server.output_root  # type: ignore[attr-defined]
        dataset_index: Dict[str, DatasetIndexEntry] = self.server.dataset_index  # type: ignore[attr-defined]
        default_scale: int = self.server.default_scale  # type: ignore[attr-defined]
        qa_config_path: str | None = getattr(self.server, "qa_config_path", None)  # type: ignore[attr-defined]
        global_training_root: Path | None = getattr(self.server, "training_output_root", None)  # type: ignore[attr-defined]

        try:
            if path in ("/", "/index.html"):
                _send_bytes(self, _read_static_index(), "text/html; charset=utf-8")
                return

            if path == "/api/tree":
                files = enumerate_metadata_jsonl(output_root)
                # enumerate training parts per-dataset using dataset.training_output_root
                parts = []
                for name in sorted(dataset_index.keys()):
                    tr = resolved_training_root(dataset_index, name)
                    if tr is None and global_training_root is not None:
                        tr = global_training_root
                    if tr is None:
                        continue
                    parts.extend(enumerate_training_parts(tr))
                _send_json(
                    self,
                    {
                        "output_root": str(output_root),
                        "files": files,
                        "training_parts": parts,
                    },
                )
                return

            if path == "/api/config":
                cfg = {
                    "output_root": str(output_root),
                    "default_scale": default_scale,
                    "qa_config_path": qa_config_path,
                    "datasets": [
                        {
                            "name": name,
                            "image_root": (ent.dataset.viz.image_root if ent.dataset.viz else None),
                            "image_root_resolved": (
                                str(resolved_image_root(dataset_index, name))
                                if ent.dataset.viz and ent.dataset.viz.image_root
                                else None
                            ),
                            "training_root": (ent.dataset.training_output_root if getattr(ent.dataset, "training_output_root", None) else None),
                            "training_root_resolved": (
                                str(resolved_training_root(dataset_index, name)) if resolved_training_root(dataset_index, name) else None
                            ),
                            "config_path": ent.config_path,
                        }
                        for name, ent in sorted(dataset_index.items())
                    ],
                }
                _send_json(self, cfg)
                return

            if path == "/api/record":
                rel = (qs.get("path") or [None])[0]
                line_s = (qs.get("line") or ["0"])[0]
                if not rel:
                    _send_json(self, {"error": "missing path"}, 400)
                    return
                try:
                    line_idx = int(line_s)
                except ValueError:
                    _send_json(self, {"error": "bad line"}, 400)
                    return
                full = (output_root / rel).resolve()
                if not is_under_root(full, output_root):
                    _send_json(self, {"error": "path outside output_root"}, 403)
                    return
                rec = read_line_jsonl(full, line_idx)
                nlines = count_lines_jsonl(full)
                _send_json(
                    self,
                    {
                        "record": rec,
                        "line": line_idx,
                        "line_count": nlines,
                        "path": rel.replace("\\", "/"),
                    },
                )
                return

            if path == "/api/seek":
                rel = (qs.get("path") or [None])[0]
                sample_id = (qs.get("sample_id") or [None])[0]
                if not rel or not sample_id:
                    _send_json(self, {"error": "missing path or sample_id"}, 400)
                    return
                full = (output_root / rel).resolve()
                if not is_under_root(full, output_root):
                    _send_json(self, {"error": "path outside output_root"}, 403)
                    return
                try:
                    line_idx = find_sample_line(full, sample_id)
                except KeyError:
                    _send_json(self, {"error": "sample_id not found", "sample_id": sample_id}, 404)
                    return
                nlines = count_lines_jsonl(full)
                _send_json(self, {"line": line_idx, "line_count": nlines, "path": rel.replace("\\", "/")})
                return

            if path == "/api/image":
                dataset_name = (qs.get("dataset") or [None])[0]
                rel_img = (qs.get("relpath") or [None])[0]
                if not dataset_name or not rel_img:
                    _send_json(self, {"error": "missing dataset or relpath"}, 400)
                    return
                img_root = resolved_image_root(dataset_index, dataset_name)
                if img_root is None:
                    _send_json(
                        self,
                        {"error": "viz.image_root not set for dataset", "dataset": dataset_name},
                        404,
                    )
                    return
                candidate = (img_root / rel_img).resolve()
                ok = safe_file_under_root(candidate, img_root)
                if ok is None:
                    _send_json(
                        self,
                        {
                            "error": "image not found or outside image_root",
                            "image_root": str(img_root),
                            "relpath": rel_img,
                        },
                        404,
                    )
                    return
                mime, _ = mimetypes.guess_type(str(ok))
                ct = mime or "application/octet-stream"
                _send_bytes(self, ok.read_bytes(), ct)
                return

            if path == "/api/training_lines":
                dataset_name = (qs.get("dataset") or [None])[0]
                split_name = (qs.get("split") or [None])[0]
                part_s = (qs.get("part") or [None])[0]
                offset_s = (qs.get("offset") or ["0"])[0]
                limit_s = (qs.get("limit") or ["50"])[0]
                if not dataset_name or not split_name or not part_s:
                    _send_json(self, {"error": "missing dataset/split/part"}, 400)
                    return
                try:
                    part_id = int(part_s)
                    offset = int(offset_s)
                    limit = int(limit_s)
                except ValueError:
                    _send_json(self, {"error": "bad part/offset/limit"}, 400)
                    return
                limit = max(1, min(limit, 200))
                tr = resolved_training_root(dataset_index, dataset_name) or global_training_root
                if tr is None:
                    _send_json(self, {"error": "training_output_root not set for dataset", "dataset": dataset_name}, 404)
                    return
                jsonl_path = (tr / dataset_name / split_name / "jsonl" / f"data_{part_id:06d}.jsonl").resolve()
                if not is_under_root(jsonl_path, tr):
                    _send_json(self, {"error": "path outside training_root"}, 403)
                    return
                if not jsonl_path.is_file():
                    _send_json(self, {"error": "jsonl not found"}, 404)
                    return
                recs, total = read_lines_jsonl(jsonl_path, offset=offset, limit=limit)
                _send_json(
                    self,
                    {
                        "dataset": dataset_name,
                        "split": split_name,
                        "part": part_id,
                        "offset": offset,
                        "limit": limit,
                        "line_count": total,
                        "records": recs,
                    },
                )
                return

            if path == "/api/training_image":
                dataset_name = (qs.get("dataset") or [None])[0]
                split_name = (qs.get("split") or [None])[0]
                part_s = (qs.get("part") or [None])[0]
                rel_img = (qs.get("relpath") or [None])[0]
                if not dataset_name or not split_name or not part_s or not rel_img:
                    _send_json(self, {"error": "missing dataset/split/part/relpath"}, 400)
                    return
                try:
                    part_id = int(part_s)
                except ValueError:
                    _send_json(self, {"error": "bad part"}, 400)
                    return
                tr = resolved_training_root(dataset_index, dataset_name) or global_training_root
                if tr is None:
                    _send_json(self, {"error": "training_output_root not set for dataset", "dataset": dataset_name}, 404)
                    return
                tar_path = (tr / dataset_name / split_name / "images" / f"data_{part_id:06d}.tar").resolve()
                tarinfo_path = (tr / dataset_name / split_name / "images" / f"data_{part_id:06d}_tarinfo.json").resolve()
                if not is_under_root(tar_path, tr) or not is_under_root(tarinfo_path, tr):
                    _send_json(self, {"error": "path outside training_root"}, 403)
                    return
                if not tar_path.is_file() or not tarinfo_path.is_file():
                    _send_json(self, {"error": "tar/tarinfo not found"}, 404)
                    return
                idx = json.loads(tarinfo_path.read_text(encoding="utf-8"))
                ent = idx.get(rel_img)
                if not isinstance(ent, dict):
                    _send_json(self, {"error": "relpath not in tarinfo", "relpath": rel_img}, 404)
                    return
                od = ent.get("offset_data")
                sz = ent.get("size")
                if not isinstance(od, int) or not isinstance(sz, int):
                    _send_json(self, {"error": "bad tarinfo entry", "relpath": rel_img}, 500)
                    return
                data = read_tar_member_by_tarinfo(tar_path, offset_data=od, size=sz)
                ct = guess_content_type_from_name(rel_img)
                _send_bytes(self, data, ct)
                return

            _send_json(self, {"error": "not found"}, 404)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            _send_json(self, {"error": str(e)}, 500)


def create_server(
    host: str,
    port: int,
    *,
    output_root: Path,
    dataset_index: Dict[str, DatasetIndexEntry],
    default_scale: int,
    qa_config_path: str | None = None,
    training_output_root: Path | None = None,
) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), VizRequestHandler)
    httpd.output_root = output_root.resolve()  # type: ignore[attr-defined]
    httpd.dataset_index = dataset_index  # type: ignore[attr-defined]
    httpd.default_scale = default_scale  # type: ignore[attr-defined]
    httpd.qa_config_path = qa_config_path  # type: ignore[attr-defined]
    httpd.training_output_root = training_output_root.resolve() if training_output_root else None  # type: ignore[attr-defined]
    return httpd


def serve_forever(httpd: ThreadingHTTPServer) -> None:
    httpd.serve_forever()
