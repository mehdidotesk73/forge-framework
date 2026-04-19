# Forge — View Layer Developer Guide

## Purpose

The View layer renders data and captures user interactions using React. It imports the generated TypeScript SDK and endpoint IDs — nothing else from the backend. It never writes `fetch` calls, never constructs HTTP requests, and never imports Python model classes.

The view layer is a standard React app. Forge supplies a widget library (`@forge-framework/ts`) and a runtime client that handles all HTTP communication with the Forge server.

---

## Setup

### Install the widget library

```bash
npm install @forge-framework/ts
# or, in a monorepo workspace, the package is already available as @forge-framework/ts
```

### Configure the base URL

In a browser, the client defaults to `window.location.origin`. When the app is served via the Vite dev server (as Forge Suite does), all `/api/*` and `/endpoints/*` requests are automatically proxied to the project backend — no configuration needed.

Only call `configureForge` if you need to override the target (e.g., pointing directly at a remote backend):

```typescript
import { configureForge } from "@forge-framework/ts";

configureForge({ baseUrl: "https://my-server.example.com" });
```

---

## Loading Data

### loadStudentSet

Import the generated loader from the generated SDK:

```typescript
import { loadStudentSet } from "../.forge/generated/typescript/Student";

const studentSet = await loadStudentSet({ limit: 100, offset: 0 });
// studentSet: ForgeObjectSet<Student>
// studentSet.rows    → Student[]
// studentSet.schema  → ForgeSchema
// studentSet.total   → number (total count in dataset)
// studentSet.mode    → "snapshot" | "stream"
```

The generated `load<Name>Set()` function calls `GET /api/objects/<Name>` internally. You never write this fetch yourself.

### Pagination

```typescript
const page1 = await loadStudentSet({ limit: 50, offset: 0 });
const page2 = await loadStudentSet({ limit: 50, offset: 50 });
```

`total` tells you how many records exist; use it to compute page count.

---

## Displaying Data

### ObjectTable

The primary widget for displaying a list of objects.

```tsx
import { ObjectTable } from "@forge-framework/ts";

<ObjectTable
  objectSet={studentSet}
  className="my-table"
/>
```

**Sorting:** Click any column header to sort. Click again to reverse. The sort indicator (`↑` / `↓`) appears in the header.

**Density:** Controlled via CSS class — `forge-table-compact` or `forge-table-comfortable`.

#### Interactions

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{
    mode: "single",                           // or "multi" for multi-select
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

Right-click any row to open the context menu. Escape or click outside to close.

#### Computed Columns

```tsx
<ObjectTable
  objectSet={studentSet}
  computedColumns={[
    {
      endpointId: "22222222-0000-0000-0000-000000000002",
      columns: ["gpa", "letter_rank"],
      params: {
        timeframe: { stateKey: "selectedTimeframe" },
      },
    },
  ]}
  localState={{ selectedTimeframe: selectedTimeframe }}
/>
```

`ObjectTable` calls the computed column endpoint automatically, passing the visible rows' primary keys plus any resolved `params`. State bindings (`{ stateKey: "..." }`) are resolved from `localState` at fetch time — when `localState` changes, the columns re-fetch.

### ObjectCard

For detail views or card-grid layouts:

```tsx
import { ObjectCard } from "@forge-framework/ts";

<ObjectCard
  object={student}
  schema={studentSet.schema}
  layout="detail"         // "default" | "compact" | "detail"
  interaction={{
    onClick: { kind: "ui", handler: (s) => openDetail(s) }
  }}
/>
```

### MetricTile

Aggregate a numeric field from an object set:

```tsx
import { MetricTile } from "@forge-framework/ts";

<MetricTile
  label="Total Students"
  objectSet={studentSet}
  field="credits"
  aggregation="sum"       // "count" | "sum" | "avg" | "min" | "max"
  format="number"         // "number" | "currency" | "percent"
/>

// Or a static value:
<MetricTile label="Active Cohort" value={42} format="number" />
```

### Chart

Line, bar, or area chart from an object set:

```tsx
import { Chart } from "@forge-framework/ts";

<Chart
  objectSet={priceSet}
  chartType="line"          // "line" | "bar" | "area"
  xField="ts"
  series={[
    { field: "close", label: "Close Price", color: "#6366f1" },
    { field: "volume", label: "Volume" },
  ]}
  height={300}
/>
```

The x-axis uses `xField`; each `series` entry maps to one line/bar/area.

### FilterBar

Client-side text filtering over an object set:

```tsx
import { FilterBar, applyFilterState } from "@forge-framework/ts";

const [filters, setFilters] = useState({});
const visible = applyFilterState(studentSet.rows, filters);

<FilterBar
  schema={studentSet.schema}
  fields={["name", "major", "status"]}   // which fields to show filter inputs for
  onChange={setFilters}
/>
<ObjectTable objectSet={{ ...studentSet, rows: visible }} />
```

`applyFilterState` does case-insensitive substring matching. All filters are applied as AND conditions.

---

## Calling Endpoints

### callEndpoint

```typescript
import { callEndpoint } from "@forge-framework/ts";

const result = await callEndpoint<Student>(
  "11111111-0000-0000-0000-000000000001",   // endpoint UUID — never the name
  { name: "Alice", email: "alice@example.com", major: "CS" }
);
```

Returns `Promise<T>` where T is the endpoint's return type. Throws on non-2xx responses.

### Form widget (auto-rendered)

The `Form` widget fetches the endpoint descriptor and renders an appropriate input for each param automatically. No manual form building required.

```tsx
import { Form } from "@forge-framework/ts";

<Form
  endpointId="11111111-0000-0000-0000-000000000001"
  prefill={{ major: "Computer Science" }}
  submitLabel="Create Student"
  onSuccess={() => { refetch(); closeModal(); }}
  onError={(err) => console.error(err)}
/>
```

**Param → input widget mapping:**

| Param type | Widget |
|------------|--------|
| `string` | TextInput |
| `integer` | NumberInput |
| `float` | NumberInput |
| `boolean` | Toggle |

`prefill` sets initial values. If a key matches a param name, that field is pre-populated.

---

## Input Widgets (standalone use)

Use these when you need custom form UIs beyond what `<Form>` auto-renders:

```tsx
import { TextInput, NumberInput, Toggle, Selector, MultiSelector, DateInput } from "@forge-framework/ts";

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
    { value: "cs", label: "Computer Science" },
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

```tsx
import { FileUpload } from "@forge-framework/ts";

<FileUpload
  label="Upload Roster"
  datasetName="student_roster"
  onSuccess={({ id }) => console.log("Dataset ID:", id)}
  onError={(err) => console.error(err)}
/>
```

Accepts `.csv`, `.parquet`, `.json`. POSTs to `/api/datasets/upload`. Returns `{id}` — the new dataset UUID.

---

## Layout Widgets

### Container

```tsx
import { Container } from "@forge-framework/ts";

// Flex row
<Container layout="flex" direction="row" gap={16} padding={24}>
  <MetricTile ... />
  <MetricTile ... />
</Container>

// CSS Grid
<Container layout="grid" columns={3} gap={16} padding={24}>
  <ObjectCard ... />
  <ObjectCard ... />
  <ObjectCard ... />
</Container>
```

### Navbar

```tsx
import { Navbar } from "@forge-framework/ts";

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

```tsx
import { Modal } from "@forge-framework/ts";

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

Portalled to `document.body`. Escape key and overlay click close the modal.

### ButtonGroup

```tsx
import { ButtonGroup } from "@forge-framework/ts";

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
  onAction={(action) => { /* optional global handler */ }}
/>
```

`renderMode="menu"` collapses all buttons into a single `⋮ Actions` dropdown.

---

## Triggering Pipelines

```typescript
import { triggerPipeline } from "@forge-framework/ts";

await triggerPipeline("normalize_students");
```

POSTs to `/api/pipelines/{name}/run`. Useful for "Refresh Data" buttons.

---

## ForgeAction Types

Actions in interactions, button groups, and context menus are typed as `ForgeAction`:

```typescript
// Local JavaScript handler
const uiAction: ForgeAction = {
  kind: "ui",
  handler: (item) => {
    setSelected(item);
    openModal();
  },
};

// Server endpoint call
const serverAction: ForgeAction = {
  kind: "server",
  endpointId: "11111111-0000-0000-0000-000000000001",
  params: { status: "graduated" },
};
```

---

## State Binding for Computed Columns

State bindings connect ObjectTable computed columns to React state, so computed values re-fetch when filters or selectors change:

```tsx
const [timeframe, setTimeframe] = useState("all");

<Selector
  value={timeframe}
  options={[
    { value: "all",  label: "All Time" },
    { value: "F2024",label: "Fall 2024" },
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
      timeframe: { stateKey: "timeframe" },   // resolved from localState
    },
  }]}
  localState={{ timeframe }}
/>
```

When `timeframe` changes, `ObjectTable` detects the stateKey resolution differs and re-calls the endpoint.

---

## Adding a New Widget

1. Add the component to `packages/forge-ts/src/widgets/<WidgetName>.tsx`
2. Export it from `packages/forge-ts/src/widgets/index.ts`
3. Re-export from `packages/forge-ts/src/index.ts`
4. Rebuild: `cd packages/forge-ts && npm run build`

Only add a new widget if existing widgets cannot be configured to cover the need.

---

## Isolation Rules

The View layer must **never**:

- Write `fetch()`, `axios`, or any raw HTTP call for Forge data (use `loadStudentSet()`, `callEndpoint()`, etc.)
- Import Python files or classes
- Construct `/api/...` URLs directly (use the runtime client functions)
- Import from `forge.model`, `forge.control`, or any Python module
- Reference dataset UUIDs (reference endpoint UUIDs and model names only)

---

## Key TypeScript Types

```typescript
// From @forge-framework/ts

interface ForgeObjectSet<T> {
  rows: T[];
  schema: ForgeSchema;
  datasetId: string;
  mode: "snapshot" | "stream";
  total: number;
}

interface ForgeSchema {
  fields: Record<string, FieldDefinition>;
  primary_key?: string;
}

interface FieldDefinition {
  type: "string" | "integer" | "float" | "boolean" | "datetime";
  nullable: boolean;
  display?: string;
  display_hint?: string;
}

type ForgeAction =
  | { kind: "ui";     handler: (item?: any) => void | Promise<void> }
  | { kind: "server"; endpointId: string; params?: Record<string, unknown> };

interface StateBinding {
  stateKey: string;
}

interface InteractionConfig {
  mode?: "single" | "multi";
  onClick?: ForgeAction;
  contextMenu?: Array<{ label: string; action: ForgeAction }>;
}

interface ComputedColumnConfig {
  endpointId: string;
  columns: string[];
  params?: Record<string, unknown | StateBinding>;
}
```
