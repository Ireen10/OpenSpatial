## 执行计划：2D relation containment 过滤

### 修改范围

- 常量：`metadata/src/openspatial_metadata/enrich/constants.py`
- 逻辑：`metadata/src/openspatial_metadata/enrich/relation2d.py`
- 测试：`metadata/tests/test_enrich_relation2d.py`

### 实施步骤

1. **新增常量**
   - 在 `constants.py` 增加 `CONTAINMENT_IOA = 0.7`

2. **实现过滤逻辑**
   - 在 bbox-bbox pair 的预过滤阶段计算：
     - 交集面积 `inter_area`
     - `ioa_small = inter_area / min(area_a, area_b)`（min=0 则 0）
   - 若 `ioa_small >= CONTAINMENT_IOA`：
     - 记录 dropped candidate：
       - `reason="containment"`
       - 可附 `ioa_small`
     - 返回/continue（不进入后续谓词判定）
   - **只对 bbox-bbox 生效**：point-point 不引入该规则

3. **单测**
   - 在 `test_enrich_relation2d.py` 增加用例：
     - big box vs small box（小框被覆盖 >70%）
     - 同时保证 IoU 很小且 near_center 不触发
     - 断言：`len(relations)==0` 且 dropped reasons 包含 `"containment"`

4. **自测**
   - `python -m pytest metadata/tests -q`

5. **变更记录**
   - `change_log.md`：记录新增过滤规则与测试结果

### 完成标准

- containment 过滤按阈值 0.7 生效
- 新增单测覆盖反例并通过
- 全套 `metadata/tests` 通过

