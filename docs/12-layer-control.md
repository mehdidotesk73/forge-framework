# Forge — Control Layer

## What the Control Layer Does

The Control layer exposes **business logic as callable HTTP endpoints**. It is the bridge between the data managed by models and the interfaces consumed by the view layer.

Control code imports model classes, creates and mutates records, performs computations, and returns results. It never imports widget code or writes UI logic.

There are three kinds of endpoints:

- **Action endpoints** — discrete operations triggered by forms or buttons: create, update, delete, custom business logic
- **Computed column endpoints** — batch computations over a set of objects, producing per-row derived values displayed in a table
- **Streaming endpoints** — long-running operations that emit incremental output via Server-Sent Events (SSE)

---

## Core Concepts

### Unit of Work

Every endpoint call runs inside a Unit of Work (UoW). When an endpoint function returns:

- **Success** — all `create`, `setattr`, and `remove` calls on managed model instances are flushed atomically to storage
- **Raises** — all pending mutations are rolled back; storage is unchanged

You never call flush or commit. The runtime does it automatically.

### Engine Injection

Inside an endpoint function, the StorageEngine and UnitOfWork are injected via context variables. Model class methods (`Student.get()`, `Student.create()`, etc.) pick up the engine automatically — you do not pass `engine=` explicitly inside endpoint functions.

### Endpoint Registry

`@action_endpoint` and `@computed_attribute_endpoint` register into a global registry at import time. `forge endpoint build` imports all modules in configured endpoint repos, collects the registry, and writes `.forge/artifacts/endpoints.json`.

### Stable UUIDs

**Endpoint UUIDs must never change after first deployment.** The view layer references endpoints by UUID (not by name). Changing a UUID breaks the view.

- Generate UUIDs once: `python -c "import uuid; print(uuid.uuid4())"`
- Hardcode them as constants in your endpoint files
- Keep them forever — never regenerate

---

## Action Endpoints

Action endpoints handle discrete operations: creating, updating, deleting objects, or any custom business logic.

### Syntax

```python
from forge.control import action_endpoint

@action_endpoint(
    name="create_student",
    endpoint_id="11111111-0000-0000-0000-000000000001",
    description="Create a new student record.",
    params=[
        {"name": "name",   "type": "string",  "required": True,  "description": "Full name"},
        {"name": "email",  "type": "string",  "required": True,  "description": "Email address"},
        {"name": "major",  "type": "string",  "required": True,  "description": "Declared major"},
        {"name": "status", "type": "string",  "required": False, "default": "active"},
    ]
)
def create_student(name: str, email: str, major: str, status: str = "active") -> dict:
    import uuid
    student = Student.create(
        id=f"s{uuid.uuid4().hex[:6]}",
        name=name,
        email=email,
        major=major,
        status=status,
        enrolled_at=str(__import__("datetime").date.today()),
        grade_keys="[]",
    )
    return student._to_dict()
```

**`@action_endpoint` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | no | Identifier shown in the auto-rendered Form widget; defaults to the function name |
| `endpoint_id` | str (UUID) | yes | Stable UUID; **never change this after first deployment** |
| `description` | str | yes | Shown in Form UI and OpenAPI docs |
| `params` | list[dict] | yes | Ordered parameter list |

**`params` entry keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | str | yes | Must match the function parameter name exactly |
| `type` | str | yes | `"string"`, `"integer"`, `"float"`, `"boolean"` |
| `required` | bool | yes | If false, must supply `"default"` |
| `description` | str | no | Shown as input placeholder/label in the Form widget |
| `default` | any | when not required | Value used if the caller omits the param |

### Return value

Return any JSON-serializable value. Typically:
- `instance._to_dict()` for single-object mutations
- `{"ok": True}` for side-effect-only operations (deletes, bulk updates)
- `{"error": "message"}` is an anti-pattern — raise instead (see Error Handling)

---

## Computed Column Endpoints

Computed column endpoints attach derived values to rows in an `ObjectTable`. The endpoint receives a list of model objects, performs batch computation, and returns a nested dict mapping primary keys to column values.

Use computed columns for values that:
- Require joining across multiple models (e.g. GPA from grades)
- Are expensive to pre-compute for all rows but only needed for visible rows
- Should re-compute when UI state changes (e.g. filtered timeframe)

### Syntax

```python
from forge.control import computed_attribute_endpoint
from models.student import Student
from models.grade import Grade

@computed_attribute_endpoint(
    object_type="Student",
    columns=["gpa", "letter_rank"],
    endpoint_id="22222222-0000-0000-0000-000000000002",
    name="compute_student_metrics",
    description="Compute GPA and letter rank for a list of students.",
    params=[
        {"name": "timeframe", "type": "string", "required": False, "default": "all"},
    ]
)
def compute_student_metrics(students: list[Student], timeframe: str = "all") -> dict:
    result = {}
    for student in students:
        grades = student.grades()    # relation method; engine injected in endpoint context
        filtered = [g for g in grades if timeframe == "all" or g.semester == timeframe]

        if not filtered:
            result[student.id] = {"gpa": None, "letter_rank": "N/A"}
            continue

        grade_map = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
        total_pts  = sum(grade_map.get(g.grade, 0) * g.credits for g in filtered)
        total_cred = sum(g.credits for g in filtered)
        gpa        = round(total_pts / total_cred, 2) if total_cred else None

        letter_rank = (
            "A" if gpa and gpa >= 3.7 else
            "B" if gpa and gpa >= 3.0 else
            "C" if gpa and gpa >= 2.0 else
            "D"
        )
        result[student.id] = {"gpa": gpa, "letter_rank": letter_rank}

    return result
```

**`@computed_attribute_endpoint` parameters:**

All parameters from `@action_endpoint`, plus:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `object_type` | str | yes | Model class name (e.g. `"Student"`) |
| `columns` | list[str] | yes | Column names produced by this endpoint |

### Return contract

```python
{
    "<primary_key_value>": {
        "<column_name>": <value>,
        ...
    },
    ...
}
```

The primary key values must match the PK field of the input objects. Rows absent from the result show empty cells. Values may be `None` for nullable display.

### Wiring to ObjectTable

In your React app, pass `computedColumns` to `ObjectTable`:

```tsx
<ObjectTable
  objectSet={studentSet}
  computedColumns={[
    {
      endpointId: "22222222-0000-0000-0000-000000000002",
      columns: ["gpa", "letter_rank"],
      params: {
        timeframe: { stateKey: "selectedTimeframe" },   // resolved from localState
      },
    },
  ]}
  localState={{ selectedTimeframe: selectedTimeframe }}
/>
```

`ObjectTable` calls the endpoint automatically with the visible rows' primary keys plus any resolved params. When `selectedTimeframe` changes, the columns re-fetch.

---

## Streaming Endpoints

Streaming endpoints handle long-running operations (builds, pipeline runs, batch jobs) that emit incremental output to the caller via Server-Sent Events (SSE).

### Syntax

```python
from forge.control import streaming_endpoint

@streaming_endpoint(
    endpoint_id="33333333-0000-0000-0000-000000000001",
    description="Build all models and stream log output.",
    params=[]
)
def build_models(emit):
    emit("Starting model build...\n")
    # ... do work ...
    emit("Done.\n")
```

The function receives an `emit` callable. Call `emit(text)` to send a chunk to the client. When the function returns, the stream closes.

**`@streaming_endpoint` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | no | Identifier; defaults to the function name |
| `endpoint_id` | str (UUID) | yes | Stable UUID; **never change this after first deployment** |
| `description` | str | yes | Shown in the Forge Suite endpoint panel |
| `params` | list[dict] | yes | Ordered parameter list (same format as action endpoints) |

### Calling from the view layer

```typescript
import { callStreamingEndpoint } from "@forge-suite/ts";

callStreamingEndpoint(
  BUILD_MODELS_ID,
  {},                                      // params
  (chunk) => setLog((prev) => prev + chunk) // onChunk callback
);
```

---

## Endpoint Repository Layout

Organize endpoint files into a Python package under `endpoint_repos/`:

```
endpoint_repos/
  student_endpoints/
    __init__.py
    student_endpoints/
      __init__.py
      create.py
      edit.py
      delete.py
      grades.py
      metrics.py
      constants.py
```

Register the repo in `forge.toml`:

```toml
[[endpoint_repos]]
module = "endpoint_repos.student_endpoints"
```

`forge endpoint build` recursively imports all `*.py` files under the repo path, triggering decorator registration, then writes `endpoints.json`.

Multiple repos are supported — useful when different teams own different endpoint sets:

```toml
[[endpoint_repos]]
module = "endpoint_repos.student_endpoints"

[[endpoint_repos]]
module = "endpoint_repos.course_endpoints"
```

---

## UUID Constants File

Store endpoint UUIDs in a constants file to avoid duplication:

```python
# endpoint_repos/student_endpoints/student_endpoints/constants.py
CREATE_STUDENT_ID  = "11111111-0000-0000-0000-000000000001"
EDIT_STUDENT_ID    = "11111111-0000-0000-0000-000000000002"
DELETE_STUDENT_ID  = "11111111-0000-0000-0000-000000000003"
COMPUTE_METRICS_ID = "22222222-0000-0000-0000-000000000002"
```

Import them in endpoint files and in your React app:

```python
# In endpoint file:
from .constants import CREATE_STUDENT_ID

@action_endpoint(endpoint_id=CREATE_STUDENT_ID, ...)
```

```typescript
// In React app (same UUID, declared as a TypeScript constant):
const CREATE_STUDENT_ID = "11111111-0000-0000-0000-000000000001";
```

---

## Building Endpoints

```bash
forge endpoint build                          # build all repos
forge endpoint build --repo student_endpoints # single repo
```

Output: `.forge/artifacts/endpoints.json` — a flat dict of `{endpoint_id: descriptor}`.

Example descriptor:

```json
{
  "11111111-0000-0000-0000-000000000001": {
    "id": "11111111-0000-0000-0000-000000000001",
    "name": "create_student",
    "kind": "action",
    "description": "Create a new student record.",
    "repo": "student_endpoints",
    "params": [
      {"name": "name",   "type": "string", "required": true},
      {"name": "email",  "type": "string", "required": true},
      {"name": "major",  "type": "string", "required": true},
      {"name": "status", "type": "string", "required": false, "default": "active"}
    ]
  }
}
```

---

## Error Handling

Raise any Python exception and the runtime:
1. Rolls back all pending mutations
2. Returns HTTP 500 with the error message to the caller
3. The `<Form>` widget surfaces the error message to the user

Use `ValueError` for user-facing validation errors, `RuntimeError` for unexpected states:

```python
@action_endpoint(...)
def create_student(name: str, email: str, major: str) -> dict:
    if not email.strip():
        raise ValueError("Email address is required.")
    if Student.filter(email=email):
        raise ValueError(f"A student with email {email!r} already exists.")
    ...
```

---

## Multi-Object Mutations

An endpoint can create, update, or delete multiple objects — the UoW batches them all:

```python
@action_endpoint(
    name="bulk_graduate",
    endpoint_id="11111111-0000-0000-0000-000000000009",
    description="Set all active students to graduated status.",
    params=[]
)
def bulk_graduate() -> dict:
    students = Student.filter(status="active")
    for s in students:
        s.status = "graduated"   # each setattr dirty-tracked
    return {"graduated": len(students)}
    # All updates flushed atomically when this returns
```

---

## Isolation Rules

The Control layer must **never**:

- Import anything from `packages/forge-ts` or any React/widget code
- Construct HTTP requests or call the Forge HTTP API (the endpoint IS inside the API)
- Reference frontend routing, component state, or UI concerns
- Import other endpoint modules (endpoints are independent; share logic via plain Python modules)

Shared business logic used by multiple endpoints should live in a separate Python module (e.g. `lib/gpa.py`) that both endpoint files import.

---

## Full Example — Complete Student Endpoint Repo

```python
# endpoint_repos/student_endpoints/student_endpoints/constants.py
CREATE_STUDENT_ID  = "11111111-0000-0000-0000-000000000001"
EDIT_STUDENT_ID    = "11111111-0000-0000-0000-000000000002"
DELETE_STUDENT_ID  = "11111111-0000-0000-0000-000000000003"
ADD_GRADE_ID       = "11111111-0000-0000-0000-000000000004"
COMPUTE_METRICS_ID = "22222222-0000-0000-0000-000000000002"
```

```python
# endpoint_repos/student_endpoints/student_endpoints/create.py
import uuid, datetime
from forge.control import action_endpoint
from forge.generated.python.student import Student
from .constants import CREATE_STUDENT_ID

@action_endpoint(
    name="create_student",
    endpoint_id=CREATE_STUDENT_ID,
    description="Create a new student record.",
    params=[
        {"name": "name",   "type": "string", "required": True},
        {"name": "email",  "type": "string", "required": True},
        {"name": "major",  "type": "string", "required": True},
        {"name": "status", "type": "string", "required": False, "default": "active"},
    ]
)
def create_student(name: str, email: str, major: str, status: str = "active") -> dict:
    if Student.filter(email=email):
        raise ValueError(f"Email {email!r} is already registered.")
    student = Student.create(
        id=f"s{uuid.uuid4().hex[:6]}",
        name=name, email=email, major=major,
        status=status,
        enrolled_at=str(datetime.date.today()),
        grade_keys="[]",
    )
    return student._to_dict()
```

```python
# endpoint_repos/student_endpoints/student_endpoints/edit.py
from forge.control import action_endpoint
from forge.generated.python.student import Student
from .constants import EDIT_STUDENT_ID

@action_endpoint(
    name="edit_student",
    endpoint_id=EDIT_STUDENT_ID,
    description="Update one or more fields on an existing student.",
    params=[
        {"name": "id",     "type": "string", "required": True},
        {"name": "name",   "type": "string", "required": False, "default": None},
        {"name": "email",  "type": "string", "required": False, "default": None},
        {"name": "major",  "type": "string", "required": False, "default": None},
        {"name": "status", "type": "string", "required": False, "default": None},
    ]
)
def edit_student(
    id: str,
    name: str | None = None,
    email: str | None = None,
    major: str | None = None,
    status: str | None = None,
) -> dict:
    student = Student.get(id)
    if student is None:
        raise ValueError(f"No student with id {id!r}.")
    if name   is not None: student.name   = name
    if email  is not None: student.email  = email
    if major  is not None: student.major  = major
    if status is not None: student.status = status
    return student._to_dict()
```

```python
# endpoint_repos/student_endpoints/student_endpoints/delete.py
from forge.control import action_endpoint
from forge.generated.python.student import Student
from forge.generated.python.grade import Grade
from .constants import DELETE_STUDENT_ID
import json

@action_endpoint(
    name="delete_student",
    endpoint_id=DELETE_STUDENT_ID,
    description="Delete a student and all their grades.",
    params=[
        {"name": "id", "type": "string", "required": True},
    ]
)
def delete_student(id: str) -> dict:
    student = Student.get(id)
    if student is None:
        raise ValueError(f"No student with id {id!r}.")
    grade_ids = json.loads(student.grade_keys or "[]")
    for grade_id in grade_ids:
        grade = Grade.get(grade_id)
        if grade:
            grade.remove()
    student.remove()
    return {"ok": True}
```
