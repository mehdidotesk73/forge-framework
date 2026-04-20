# Documentation Overhaul — Task Plan

Use this file to track progress and recover the session. Check off each item as it completes.

## Status

- [x] Research phase — read all source files
- [x] Write layer docs (Batch 1)
- [x] Write project developer docs (Batch 2)
- [x] Write suite developer docs (Batch 3)
- [x] Update release script + README (Batch 4)
- [x] Write Claude command files (Batch 5)
- [x] Remove old docs (Batch 6)

---

## Batch 1 — Layer docs (parallel writes)

- [x] `docs/10-layer-pipeline.md` — @pipeline decorator, ForgeInput/Output, DuckDB, scheduling, DAG, isolation
- [x] `docs/11-layer-model.md` — snapshot vs stream, @forge_model, field_def, CRUD, UoW, relations, generated SDKs
- [x] `docs/12-layer-control.md` — action_endpoint, computed_attribute_endpoint, UoW, stable UUIDs, multi-object mutations
- [x] `docs/13-layer-view.md` — all widgets, ForgeAction, StateBinding, loading data, isolation

## Batch 2 — Project developer docs

- [x] `docs/01-project-getting-started.md` — what Forge does, pip install forge-suite, forge-suite serve, full tutorial (sidebar-corrected)
- [x] `docs/02-project-widget-reference.md` — all widgets with multiple copy-paste examples

## Batch 3 — Suite developer docs

- [x] `docs/20-suite-developer-guide.md` — architecture, dev commands, restart requirements, publishing, CLI reference
- [x] `docs/21-suite-todo.md` — move/update from docs/todo.md

## Batch 4 — Infrastructure

- [x] `dev/release.sh` — add copy step in Phase 5: docs/*.md → packages/forge-suite/forge_suite/docs/
- [x] `README.md` — full overhaul; point to 01-project-getting-started.md as entry point

## Batch 5 — Claude command files

- [x] `.claude/commands/pipeline.md` — what to read/update for pipeline changes
- [x] `.claude/commands/model.md` — what to read/update for model changes
- [x] `.claude/commands/control.md` — what to read/update for endpoint changes
- [x] `.claude/commands/view.md` — what to read/update for widget/view changes
- [x] `.claude/commands/suite.md` — what to read/update for suite changes

## Batch 6 — Remove old superseded docs

- [x] Remove `docs/pipeline-layer.md` (replaced by 10-layer-pipeline.md)
- [x] Remove `docs/model-layer.md` (replaced by 11-layer-model.md)
- [x] Remove `docs/control-layer.md` (replaced by 12-layer-control.md)
- [x] Remove `docs/view-layer.md` (replaced by 13-layer-view.md)
- [x] Remove `docs/new-project-guide.md` (replaced by 01-project-getting-started.md)
- [x] Remove `docs/todo.md` (replaced by 21-suite-todo.md)

---

## Key decisions recorded

- Flat docs/ folder, filenames prefixed with section number so UI sort order = logical order
- docs/*.md are copied to both packages/forge-py/forge/docs/ and packages/forge-suite/forge_suite/docs/ during publish
- Navigation in UI is "left sidebar", NOT "top navigation bar"
- Endpoint UUIDs and dataset UUIDs: never regenerate; assign once
- pipeline_id is optional in @pipeline decorator; maps to id in [[pipelines]] in forge.toml
