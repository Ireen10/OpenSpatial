# Expression refresh + category (Qwen VL, OpenAI-compatible API)

## Goal

Second-stage adapter after `GroundingQAAdapter`: call a local vision LLM (OpenAI-style `POST /v1/chat/completions`) to refresh `objects[].phrase` and `category`, forbidding spatial language; `phrase: null` drops the object and rewrites `queries`.

## Components

- **`OpenAICompatibleChatClient`**: minimal HTTP JSON client; `base_url` includes `/v1`.
- **`ExpressionRefreshQwenAdapter`**: loads image from `image_root` + `sample.image.path`, one API call per object bbox; multi-instance uses ordered `candidate_object_ids` with multi-object prompt.

## Config

- **`AdapterSpec.params`**: forwarded to adapter `__init__` when the parameter name exists on the class.
- **CLI**: passes resolved `dataset_config_path` so default `image_root` matches `viz.image_root` / dataset dir (same as `_resolve_image_root`).

## Non-goals

- No batching / async; no prompt auto-retry beyond error policy `on_llm_error` (`keep` | `drop`).
