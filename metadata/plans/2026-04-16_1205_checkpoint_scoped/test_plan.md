## Test plan

### Unit tests

- **UT-CKPT-1 (new location)**:
  - Run CLI once with a tiny dataset config into a temp `out_root`
  - Assert at least one file exists under `out_root/{dataset}/{split}/.checkpoints/`

- **UT-CKPT-2 (backward compatible read)**:
  - Prepare an old-style checkpoint under `out_root/.checkpoints/<md5>.json` that marks input done
  - Ensure the new-style checkpoint does not exist
  - Run CLI with resume enabled
  - Assert it does not re-process inputs (e.g. output file remains unchanged / no new writes)

### Regression

- Run full `pytest metadata/tests -q`

