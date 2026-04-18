# student-manager — Forge Example Project

Demonstrates snapshot objects, action endpoints, computed column endpoints, and multi-app composition.

## Quick Start

```bash
cd examples/student-manager
bash setup.sh           # loads data, runs pipeline, builds models + endpoints

forge dev serve &       # starts API server on :8000

# App 1 — student manager
cd apps/student-manager && npm install && npm run dev  # :5173

# App 2 — analytics dashboard
cd apps/analytics && npm install && npm run dev        # :5174
```

## Layer Developer Guide

### Pipeline developer (`pipelines/`)

You ingest `students_raw` and `grades_raw` datasets and produce normalized `students`, `grades`, and `courses` datasets. You work with dataset UUIDs and DataFrames only.

```bash
forge pipeline run student_pipeline
forge pipeline history student_pipeline
forge pipeline dag
```

You do not know about the Student or Grade object types. You do not know what endpoints exist. You do not know what the apps look like.

### Model developer (`models/`)

You declare `Student` (snapshot) and `Grade` (stream) object types. You run `forge model build`.

```bash
forge model build
forge model reinitialize Student   # drop + recreate snapshot from pipeline output
```

`Student` is a snapshot object — mutations persist to a disconnected copy. `Grade` is a stream object — it stays linked to the pipeline output and is read-only.

You do not write pipeline logic. You do not write endpoint logic. You do not write UI code.

### API developer (`endpoint_repos/student_endpoints/`)

You write `create_student` (action endpoint) and `compute_student_metrics` (computed column endpoint returning `gpa` and `rank`). You import from the generated Python SDK.

```bash
forge endpoint build
forge endpoint build --repo student_endpoints   # rebuild this repo only
```

`compute_student_metrics` accepts a list of Student objects and a `timeframe` parameter. It returns per-student `gpa` and `rank` values. The view layer attaches this endpoint to the ObjectTable and binds the `timeframe` parameter to a Selector widget.

You do not write UI code. You do not know about widget structure.

### UI developer (`apps/`)

You import object sets and endpoint IDs. You compose widgets. You never write fetch logic.

```bash
cd apps/student-manager && npm run dev
cd apps/analytics && npm run dev
```

The two apps share the same API server but compose completely different pages. Widget state is not shared between apps.

## What the apps demonstrate

**student-manager app:**
- `ObjectTable` with computed GPA/rank columns
- `Selector` for timeframe, bound via `bindState` to the computed column `timeframe` parameter
- `ButtonGroup` that opens a `Modal` containing an auto-rendered `Form` for `create_student`
- `MetricTile` aggregations

**analytics app:**
- Grade distribution and major breakdown `Chart` widgets
- Student roster `ObjectTable`
- Same underlying data, completely different page composition
