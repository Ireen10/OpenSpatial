# 训练数据格式说明

本文描述 **导出给训练使用的 JSONL 形态**：与 **上游 grounding 数据** 使用同一套字段约定（可参考 `metadata/tests/fixtures/*.jsonl` 与 `metadata/src/openspatial_metadata/adapters/grounding_qa.py`）。

## 与 OpenSpatial 管线字段的关系

- **不使用** OpenSpatial 的 **`messages`**（`human` / `gpt` 列表）。管线内以 **`question` / `answer` / `meta`** 传递；合并进 **`MetadataV0.qa_items`** 后，由导出步骤转为本文的 `data` 结构。
- **标注阶段不产出图像数据**：不写 `QA_images` / bytes。需要画框的图像在 **训练数据导出前** 根据 `qa_items[].meta`（角色/颜色）与 `objects[].bbox_xyxy_norm_1000`（几何）从原图 **重绘** 后再打包进 `images/*.tar`。
- **相关 schema**：`MetadataV0.qa_items`（`AnnotationQaItemV0`）。无生成 QA 时 `qa_items` 为空列表。

## 目录布局

导出训练包时，**端到端验收**应至少包含以下目录与文件。CLI 在写完 `metadata_qa/data_*.jsonl` 后按 `training_rows_per_part` / `training_row_align` 将训练行打包为多个 **bundle**（`id=0` 即 `data_000000.*`）。

- `root/`
  - `images/`
    - `data_{id:06d}.tar` — 图像按 **tar 内相对路径** 存放（JSONL 里 `image.relative_path` 与此一致）
    - `data_{id:06d}_tarinfo.json` — 与上述 tar **同 id、同一次写出**，便于按 offset 随机读图（见下）
  - `jsonl/`
    - `data_{id:06d}.jsonl` — 与 `images` 使用 **相同 id**，便于分片对齐

### `*_tarinfo.json` 结构

顶层为 **对象**：键为 **该 tar 包内的相对路径**（与 JSONL 中 `relative_path` 一致），值为该成员在 tar 中的数据区信息：

```json
{
  "subdir/name.jpg": {
    "offset_data": 5120,
    "size": 12345,
    "sparse": null
  }
}
```

- `offset_data`：成员 **文件数据** 在 tar 文件中的字节偏移（实现需与所用打包方式一致）。
- `size`：该成员 **未压缩** 的数据字节长度（或与你们上游约定一致）。
- `sparse`：无稀疏文件时固定为 `null`（与上游一致即可）。

### `image.relative_path`（tar 内路径）命名

- **基准**：始终来自 **`MetadataV0.sample.image.path`**（导出时规范为 **POSIX** 相对路径，与 tar 内成员名一致）。
- **原图组**（无新框、`n_marked_boxes == 0` / `visual_group_key == "original"`）：**直接使用**上述路径作为 tar 成员名与 JSONL 中的 `relative_path`。
- **带框重绘组**：在同一目录下，使用 **`{stem}_m{8hex}.jpg`**，其中 `8hex` 为 **SHA-256(`visual_group_key`) 的前 8 个十六进制字符**（短且稳定）；扩展名固定为 **`.jpg`**（与导出 JPEG 字节一致）。

## 单条 JSONL 行的顶层字段

| 字段 | 约定 |
|------|------|
| `meta_prompt` | **固定为** `[""]`（仅保留一个空字符串）。 |
| `data` | 见下节：用户与助手 **严格交替**；除首轮 user 外，不重复插入图像部件。 |
| `id` | 训练样本 id；**内部命名规则待定**，导出实现可暂用空字符串 `""` 占位，规则确定后再写入。 |

## `data`：轮次与部件

- **角色顺序**：`user` → `assistant` → `user` → `assistant` → …
- **图像**：**仅出现在第一轮 `user` 的 `content` 最前面**（一个 image 部件），对应该组所使用的视觉输入（原图或某张带框渲染图在 tar 内的相对路径，见下文分组）。
- **文本**：
  - 每个 **`user`**：`content` 中除上述 image 外，仅为 **一个** `type: text` 部件，其字符串为对应 QA 的 **`question`**。
  - 每个 **`assistant`**：`content` 中仅为 **一个** `type: text` 部件，其字符串为对应 QA 的 **`answer`**。
- 不再混入其它部件类型或额外 system 消息。

### `content` 部件：文本

```json
{
  "type": "text",
  "text": {
    "type": "string",
    "format": "utf-8",
    "string": "question 或 answer 的纯文本"
  }
}
```

### `content` 部件：图像（仅首轮 user）

```json
{
  "type": "image",
  "image": {
    "type": "relative_path",
    "format": "image/jpeg",
    "relative_path": "在对应 part tar 包内的相对路径",
    "width": 640,
    "height": 426
  }
}
```

### 单轮示例（一组内仅一条 QA）

```json
{
  "meta_prompt": [""],
  "data": [
    {
      "role": "user",
      "content": [
        { "type": "image", "image": { "type": "relative_path", "format": "image/jpeg", "relative_path": "…", "width": 640, "height": 426 } },
        { "type": "text", "text": { "type": "string", "format": "utf-8", "string": "<question>" } }
      ]
    },
    {
      "role": "assistant",
      "content": [
        { "type": "text", "text": { "type": "string", "format": "utf-8", "string": "<answer>" } }
      ]
    }
  ],
  "id": ""
}
```

### 多轮示例（同一组内多条 QA）

同一 `data` 数组内按顺序追加多对 `(user, assistant)`；**仅第一条 user 含 image**，后续 user 只有 text（question）。

---

## 从 metadata 到「一条训练行」：分组规则

一个 **metadata sample** 下可有 **多条** `qa_items`。转成训练数据时 **不是** 一条 metadata 固定对应一行 JSONL，而是先 **分组**，**每组对应一行 JSONL**（一条训练样本）。

分组依据（在导出前，利用 metadata / `qa_items` 中保存的 **绘制框与渲染信息**，例如 `meta` 里与框、颜色、是否使用原图等相关字段）：

1. **原图组**：凡 **不需要**在图上画新框、直接使用 **原图** 作为视觉输入的 QA，归为一组（若有多条，则在该组内形成 **多轮** `user`/`assistant`）。
2. **带框渲染图组**：需要 **新产出的带框图** 的 QA，按 **完全相同的框绘制结果**（同一渲染图、同一路径或可比较的框签名）再细分：**使用同一张渲染图的 QA 归为一组**，避免同一张框图在 tar 中重复存储多份。
3. **每组 → 一行 JSONL**：该组共用 **首轮 user 前** 的那一张图（原图或该组的渲染图）；组内 **多条 QA** → **`data` 内多轮**交替；**单条 QA** → **单轮**。

`id` 在命名规则明确前可置空；若需追溯，可在实现中临时写入 `aux` 或日志，待规则落地后再写入 `id`。

## 转换流程

- **端到端**：metadata → 标注与合并（含 `qa_items` 与绘制元数据）→ **按上节分组** → 写出 grounding 式 JSONL（及 tar 内图像路径）。
- **仅重刷训练数据**：读取已含 `qa_items` 的 metadata → 仅跑分组与导出。
