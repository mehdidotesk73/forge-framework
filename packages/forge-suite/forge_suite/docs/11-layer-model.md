# Forge — Model Layer

## What the Model Layer Does

The Model layer defines **typed Python classes over datasets**. It is the bridge between raw Parquet data (written by pipelines) and the business logic above (implemented by endpoints and the view).

When you run `forge model build`, Forge reads the live dataset schema and your model class definition, then generates:
- A **Python SDK** (`.forge/generated/python/<name>.py`) — used by endpoint code
- A **TypeScript SDK** (`.forge/generated/typescript/<Name>.ts`) — imported by your React app
- A **schema artifact** (`.forge/artifacts/<Name>.schema.json`) — read by the framework at runtime

The Model layer has zero knowledge of endpoints or UI. It reads datasets and emits SDKs.

---

## Snapshot vs. Stream

Every Forge model is either `mode="snapshot"` or `mode="stream"`. Choose based on whether you need to mutate the data.

| | Snapshot | Stream |
|---|---|---|
| **Backing data** | Mutable copy of a backing dataset | Immutable pipeline output |
| **CRUD** | Yes — create, update, delete | No — read-only |
| **Use for** | Entities you manage (students, orders, records) | Facts you observe (prices, events, logs) |
| **Dataset** | Separate snapshot Parquet file, overwritten on mutation | Original pipeline output, versioned |
| **Build behavior** | Creates snapshot copy on first `forge model build` | Points directly at pipeline output |

**When to use snapshot:** you need to add, edit, or delete individual records via endpoints.

**When to use stream:** you only need to display or query data that a pipeline produces; no user mutations needed.

---

## Defining a Model

### 1. Write the class

```python
# models/student.py
from forge.model import forge_model, field_def, related

@forge_model(mode="snapshot", backing_dataset="a1b2c3d4-0000-0000-0000-000000000001")
class Student:
    id:          str  = field_def(primary_key=True)
    name:        str  = field_def(display="Full Name")
    email:       str  = field_def(display="Email Address")
    major:       str
    enrolled_at: str
    status:      str
    grade_keys:  str  = field_def(display="Grade IDs")
```

The `backing_dataset` value is the UUID of the dataset — the same UUID assigned by `forge dataset load` and declared in the pipeline's `@pipeline` decorator.

### 2. Register in forge.toml

```toml
[[models]]
class_name = "Student"
mode       = "snapshot"
module     = "models.student"
```

### 3. Build

```bash
forge model build
```

This writes:
- `.forge/artifacts/Student.schema.json`
- `.forge/generated/python/student.py`
- `.forge/generated/typescript/Student.ts`
- Updates barrel exports in both `__init__.py` and `index.ts`

---

## @forge_model Parameters

```python
@forge_model(
    mode:            "snapshot" | "stream",   # required
    backing_dataset: str,                     # required — dataset UUID
)
```

---

## Field Definitions

Use `field_def()` to annotate fields with display metadata and constraints:

```python
from forge.model import field_def

id:    str           = field_def(primary_key=True)
score: float         = field_def(display="Score (%)", display_hint="percent")
notes: str           = field_def(display="Notes", nullable=True)
price: float         = field_def(display="Price", display_hint="currency")
```

**`field_def()` parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `primary_key` | bool | Mark as the model's primary key. Exactly one field must be `primary_key=True`. |
| `display` | str | Human-readable label shown in widgets and generated forms |
| `display_hint` | str | Rendering hint for widgets: `"percent"`, `"currency"` |
| `nullable` | bool | Whether the field can be null. If not set, inferred from `Optional[T]` annotation. |

Fields declared without `field_def()` are inferred from their Python type annotation.

---

## Type Mapping

| Python | Forge type | TypeScript |
|--------|-----------|------------|
| `str` | `string` | `string` |
| `int` | `integer` | `number` |
| `float` | `float` | `number` |
| `bool` | `boolean` | `boolean` |
| `Optional[str]` | `string`, nullable | `string \| undefined` |
| `Optional[float]` | `float`, nullable | `number \| undefined` |

---

## Primary Key Rules

Every model must declare exactly one `primary_key=True` field. The decorator validates this at import time and raises if zero or more than one is found.

**String PKs** — use a short prefixed hex string to avoid collisions:

```python
import uuid

id = f"s{uuid.uuid4().hex[:6]}"   # e.g. "s3a9f2"
```

**Integer PKs** — use sequential IDs or auto-increment logic in your create endpoint.

---

## Relations

Relations express one-to-many links. The related object IDs are stored as a JSON array in a string field:

```python
from forge.model import forge_model, field_def, related

@forge_model(mode="snapshot", backing_dataset="a1b2c3d4-0000-0000-0000-000000000001")
class Student:
    id:         str = field_def(primary_key=True)
    name:       str
    grade_keys: str = field_def(display="Grade IDs")

    grades = related(target_model="Grade", via="grade_keys")
```

`related()` adds a method `student.grades()` that:
1. Reads `self.grade_keys` as a JSON array of IDs
2. Fetches the Grade dataset
3. Filters to matching primary keys
4. Returns a list of `Grade` instances

The `via` parameter is the field name that holds the JSON key list. The target model class must also be `@forge_model`-decorated and imported before the method is called. Inside endpoint context, the engine is injected automatically — no `engine=` needed.

### Maintaining relations in endpoints

Relations are stored as JSON strings — you must update them manually when creating or deleting linked objects:

```python
import json

# Create a grade and link it to a student:
new_grade = Grade.create(id=f"g{uuid.uuid4().hex[:6]}", ...)
student = Student.get(student_id)
keys = json.loads(student.grade_keys or "[]")
keys.append(new_grade.id)
student.grade_keys = json.dumps(keys)   # dirty-tracked, flushed atomically

# Delete a grade and unlink it:
grade = Grade.get(grade_id)
grade.remove()
student = Student.get(grade.student_id)
keys = json.loads(student.grade_keys or "[]")
keys.remove(grade_id)
student.grade_keys = json.dumps(keys)
```

---

## Reading Data

These class methods are available on all model classes. Inside an endpoint the engine is injected from request context automatically. Outside an endpoint you must supply `engine` explicitly.

```python
# All records
students = Student.all()                          # inside endpoint (engine injected)
students = Student.all(engine=engine)             # outside endpoint

# Single record by PK — returns None if not found
student = Student.get("s1a2b3")

# Batch fetch — preserves input order
students = Student.get_many(["s1", "s2", "s3"])

# Equality filter — all kwargs are AND conditions
active = Student.filter(status="active", major="CS")
```

---

## Writing Data (Snapshot Models Only)

### Create

```python
student = Student.create(
    id=f"s{uuid.uuid4().hex[:6]}",
    name="Alice Smith",
    email="alice@example.com",
    major="Computer Science",
    enrolled_at="2024-09-01",
    status="active",
    grade_keys="[]",
)
```

If `id` is omitted and the PK field is a string, Forge auto-generates a UUID-based ID.

### Update (via attribute assignment)

```python
student = Student.get(student_id)
student.name  = "Alice Johnson"
student.email = "alicej@example.com"
# mutations are dirty-tracked; flushed atomically when the endpoint returns
```

You can also call `.update()` explicitly if you are outside an endpoint context:

```python
student.update(engine=engine, name="Alice Johnson")
```

### Delete

```python
student = Student.get(student_id)
student.remove()
```

---

## Unit of Work and Dirty Tracking

Inside an endpoint call, every `create`, `setattr`, and `remove` on managed model instances is automatically tracked. When the endpoint returns:

- **Success** — all pending creates, updates, and deletes are flushed atomically to storage
- **Raises** — all pending mutations are discarded (rolled back); storage is unchanged

You do not need to call flush or commit explicitly. The `@action_endpoint` runtime handles this for you.

---

## Stream Models

Stream models are read-only views of pipeline output:

```python
@forge_model(mode="stream", backing_dataset="a1b2c3d4-0000-0000-0000-000000000099")
class StockPrice:
    symbol: str   = field_def(primary_key=True)
    ts:     str
    close:  float
    volume: int
```

Stream models support only `all()`, `get()`, `get_many()`, and `filter()`. Calling `create()`, `update()`, or `remove()` on a stream model raises `NotImplementedError`.

---

## Reinitializing a Snapshot

If you need to reset a snapshot model back to the state of its backing dataset (e.g. after bad mutations in development):

```bash
forge model reinitialize Student
```

This drops the snapshot Parquet file and creates a fresh copy from the backing dataset. **All mutations since the last pipeline run are lost.** Use only in development.

---

## Generated Python SDK

The generated file at `.forge/generated/python/student.py` provides a typed dataclass and a set class:

```python
@dataclass
class Student:
    id:          str
    name:        str
    email:       str
    major:       str
    enrolled_at: str
    status:      str
    grade_keys:  str

    @classmethod
    def all(cls) -> list["Student"]: ...

    @classmethod
    def get(cls, pk: str) -> "Student | None": ...

    @classmethod
    def get_many(cls, pks: list[str]) -> list["Student"]: ...

    @classmethod
    def filter(cls, **kwargs) -> list["Student"]: ...

    # Snapshot only:
    @classmethod
    def create(cls, **kwargs) -> "Student": ...

    def remove(self): ...

    def _to_dict(self) -> dict: ...
```

Import this in endpoint files:

```python
from forge.generated.python.student import Student
```

---

## Generated TypeScript SDK

The generated file at `.forge/generated/typescript/Student.ts` provides a typed interface and a loader function:

```typescript
export interface Student {
  id:          string;
  name:        string;
  email:       string;
  major:       string;
  enrolled_at: string;
  status:      string;
  grade_keys:  string;
}

export const StudentSchema: ForgeSchema = { ... };

export async function loadStudentSet(
  options?: { limit?: number; offset?: number }
): Promise<ForgeObjectSet<Student>> { ... }
```

Import this in your React app:

```typescript
import { loadStudentSet } from "../../../.forge/generated/typescript/Student";
```

Never write `fetch` calls for object data directly — always use the generated loader.

---

## Schema Artifact

`forge model build` writes `.forge/artifacts/<Name>.schema.json`. This file is read by the TypeScript runtime and by the Forge Suite webapp:

```json
{
  "class_name": "Student",
  "mode": "snapshot",
  "primary_key": "id",
  "fields": {
    "id":          {"type": "string",  "nullable": false, "display": "ID"},
    "name":        {"type": "string",  "nullable": false, "display": "Full Name"},
    "email":       {"type": "string",  "nullable": false, "display": "Email Address"},
    "major":       {"type": "string",  "nullable": false},
    "enrolled_at": {"type": "string",  "nullable": false},
    "status":      {"type": "string",  "nullable": false},
    "grade_keys":  {"type": "string",  "nullable": false, "display": "Grade IDs"}
  }
}
```

The schema is rebuilt from the **live dataset** on each `forge model build`. If a pipeline adds a new column, rebuild to pick it up.

---

## Isolation Rules

The Model layer must **never**:

- Import `@action_endpoint` or `@computed_attribute_endpoint` decorators
- Import anything from `packages/forge-ts` or any React/widget code
- Construct HTTP requests
- Reference UI concerns (display state, routing, component lifecycle)

Model classes may be imported by the Control layer. The Control layer may not be imported by the Model layer.

---

## Full Example — Student and Grade Models

```python
# models/student.py
from forge.model import forge_model, field_def, related

@forge_model(mode="snapshot", backing_dataset="de271075-b375-4b05-bd79-eb710df8b2c3")
class Student:
    id:          str  = field_def(primary_key=True)
    name:        str  = field_def(display="Full Name")
    email:       str  = field_def(display="Email Address")
    major:       str  = field_def(display="Major")
    enrolled_at: str  = field_def(display="Enrolled At")
    status:      str  = field_def(display="Status")
    grade_keys:  str  = field_def(display="Grade IDs")

    grades = related(target_model="Grade", via="grade_keys")
```

```python
# models/grade.py
from forge.model import forge_model, field_def

@forge_model(mode="snapshot", backing_dataset="df13b4b7-8704-4082-8822-895de3d4ec41")
class Grade:
    id:         str   = field_def(primary_key=True)
    student_id: str   = field_def(display="Student")
    course:     str   = field_def(display="Course")
    semester:   str   = field_def(display="Semester")
    grade:      str   = field_def(display="Grade")
    credits:    int   = field_def(display="Credits")
```

```toml
# forge.toml
[[models]]
class_name = "Student"
mode       = "snapshot"
module     = "models.student"

[[models]]
class_name = "Grade"
mode       = "snapshot"
module     = "models.grade"
```

```bash
forge model build
# Creates Student.schema.json, Grade.schema.json
# Generates student.py, grade.py, Student.ts, Grade.ts
```

---

## Full Example — Stream Model (Stock Price)

```python
# models/stock_price.py
from forge.model import forge_model, field_def

@forge_model(mode="stream", backing_dataset="22222222-0000-0000-0000-000000000001")
class StockPrice:
    symbol: str   = field_def(primary_key=True)
    ts:     str   = field_def(display="Timestamp")
    close:  float = field_def(display="Close Price", display_hint="currency")
    volume: int   = field_def(display="Volume")
```

```toml
[[models]]
class_name = "StockPrice"
mode       = "stream"
module     = "models.stock_price"
```

Endpoints can read from this model but cannot mutate it:

```python
from forge.generated.python.stock_price import StockPrice

prices = StockPrice.filter(symbol="BTC")  # ok
prices[0].close = 100.0                   # raises NotImplementedError
```
