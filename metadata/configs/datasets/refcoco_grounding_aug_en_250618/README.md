## refcoco_grounding_aug_en_250618

本目录用于记录该数据集的**原始文件结构**与**数据格式/解析规则**（不包含任何落地实现方案）。

### 1. 目录结构

数据集目录（示意）：

- `refcoco_grounding_aug_en_250618/`
  - `images/`
    - `part_{id}.tar`
    - `part_{id}_tarinfo.json`
    - ...
  - `jsonl/`
    - `part_{id}.jsonl`
    - ...

其中 `id` 为 6 位数字（`{:06d}`），例如 `000001`。

### 2. images：tar 与 tarinfo

#### 2.1 `part_{id}.tar`

一个 tar 包内包含若干张图像文件，图像在 tar 内用**相对路径**定位（下文 `relative_path`）。

#### 2.2 `part_{id}_tarinfo.json`

该文件是对 `part_{id}.tar` 内各图像条目的索引（偏移与大小），结构如下：

```json
{
  "{image_relative_path}": {
    "offset_data": 123456,
    "size": 98765,
    "sparse": null
  }
}
```

含义：给定 tar 内 `image_relative_path`，可用 `offset_data/size` 定位其二进制内容（如果 adapter 选择“直接读 tar”而不是先解包）。

### 3. jsonl：对话结构

`jsonl/part_{id}.jsonl` 每行是一个样本，结构（仅列关键信息）：

```json
{
  "id": "<sample_id>",
  "data": [
    {"role": "user", "content": [ ... ]},
    {"role": "assistant", "content": [ ... ]}
  ],
  "meta_prompt": [""],
  "repeat_flag": 1
}
```

- `meta_prompt` / `repeat_flag`：非核心字段，可忽略（`repeat_flag` 可能缺失）
- `data`：一轮或多轮对话（user/assistant 交替）

#### 3.1 content：多模态条目

`content` 是一个 list，元素可能是 text 或 image：

- text：

```json
{
  "type": "text",
  "text": {"type": "string", "format": "utf-8", "string": "{query}"}
}
```

- image：

```json
{
  "type": "image",
  "image": {
    "type": "relative_path",
    "format": "image/jpeg",
    "relative_path": "image_path/huawei_logo.jpg",
    "width": 640,
    "height": 480
  }
}
```

实践中：模型回复（assistant 的 content）结构与 user 一致，但通常只需要关注其**文本模态**内容（一般只有一条）。

### 4. grounding 信息：从 assistant 文本解析 bbox

grounding 结果位于 assistant 的 text 中，采用特殊标记格式：

```text
<|object_ref_start|>{ref_exp}<|object_ref_end|>
<|box_start|>({x1:03d}, {y1:03d}),({x2:03d},{y2:03d})<|box_end|>
```

#### 4.1 多 bbox 情况

一个 `object_ref` 后可以紧跟**多个 bbox**，例如：

```text
<|object_ref_start|>mushroom<|object_ref_end|>
<|box_start|>(000, 000),(111,111)<|box_end|>
<|box_start|>(222, 222),(333,333)<|box_end|>
```

#### 4.2 bbox 坐标约定

- 形式：`xyxy`
- 范围：归一化到 0~1000（通常落在 `[0, 999]`）

#### 4.3 解析跳过规则（重要）

以下情况**不解析**（跳过该段）：

- 只有 ref，没有 box
- 只有 box，没有 ref

### 5. 真实数据示例
{
  "meta_prompt": [
    ""
  ],
  "data": [
    {
      "role": "user",
      "content": [
        {
          "type": "image",
          "image": {
            "type": "relative_path",
            "format": "image/jpeg",
            "relative_path": "type7/train2014/COCO_train2014_000000569667.jpg",
            "width": 640,
            "height": 426
          }
        },
        {
          "type": "text",
          "text": {
            "type": "string",
            "format": "utf-8",
            "string": "Please provide the bounding box coordinate of the region this sentence describes: yeah impossible here the one with yellow cheese on end"
          }
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": {
            "type": "string",
            "format": "utf-8",
            "string": "<|object_ref_start|>yeah impossible here the one with yellow cheese on end<|object_ref_end|><|box_start|>(601,346),(953,828)<|box_end|>"
          }
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": {
            "type": "string",
            "format": "utf-8",
            "string": "Please provide the bounding box coordinate of the region this sentence describes: darkest hot dog"
          }
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": {
            "type": "string",
            "format": "utf-8",
            "string": "<|object_ref_start|>darkest hot dog<|object_ref_end|><|box_start|>(023,191),(353,636)<|box_end|>"
          }
        }
      ]
    }
  ],
  "repeat_flag": 1,
  "id": "type7-0806-6_myNGTNg5_2690"
}

