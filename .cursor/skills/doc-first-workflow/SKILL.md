---
name: doc-first-workflow
description: Enforces a documentation-first engineering workflow (Design → Execution Plan → Test Plan → Implementation) with timestamped artifacts and change logs. Use whenever implementing new features, refactors, data pipelines, or any non-trivial code change, or when the user asks for a plan/process, documentation, or wants changes recorded. Also applies a lightweight fast-track for tiny bugfixes while still requiring written documentation before code edits.
---

# Doc-first workflow (Design → Plan → Test → Implement)

## Core rules (hard constraints)

1. **Sequential alignment required**: Documents must be produced and aligned **one step at a time**:
   - Write `design.md` → align with user → only then write `plan.md`
   - Align `plan.md` → only then write `test_plan.md`
   - Align `test_plan.md` → only then implement code
   - `test_plan.md` must explicitly map test items to the planned functional points in `plan.md`.
2. **No implementation before aligned test plan**: Do not modify code until the user confirms alignment on the required docs for the current change.
2. **Timestamped directory per change**: Every feature/change gets its own directory: `metadata/plans/YYYY-MM-DD_HHMM_<topic>/` (or the project’s chosen plans root).
3. **Artifacts (produced sequentially)**:
   - `design.md` (first)
   - `plan.md` (second, only after design alignment)
   - `test_plan.md` (third, only after plan alignment)
   - `change_log.md` (written at the end of the change, after implementation/testing; not upfront)
4. **Changes always recorded**: For every subsequent change/new feature, create a new timestamped directory; never overwrite prior change docs.
5. **Self-acceptance testing is mandatory**: After implementation, the agent must run the tests specified in `test_plan.md` (or the `bugfix_brief.md` test steps for tiny bugfixes). Do not consider the change “done” until the agreed tests pass; if tests fail, fix and rerun.

## Fast-track for tiny bugfixes (still doc-first)

If the change is a *tiny bugfix*, use a lightweight doc set:

- Create `metadata/plans/YYYY-MM-DD_HHMM_<topic>/`
- Write **only**:
  - `bugfix_brief.md` (template below)
- Align `bugfix_brief.md` with the user → only then implement
- Write `change_log.md` **after** the fix + verification are done

Treat it as *tiny bugfix* only when all are true:
- Affects **≤ 2 files**
- **No schema changes**, no new public APIs
- No new dependencies
- Low risk of regressions (localized fix)

If any condition fails, use the full 4-doc workflow.

### `bugfix_brief.md` template

```markdown
## Bugfix brief

### Symptom

### Root cause (evidence-based)

### Fix (what changes, why safe)

### Test (what you will run / how you will verify)
```

## Step-by-step process to follow every time

1. **Discovery / intake**
   - Summarize the request in 1–3 sentences.
   - List assumptions vs known facts.
   - List uncertainties that require user confirmation.
2. **Write docs first (sequential)**
   - Create the timestamped directory.
   - Draft `design.md` (or `bugfix_brief.md` for tiny bugfix) and stop.
3. **Align with user (Design)**
   - Ask the user to confirm or correct any uncertainties.
   - Only proceed after explicit alignment.
4. **Write `plan.md`**
   - Only after Design alignment. Stop and align again.
5. **Write `test_plan.md`**
   - Only after Plan alignment. Ensure every test item traces back to `plan.md`. Stop and align again.
4. **Implement**
   - Only after Test Plan alignment.
   - Make minimal, well-scoped changes.
   - Keep changes consistent with the approved docs.
6. **Test**
   - **Execute the approved test plan** (or the brief test steps).
   - If tests are described as commands/scripts, run them.
   - If tests require manual verification, follow the checklist and record outcomes.
7. **Write `change_log.md`**
   - Record what changed, what was tested, results, and any deviations.

## Output conventions

- Prefer **concise, high-signal** docs.
- Use consistent headings.
- Avoid time-sensitive statements.
- When a decision is made, record it in `design.md` (or `bugfix_brief.md`) and `change_log.md`.

