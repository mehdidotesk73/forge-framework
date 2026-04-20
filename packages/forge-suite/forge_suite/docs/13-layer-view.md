# Forge — View Layer

## What the View Layer Does

The View layer renders data and captures user interactions using React. It is the only layer the end user sees. View code imports the generated TypeScript SDK and endpoint UUID constants — nothing else from the backend.

The view layer has no knowledge of pipelines, model internals, or Python. It receives data by calling generated loader functions, sends mutations through `callEndpoint()`, and wires everything together using Forge widgets from `@forge-suite/ts`.

**Three things the view layer does:**

1. **Load data** — fetch rows with `fetchObjectSet()`, then wrap into a typed `ForgeObjectSet<T>` via `load<Name>Set(rows)`
2. **Display data** — pass the object set to widgets (`ObjectTable`, `Chart`, `MetricTile`, etc.)
3. **Mutate data** — invoke endpoints via `callEndpoint()` or `<Form>` widget; refresh on success

---

## Setup

### Install the widget library

In a Forge project created by `forge app create`, `@forge-suite/ts` is already wired. For a standalone project:

```bash
npm install @forge-suite/ts
```

### Configure the base URL

By default, the Forge client targets `window.location.origin`. When using the Vite dev server, all `/api/*` and `/endpoints/*` requests are automatically proxied to the Forge backend — no configuration needed.

Only call `configureForge` when you need to override the target explicitly:

```typescript
import { configureForge } from "@forge-suite/ts";

configureForge({ baseUrl: "https://my-server.example.com" });
```

---

## Loading Data

Loading data requires two steps:

1. **Fetch rows over HTTP** — use `fetchObjectSet<T>()` from `@forge-suite/ts`
2. **Wrap into a typed set** — use the generated `load<Name>Set(rows)` function

### Step 1 — `fetchObjectSet`

```typescript
import { fetchObjectSet } from "@forge-suite/ts";

const { rows, total } = await fetchObjectSet<Student>("Student", { limit: 100, offset: 0 });
// rows   → Student[]
// total  → number (full row count, before pagination)
```

`fetchObjectSet` makes the HTTP GET request to `/api/objects/{type}`. It is the only approved way to fetch object rows — never write raw `fetch()` or `axios` calls for Forge data.

### Step 2 — generated `load<Name>Set`

`forge model build` generates a typed `load<Name>Set(rows)` function for every model. It is **synchronous** — it wraps already-fetched rows into a `ForgeObjectSet<T>`:

```typescript
import { loadStudentSet } from "../.forge/generated/typescript/Student";

const studentSet = loadStudentSet(rows);
// studentSet.rows    → Student[]
// studentSet.schema  → ForgeSchema
// studentSet.total   → number
// studentSet.mode    → "snapshot" | "stream"
```

### Complete pattern

```typescript
import { fetchObjectSet } from "@forge-suite/ts";
import { loadStudentSet } from "../.forge/generated/typescript/Student";

const { rows } = await fetchObjectSet<Student>("Student", { limit: 100, offset: 0 });
const studentSet = loadStudentSet(rows);
```

### Pagination

```typescript
const { rows: page1Rows, total } = await fetchObjectSet<Student>("Student", { limit: 50, offset: 0 });
const { rows: page2Rows }        = await fetchObjectSet<Student>("Student", { limit: 50, offset: 50 });
// total gives the full row count
```

---

## Displaying Data

### ObjectTable

The primary widget for tabular data. Renders column headers, sortable rows, computed columns, and row interactions.

```tsx
import { ObjectTable } from "@forge-suite/ts";

<ObjectTable objectSet={studentSet} />
```

Click a column header to sort; click again to reverse. The sort indicator (`↑` / `↓`) appears in the header.

#### Row interactions

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{
    mode: "single",
    onClick: {
      kind: "ui",
      handler: (student) => setSelected(student),
    },
    contextMenu: [
      {
        label: "Edit",
        action: { kind: "ui", handler: (s) => openEditModal(s) },
      },
      {
        label: "Delete",
        action: { kind: "ui", handler: (s) => handleDelete(s.id) },
      },
    ],
  }}
/>
```

Right-click any row to open the context menu. Escape or clicking outside closes it.

#### Computed columns

Computed column endpoints are called automatically with the visible rows' PKs:

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

When `localState` changes, any columns with a matching `stateKey` binding re-fetch automatically.

---

### ObjectCard

For detail views or card-grid layouts:

```tsx
import { ObjectCard } from "@forge-suite/ts";

<ObjectCard
  object={student}
  schema={studentSet.schema}
  layout="detail"             // "default" | "compact" | "detail"
  interaction={{
    onClick: { kind: "ui", handler: (s) => openDetail(s) },
  }}
/>
```

---

### MetricTile

Aggregate a numeric field or display a static value:

```tsx
import { MetricTile } from "@forge-suite/ts";

// Computed from an object set
<MetricTile
  label="Total Credits"
  objectSet={studentSet}
  field="credits"
  aggregation="sum"       // "count" | "sum" | "avg" | "min" | "max"
  format="number"         // "number" | "currency" | "percent"
/>

// Static value
<MetricTile label="Active Cohort" value={42} format="number" />
```

---

### Chart

Line, bar, or area chart from an object set:

```tsx
import { Chart } from "@forge-suite/ts";

<Chart
  objectSet={priceSet}
  chartType="line"          // "line" | "bar" | "area"
  xField="ts"
  series={[
    { field: "close",  label: "Close Price", color: "#6366f1" },
    { field: "volume", label: "Volume" },
  ]}
  height={300}
/>
```

The x-axis uses `xField`; each entry in `series` maps to one line, bar, or area.

---

### FilterBar

Client-side text filtering over an object set. Filters are applied as AND conditions with case-insensitive substring matching:

```tsx
import { FilterBar, applyFilterState } from "@forge-suite/ts";

const [filters, setFilters] = useState({});
const visibleRows = applyFilterState(studentSet.rows, filters);

<FilterBar
  schema={studentSet.schema}
  fields={["name", "major", "status"]}
  onChange={setFilters}
/>
<ObjectTable objectSet={{ ...studentSet, rows: visibleRows }} />
```

`applyFilterState` is a pure function — pass its result to any widget that accepts rows.

---

## Calling Endpoints

### callEndpoint

Invoke any action endpoint by UUID:

```typescript
import { callEndpoint } from "@forge-suite/ts";

const result = await callEndpoint<Student>(
  "11111111-0000-0000-0000-000000000001",
  { name: "Alice", email: "alice@example.com", major: "CS" }
);
```

Always reference endpoints by UUID string constant. Never construct `/endpoints/...` URLs manually.

### Form widget (auto-rendered)

`<Form>` fetches the endpoint descriptor and renders typed inputs automatically — no manual form building:

```tsx
import { Form } from "@forge-suite/ts";

<Form
  endpointId="11111111-0000-0000-0000-000000000001"
  prefill={{ major: "Computer Science" }}
  submitLabel="Create Student"
  onSuccess={() => { refetch(); closeModal(); }}
  onError={(err) => console.error(err)}
/>
```

**Param type → input widget mapping:**

| Param type | Widget rendered |
|------------|----------------|
| `string` | TextInput |
| `integer` | NumberInput |
| `float` | NumberInput |
| `boolean` | Toggle |

`prefill` sets initial values; a key matching a param name pre-populates that field.

---

## Input Widgets

Use standalone input widgets when `<Form>` auto-rendering is not sufficient:

```tsx
import {
  TextInput, NumberInput, Toggle,
  Selector, MultiSelector, DateInput,
} from "@forge-suite/ts";

<TextInput
  value={name}
  onChange={setName}
  label="Full Name"
  placeholder="Enter name..."
/>

<NumberInput
  value={credits}
  onChange={setCredits}
  min={1}
  max={6}
  step={1}
  label="Credits"
/>

<Toggle
  checked={active}
  onChange={setActive}
  label="Active"
/>

<Selector
  value={major}
  options={[
    { value: "cs",   label: "Computer Science" },
    { value: "math", label: "Mathematics" },
  ]}
  onChange={setMajor}
  label="Major"
  placeholder="Select major..."
/>

<MultiSelector
  value={selectedSemesters}
  options={semesterOptions}
  onChange={setSelectedSemesters}
  label="Semesters"
/>

<DateInput
  value={enrolledAt}
  onChange={setEnrolledAt}
  label="Enrolled At"
/>
```

---

## File Upload

Upload a CSV, Parquet, or JSON file as a new dataset:

```tsx
import { FileUpload } from "@forge-suite/ts";

<FileUpload
  label="Upload Roster"
  datasetName="student_roster"
  onSuccess={({ id }) => console.log("Dataset ID:", id)}
  onError={(err) => console.error(err)}
/>
```

POSTs to `/api/datasets/upload`. `onSuccess` receives `{ id }` — the new dataset UUID.

---

## Layout Widgets

### Container

Flex row or CSS grid layout:

```tsx
import { Container } from "@forge-suite/ts";

// Flex row
<Container layout="flex" direction="row" gap={16} padding={24}>
  <MetricTile ... />
  <MetricTile ... />
</Container>

// CSS grid
<Container layout="grid" columns={3} gap={16} padding={24}>
  <ObjectCard ... />
  <ObjectCard ... />
  <ObjectCard ... />
</Container>
```

### Navbar

```tsx
import { Navbar } from "@forge-suite/ts";

<Navbar
  title="Student Manager"
  items={[
    { label: "Students", href: "/students", active: true },
    { label: "Reports",  href: "/reports" },
    { label: "Settings", onClick: () => openSettings() },
  ]}
  rightContent={<span>{user.email}</span>}
/>
```

### Modal

Portalled to `document.body`. Escape key and overlay click close the modal:

```tsx
import { Modal } from "@forge-suite/ts";

<Modal
  open={showCreate}
  onClose={() => setShowCreate(false)}
  title="Add Student"
  size="md"               // "sm" | "md" | "lg" | "xl"
>
  <Form
    endpointId={CREATE_STUDENT_ID}
    onSuccess={() => { refetch(); setShowCreate(false); }}
  />
</Modal>
```

### ButtonGroup

```tsx
import { ButtonGroup } from "@forge-suite/ts";

<ButtonGroup
  buttons={[
    {
      label: "Edit",
      variant: "secondary",
      action: { kind: "ui", handler: () => openEdit(student) },
    },
    {
      label: "Delete",
      variant: "danger",
      action: { kind: "ui", handler: () => handleDelete(student.id) },
    },
  ]}
  renderMode="inline"       // "inline" | "menu"
  size="medium"
/>
```

`renderMode="menu"` collapses all buttons into a single `⋮ Actions` dropdown.

---

## Triggering Pipelines

```typescript
import { triggerPipeline } from "@forge-suite/ts";

await triggerPipeline("normalize_students");
```

POSTs to `/api/pipelines/{name}/run`. Useful for "Refresh Data" buttons that re-pull from an external source.

---

## ForgeAction

Actions used in `interaction`, `ButtonGroup`, and context menus share the `ForgeAction` type:

```typescript
// Local JavaScript handler
const uiAction: ForgeAction = {
  kind: "ui",
  handler: (item) => {
    setSelected(item);
    openModal();
  },
};

// Server-side endpoint call
const serverAction: ForgeAction = {
  kind: "server",
  endpointId: "11111111-0000-0000-0000-000000000001",
  params: { status: "graduated" },
};
```

---

## State Binding for Computed Columns

Connect computed column params to React state so they re-fetch when filters or selectors change:

```tsx
const [timeframe, setTimeframe] = useState("all");

<Selector
  value={timeframe}
  options={[
    { value: "all",   label: "All Time" },
    { value: "F2024", label: "Fall 2024" },
  ]}
  onChange={setTimeframe}
  label="Timeframe"
/>

<ObjectTable
  objectSet={studentSet}
  computedColumns={[{
    endpointId: COMPUTE_METRICS_ID,
    columns: ["gpa", "letter_rank"],
    params: {
      timeframe: { stateKey: "timeframe" },
    },
  }]}
  localState={{ timeframe }}
/>
```

When `timeframe` changes, `ObjectTable` detects the resolved value differs and re-calls the endpoint.

---

## Isolation Rules

The View layer must **never**:

- Write raw `fetch()` or `axios` calls for Forge data — use `fetchObjectSet()`, `load<Name>Set(rows)`, `callEndpoint()`, `triggerPipeline()`
- Construct `/api/...` or `/endpoints/...` URLs directly
- Import from Python modules or reference Python class names
- Reference dataset UUIDs (reference endpoint UUIDs and model type names only)
- Import `@forge_model`, `@action_endpoint`, or any symbol from `forge.model` or `forge.control`

---

## Key TypeScript Types

```typescript
// From @forge-suite/ts

interface ForgeObjectSet<T> {
  rows:      T[];
  schema:    ForgeSchema;
  datasetId: string;
  mode:      "snapshot" | "stream";
  total:     number;
}

interface ForgeSchema {
  fields:      Record<string, FieldDefinition>;
  primary_key?: string;
}

interface FieldDefinition {
  type:          "string" | "integer" | "float" | "boolean" | "datetime";
  nullable:      boolean;
  display?:      string;
  display_hint?: string;
}

type ForgeAction =
  | { kind: "ui";     handler: (item?: any) => void | Promise<void> }
  | { kind: "server"; endpointId: string; params?: Record<string, unknown> };

interface StateBinding {
  stateKey: string;
}

interface InteractionConfig {
  mode?:        "single" | "multi";
  onClick?:     ForgeAction;
  contextMenu?: Array<{ label: string; action: ForgeAction }>;
}

interface ComputedColumnConfig {
  endpointId: string;
  columns:    string[];
  params?:    Record<string, unknown | StateBinding>;
}
```
