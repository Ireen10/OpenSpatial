from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def test_global_llm_defaults_are_injected_and_params_override(tmp_path: Path) -> None:
    """
    Validate constructor injection precedence:
    - global.llm provides defaults
    - adapter.params overrides same keys
    Uses a test-only adapter that records received kwargs into aux.
    """
    tests_dir = Path(__file__).resolve().parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))

    in_jsonl = tmp_path / "in.jsonl"
    in_jsonl.write_text(json.dumps({"x": 1}, ensure_ascii=False) + "\n", encoding="utf-8")

    out_root = tmp_path / "out"

    gcfg = tmp_path / "global.yaml"
    gcfg.write_text(
        yaml.safe_dump(
            {
                "metadata_output_root": str(out_root),
                "llm": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "model": "default-model",
                    "timeout_s": 12,
                    "max_tokens": 111,
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    ds_dir = tmp_path / "datasets" / "d"
    ds_dir.mkdir(parents=True, exist_ok=True)
    in_jsonl_posix = in_jsonl.as_posix()
    (ds_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                'name: "d"',
                "adapters:",
                "  - module: llm_param_probe",
                "    class_name: LlmParamProbeAdapter",
                "    params:",
                "      model: override-model",
                "      max_tokens: 222",
                "splits:",
                "  - name: train",
                "    input_type: jsonl",
                f"    inputs: ['{in_jsonl_posix}']",
                "",
            ]
        ),
        encoding="utf-8",
    )

    from openspatial_metadata.cli import main

    main(["--config-root", str(ds_dir.parent), "--global-config", str(gcfg), "--progress", "none"])

    md_path = out_root / "d" / "train" / "data_000000.jsonl"
    lines = [x for x in md_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    probe = (rec.get("aux") or {}).get("llm_param_probe") or {}

    # global defaults
    assert probe["base_url"] == "http://127.0.0.1:8000/v1"
    assert probe["timeout_s"] == 12
    # adapter.params overrides
    assert probe["model"] == "override-model"
    assert probe["max_tokens"] == 222

