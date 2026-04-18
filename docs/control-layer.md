# Forge — Control Layer Developer Guide

## Purpose

The Control layer exposes **business logic as callable endpoints**. It is the bridge between the data managed by models and the interfaces consumed by the view layer. Control code imports model classes, performs mutations, and returns results — but it never imports widget code or writes UI logic.

There are two kinds of endpoints:
- **Action endpoints** — discrete operations triggered by forms or button clicks (create, update, delete, custom logic)
- **Computed column endpoints** — batch computations over a set of objects, producing per-row derived values for display in a table

---

## Core Concepts

### Unit of Work

Every endpoint call runs inside a Unit of Work (UoW). When an endpoint function returns:
- All `create`, `setattr`, and `remove` calls on managed model instances are **flushed atomically** to storage
- If the function raises, all pending mutations are **rolled back** — storage is unchanged

You do not call flush or commit. The runtime does it automatically.

### Context Variables

Inside an endpoint function, the StorageEngine and UnitOfWork are injected via context variables. Model class methods (`Student.get()`, `Student.create()`, etc.) pick up the engine from context automatically — you do not pass `engine=` explicitly inside endpoint functions.

### Endpoint Registry

`@action_endpoint` and `@computed_column_endpoint` register into a global `_ENDPOINT_REGISTRY` at import time. `forge endpoint build` imports all modules in the configured endpoint repos, collects the registry, and writes `.forge/artifacts/endpoints.json`.

---

## Action Endpoints

### Declaring an Action Endpoint

```python
# endpoints/student/create.py
import uuid
from forge.control import action_endpoint
from models.student import Student

@action_endpoint(
    name="create_student",
    endpoint_id="11111111-0000-0000-0000-000000000001",
    description="Create a new student record.",
    params=[
        {"name": "name",  "type": "string",  "required": True,  "description": "Full name"},
        {"name": "email", "type": "string",  "required": True,  "description": "Email address"},
        {"name": "major", "type": "string",  "required": True,  "description": "Declared major"},
        {"name": "status","type": "string",  "required": False, "default": "active"},
    ]
)
def create_student(name: str, email: str, major: str, status: str = "active") -> dict:
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
| `name` | str | yes | Identifier; also shown in the auto-rendered Form |
| `endpoint_id` | str (UUID) | yes | Stable UUID; never change this after first deployment |
| `description` | str | yes | Shown in Form UI and OpenAPI docs |
| `params` | list[dict] | yes | Ordered parameter list (see below) |

**`params` entry keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | str | yes | Must match the function parameter name |
| `type` | str | yes | `"string"`, `"integer"`, `"float"`, `"boolean"` |
| `required` | bool | yes | If false, must supply `"default"` |
| `description` | str | no | Shown as input placeholder/label |
| `default` | any | when not required | Value used if the caller omits the param |

### Return Value

Return any JSON-serializable value. The FastAPI route wraps it in a JSON response. Typically return `instance._to_dict()` for single-object mutations, or `{"ok": True}` for side-effect-only operations.

### Calling an Endpoint from TypeScript

```typescript
import { callEndpoint } from "@forge-framework/ts";

const result = await callEndpoint<Student>(
  "11111111-0000-0000-0000-000000000001",
  { name: "Alice", email: "alice@example.com", major: "CS" }
);
```

Or use the `<Form>` widget — it auto-renders an input form from the endpoint descriptor.

---

## Computed Column Endpoints

Computed columns attach derived values to rows in an `<ObjectTable>`. The endpoint receives a list of model objects, performs batch computation (e.g. GPA calculation, rank assignment, external data lookup), and returns a nested dict mapping primary keys to column values.

### Declaring a Computed Column Endpoint

```python
# endpoints/student/metrics.py
from forge.control import computed_column_endpoint
from models.student import Student
from models.grade import Grade

@computed_column_endpoint(
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
        grades = student.grades()  # relation method, no engine= needed in endpoint context
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

**`@computed_column_endpoint` parameters:**

All parameters from `@action_endpoint`, plus:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `object_type` | str | yes | Model class name (e.g. `"Student"`) |
| `columns` | list[str] | yes | Column names produced by this endpoint |

**Return contract:**

```python
{
    "<primary_key_value>": {
        "<column_name>": <value>,
        ...
    },
    ...
}
```

The primary key values must match the `id` (or whatever the PK field is) of the input objects. Rows absent from the result dict will show empty cells.

### Wiring to ObjectTable

In your React app:

```tsx
<ObjectTable
  objectSet={studentSet}
  computedColumns={[
    {
      endpointId: "22222222-0000-0000-0000-000000000002",
      params: {
        timeframe: { stateKey: "selectedTimeframe" },  // bound to local UI state
      },
      columns: ["gpa", "letter_rank"],
    },
  ]}
  localState={{ selectedTimeframe: selectedTimeframe }}
/>
```

`ObjectTable` calls the endpoint automatically with the visible rows' PKs and the resolved `params`.

---

## Endpoint Repository Layout

Organize endpoint files into a repo directory and declare it in `forge.toml`:

```
endpoints/
  student/
    __init__.py
    create.py
    edit.py
    delete.py
    grades.py
    metrics.py
```

```toml
[[endpoint_repos]]
name = "student_endpoints"
path = "endpoints/student"
```

`forge endpoint build` recursively imports all `*.py` files under `path`, triggering decorator registration, then writes `endpoints.json`.

Multiple repos are supported — useful when different teams own different endpoint sets.

---

## Building Endpoints

```bash
forge endpoint build                    # build all repos
forge endpoint build --repo student_endpoints  # single repo
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
      {"name": "name",  "type": "string", "required": true},
      {"name": "email", "type": "string", "required": true},
      {"name": "major", "type": "string", "required": true},
      {"name": "status","type": "string", "required": false, "default": "active"}
    ]
  }
}
```

---

## Error Handling

Raise any Python exception from an endpoint function and the runtime:
1. Rolls back all pending mutations
2. Returns a 500 with the error message to the caller
3. The `<Form>` widget surfaces the error message to the user

Use `ValueError` for user-facing validation errors, `RuntimeError` for unexpected states.

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

## Endpoint IDs

**Endpoint UUIDs must be stable.** The view layer references endpoints by UUID (not by name). If you change a UUID after the app is deployed, the view breaks.

- Generate UUIDs once (e.g. `python -c "import uuid; print(uuid.uuid4())"`) and hardcode them
- Store them in a constants file if you reference the same UUID in multiple places:

```python
# endpoints/student/constants.py
CREATE_STUDENT_ID    = "11111111-0000-0000-0000-000000000001"
EDIT_STUDENT_ID      = "11111111-0000-0000-0000-000000000002"
DELETE_STUDENT_ID    = "11111111-0000-0000-0000-000000000003"
COMPUTE_METRICS_ID   = "22222222-0000-0000-0000-000000000002"
```

---

## Multi-Object Mutations

An endpoint function can create, update, or delete multiple objects — the UoW batches them all:

```python
@action_endpoint(
    name="bulk_graduate",
    endpoint_id="...",
    description="Set all active students to graduated status.",
    params=[]
)
def bulk_graduate() -> dict:
    students = Student.filter(status="active")
    for s in students:
        s.status = "graduated"   # dirty-tracked for each
    return {"graduated": len(students)}
    # All updates flushed atomically when this returns
```

---

## Isolation Rules

The Control layer must **never**:

- Import anything from `packages/forge-ts` or any React/widget code
- Construct HTTP requests or call the Forge HTTP API (it is running inside the API)
- Reference frontend routing, component state, or UI concerns
- Import other endpoint modules (endpoints are independent; share logic via plain Python modules)

Shared business logic used by multiple endpoints should live in a separate Python module (e.g. `lib/gpa.py`) that both endpoint files import.

---

## Full Example: Edit Student Endpoint

```python
# endpoints/student/edit.py
from forge.control import action_endpoint
from models.student import Student

@action_endpoint(
    name="edit_student",
    endpoint_id="11111111-0000-0000-0000-000000000002",
    description="Update one or more fields on an existing student.",
    params=[
        {"name": "id",     "type": "string",  "required": True},
        {"name": "name",   "type": "string",  "required": False, "default": None},
        {"name": "email",  "type": "string",  "required": False, "default": None},
        {"name": "major",  "type": "string",  "required": False, "default": None},
        {"name": "status", "type": "string",  "required": False, "default": None},
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
