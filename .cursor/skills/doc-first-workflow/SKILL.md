---
name: doc-first-workflow
description: Enforces a documentation-first engineering workflow (Design → Execution Plan → Test Plan → Implementation) with timestamped artifacts and change logs. Use whenever implementing new features, refactors, data pipelines, or any non-trivial code change, or when the user asks for a plan/process, documentation, or wants changes recorded. Also applies a lightweight fast-track for tiny bugfixes while still requiring written documentation before code edits.
---

# Doc-first workflow (Design → Plan → Test → Implement)

## Core rules (hard constraints)

1. **No implementation before docs**: Do not modify code until the required docs for the current change are written to disk and the user confirms alignment.
2. **Timestamped directory per change**: Every feature/change gets its own directory: `metadata/plans/YYYY-MM-DD_HHMM_<topic>/` (or the project’s chosen plans root).
3. **Written artifacts required**:
   - `design.md`
   - `plan.md`
   - `test_plan.md`
   - `change_log.md`
4. **Changes always recorded**: For every subsequent change/new feature, create a new timestamped directory; never overwrite prior change docs.

## Fast-track for tiny bugfixes (still doc-first)

If the change is a *tiny bugfix*, use a lightweight doc set:

- Create `metadata/plans/YYYY-MM-DD_HHMM_<topic>/`
- Write **only**:
  - `bugfix_brief.md` (template below)
  - `change_log.md`

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
2. **Write docs first**
   - Create the timestamped directory.
   - Draft `design.md` (or `bugfix_brief.md` for tiny bugfix).
   - Draft `plan.md` and `test_plan.md` (unless tiny bugfix).
   - Draft `change_log.md`.
3. **Align with user**
   - Ask the user to confirm or correct any uncertainties.
   - Only proceed after explicit alignment.
4. **Implement**
   - Make minimal, well-scoped changes.
   - Keep changes consistent with the approved docs.
5. **Test**
   - Execute the approved test plan (or the brief test steps).
   - Record results (and any deviations) in the change docs.

## Output conventions

- Prefer **concise, high-signal** docs.
- Use consistent headings.
- Avoid time-sensitive statements.
- When a decision is made, record it in `design.md` (or `bugfix_brief.md`) and `change_log.md`.

