## 变更记录（Change Log）：2D relation containment 过滤（2026-04-15）

### 变更摘要

- **新增过滤**：bbox-bbox pair 若 \(|A∩B| / \min(|A|,|B|) ≥ 0.7\)（小框被覆盖 ≥70%）则丢弃该候选关系（`reason="containment"`）。
- **实现细节**：containment 检查在 `high_iou` 与 `near_center` 之后执行，避免覆盖更特定的丢弃原因。
- **常量**：新增 `CONTAINMENT_IOA = 0.7`
- **测试**：新增用例覆盖 “IoU 小但 containment 高” 的场景。

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：30 passed

