# Forge — Model Layer Developer Guide

## Purpose

The Model layer defines **typed object representations** of your datasets. It is the bridge between raw Parquet data (written by pipelines) and the business logic above (implemented by endpoints). Its build output is a pair of SDKs — Python and TypeScript — plus a schema artifact used by the framework at runtime.

The Model layer has zero knowledge of endpoints or UI. It reads datasets and emits schema + SDKs.

---

## Core Concepts

### Snapshot vs. Stream

Every Forge model is either `mode="snapshot"` or `mode="stream"`.

| | Snapshot | Stream |
|---|---|---|
| **Backing data** | Mutable copy of a backing dataset | Immutable pipeline output |
| **CRUD** | Yes — `create`, `update`, `remove` | No — read-only |
| **Use for** | Entities you manage (students, orders) | Facts you observe (prices, events) |
| **Dataset** | Separate snapshot file, overwritten in place | Original pipeline output, versioned |

### Dataset Resolution

When a snapshot model is built, Forge:
1. Reads the backing dataset (identified by UUID in `forge.toml`)
2. Creates a separate snapshot Parquet file (if one doesn't exist yet)
3. All CRUD operations go to the snapshot file; the backing dataset is untouched

For stream models, all reads go directly to the backing dataset.

---

## Defining a Model

### 1. Write the class

```python
# models/student.py
from forge.model import forge_model, field_def, related

@forge_model(mode="snapshot", backing_dataset="students")
class Student:
    id:          str  = field_def(primary_key=True)
    name:        str  = field_def(display="Full Name")
    email:       str  = field_def(display="Email Address")
    major:       str
    enrolled_at: str
    status:      str
    grade_keys:  str  = field_def(display="Grade IDs")
```

The `backing_dataset` value must match the `name` field of a dataset entry in `forge.toml` (not the UUID — Forge looks it up by name).

### 2. Register in forge.toml

```toml
[[models]]
name   = "Student"
mode   = "snapshot"
module = "models.student"
class  = "Student"
```

### 3. Build

```bash
forge model build
```

This writes:
- `.forge/artifacts/Student.schema.json`
- `.forge/generated/python/student.py`
- `.forge/generated/typescript/Student.ts`
- Updates barrel exports in `__init__.py` and `index.ts`

---

## Field Definitions

Use `field_def()` to annotate a field with metadata beyond its Python type:

```python
from forge.model import field_def

id:    str   = field_def(primary_key=True)
score: float = field_def(display="Score (%)", display_hint="percent")
notes: str   = field_def(display="Notes", nullable=True)
```

`field_def()` parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `primary_key` | bool | Mark as the model's primary key (exactly one per model required) |
| `display` | str | Human-readable label shown in widgets |
| `display_hint` | str | Rendering hint for widgets (e.g. `"percent"`, `"currency"`) |
| `nullable` | bool | Whether the field can be null (inferred from `Optional[T]` annotation if not set) |

Fields declared without `field_def()` are inferred from their type annotation. `Optional[str]` → nullable string.

**Type mapping** (Python → Forge):

| Python | Forge type | TypeScript |
|--------|-----------|------------|
| `str` | `string` | `string` |
| `int` | `integer` | `number` |
| `float` | `float` | `number` |
| `bool` | `boolean` | `boolean` |
| `Optional[T]` | same type, nullable | `T \| undefined` |

---

## Exactly One Primary Key

Every model must declare exactly one `primary_key=True` field. The decorator validates this at import time and raises if zero or more than one is found.

For string PKs, the convention is `f"s{uuid.uuid4().hex[:6]}"` — a short prefixed hex string. For integer PKs, use auto-increment logic in your create endpoint.

---

## Relations

Relations express one-to-many links stored as JSON key lists in a string field:

```python
from forge.model import forge_model, field_def, related

@forge_model(mode="snapshot", backing_dataset="students")
class Student:
    id:         str = field_def(primary_key=True)
    name:       str
    grade_keys: str = field_def(display="Grade IDs")

    grades = related(target_model="Grade", via="grade_keys")
```

`related()` generates a method `student.grades(*, engine)` that:
1. Reads `self.grade_keys` as a JSON array of IDs
2. Fetches the Grade dataset
3. Filters to matching PKs
4. Returns a list of `Grade` instances

The `via` parameter is the field name on this model that holds the JSON key list. The target model class must also be `@forge_model`-decorated and imported before this method is called.

### Maintaining Relations in Endpoints

Relations are stored as JSON strings — you must update them manually when creating or deleting linked objects:

```python
import json

# Creating a grade linked to a student:
new_grade = Grade.create(id=f"g{uuid.uuid4().hex[:6]}", ...)
student = Student.get(student_id)
keys = json.loads(student.grade_keys or "[]")
keys.append(new_grade.id)
student.grade_keys = json.dumps(keys)  # dirty-tracked, flushed atomically

# Deleting a grade:
grade.remove()
keys = json.loads(student.grade_keys or "[]")
keys.remove(grade.id)
student.grade_keys = json.dumps(keys)
```

---

## Reading Data

These class methods are mixed in by the `@forge_model` decorator. Outside of an endpoint context you must supply `engine` explicitly; inside an endpoint the engine is injected from the request context.

```python
# All records
students = Student.all(engine=engine)

# Single record by PK
student = Student.get("s1a2b3", engine=engine)  # returns None if not found

# Batch fetch (preserves input order)
students = Student.get_many(["s1", "s2", "s3"], engine=engine)

# Equality filter
active = Student.filter(engine=engine, status="active", major="CS")
```

---

## Writing Data (Snapshot Models Only)

### create

```python
student = Student.create(
    engine=engine,
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

### update (via setattr)

```python
student = Student.get(student_id, engine=engine)
student.name  = "Alice Johnson"
student.email = "alicej@example.com"
# mutations are dirty-tracked; flushed atomically when the endpoint returns
```

You can also call `.update()` explicitly if you are outside an endpoint context:

```python
student.update(engine=engine, name="Alice Johnson")
```

### remove

```python
student = Student.get(student_id, engine=engine)
student.remove(engine=engine)
```

---

## Unit of Work and Dirty Tracking

Inside an endpoint call, every `setattr` on a managed model instance is automatically tracked. When the endpoint returns successfully, all pending creates, updates, and deletes are flushed to storage in a single atomic operation.

If the endpoint raises, all pending mutations are discarded (rolled back) — storage is unchanged.

You do not need to call flush or commit explicitly. The `@action_endpoint` runtime handles this for you.

---

## Stream Models

Stream models are read-only views of pipeline output:

```python
@forge_model(mode="stream", backing_dataset="stock_prices")
class StockPrice:
    symbol: str  = field_def(primary_key=True)
    ts:     str
    close:  float
    volume: int
```

Stream models support only `all()`, `get()`, `get_many()`, and `filter()`. Calling `create()` or `remove()` on a stream model raises an error.

---

## Schema Artifact

`forge model build` writes `.forge/artifacts/<Name>.schema.json`. This file is the authoritative schema for code generation and is read by the TypeScript runtime:

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

The schema is rebuilt from the **live dataset** on each `forge model build` run. If the dataset schema changes (new column from a pipeline), rebuild to pick it up.

---

## Reinitializing a Snapshot

If you need to reset a snapshot model back to the state of its backing dataset (e.g. after bulk bad writes in development):

```bash
forge model reinitialize Student
```

This drops the snapshot Parquet file and creates a fresh copy from the backing dataset. **All mutations are lost.**

---

## Generated Python SDK

The generated file at `.forge/generated/python/student.py` contains:

```python
@dataclass
class Student:
    id: str
    name: str
    ...

    @classmethod
    def _from_row(cls, row: dict) -> "Student": ...

    def _to_dict(self) -> dict: ...

class StudentSet:
    @classmethod
    def _load(cls, *, engine) -> "StudentSet": ...

    # snapshot only:
    @classmethod
    def create(cls, *, engine, **kwargs) -> Student: ...
    def update(self, *, engine, **kwargs) -> Student: ...
    def delete(self, *, engine, pk_value: str): ...
```

Import this in endpoint code or in UI-layer scripts for type-safe access.

---

## Generated TypeScript SDK

The generated file at `.forge/generated/typescript/Student.ts` contains:

```typescript
export interface Student {
  id: string;
  name: string;
  // ...
}

export const StudentSchema: ForgeSchema = { ... };

export async function loadStudentSet(
  options?: { limit?: number; offset?: number }
): Promise<ForgeObjectSet<Student>> { ... }
```

Import this in your React app — never write `fetch` calls for object data directly.

---

## Isolation Rules

The Model layer must **never**:

- Import `@action_endpoint` or `@computed_attribute_endpoint` decorators
- Import anything from `packages/forge-ts` or any React/widget code
- Construct HTTP requests
- Reference UI concerns (display state, routing, component lifecycle)

Model classes may be imported by the Control layer. The Control layer may not be imported by the Model layer.

---

## Full Example: Grade Model

```python
# models/grade.py
from forge.model import forge_model, field_def

@forge_model(mode="snapshot", backing_dataset="grades")
class Grade:
    id:         str   = field_def(primary_key=True)
    student_id: str   = field_def(display="Student ID")
    course:     str   = field_def(display="Course")
    semester:   str   = field_def(display="Semester")
    grade:      str   = field_def(display="Grade")
    credits:    int   = field_def(display="Credits")
```

```toml
[[models]]
name   = "Grade"
mode   = "snapshot"
module = "models.grade"
class  = "Grade"
```

After `forge model build`, endpoints can do:

```python
from .forge.generated.python import Grade

grade = Grade.get("g1a2b3")
grade.grade = "A"   # dirty-tracked, flushed atomically
```
