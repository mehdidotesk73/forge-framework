# Forge — Widget Reference

All widgets are exported from `@forge-suite/ts`. Install once:

```bash
npm install @forge-suite/ts
```

Import any widget by name:

```typescript
import { ObjectTable, Chart, MetricTile, Form, Modal } from "@forge-suite/ts";
```

---

## Data Widgets

### ObjectTable

The primary widget for tabular data. Renders column headers, sortable rows, computed columns, and row interactions.

```tsx
import { ObjectTable } from "@forge-suite/ts";

<ObjectTable objectSet={studentSet} />
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `objectSet` | `ForgeObjectSet<T>` | Data and schema |
| `interaction` | `InteractionConfig<T>` | Click, selection, context menu, display options |
| `computedColumns` | `ComputedAttributeAttachment[]` | Server-computed column configs |
| `localState` | `Record<string, unknown>` | State values for `StateBinding` resolution |
| `renderCell` | `(field, value, row) => ReactNode` | Custom cell renderer |
| `className` | `string` | Extra CSS class |
| `style` | `CSSProperties` | Inline styles |

#### Sorting

Click a column header to sort; click again to reverse. Set initial sort with `interaction.sortField` and `interaction.sortOrder`:

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{
    sortField: "enrolled_at",
    sortOrder: "desc",
  }}
/>
```

#### Row selection

```tsx
const [selected, setSelected] = useState<Student[]>([]);

<ObjectTable
  objectSet={studentSet}
  interaction={{
    selectable: "multi",          // "none" | "single" | "multi"
    onSelectionChange: setSelected,
  }}
/>
```

Ctrl+click and Shift+click work for multi-select.

#### Click and double-click handlers

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{
    selectable: "single",
    onClick: { kind: "ui", handler: (student) => setSelected(student) },
    onDoubleClick: { kind: "ui", handler: (student) => openDetail(student) },
  }}
/>
```

#### Context menu

Pass a static array or a function for per-row menus:

```tsx
// Static menu
<ObjectTable
  objectSet={studentSet}
  interaction={{
    contextMenu: [
      { label: "Edit",   action: { kind: "ui", handler: (s) => openEdit(s) } },
      { label: "Delete", action: { kind: "ui", handler: (s) => handleDelete(s.id) } },
    ],
  }}
/>

// Dynamic per-row menu
<ObjectTable
  objectSet={studentSet}
  interaction={{
    contextMenu: (student) => [
      { label: "Edit", action: { kind: "ui", handler: () => openEdit(student) } },
      ...(student.status === "active"
        ? [{ label: "Graduate", action: { kind: "ui", handler: () => graduate(student.id) } }]
        : []),
    ],
  }}
/>
```

Right-click any row to open the context menu. Escape or clicking outside closes it.

#### Visible fields

Override which columns are shown and their order:

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{ visibleFields: ["name", "major", "status", "enrolled_at"] }}
/>
```

#### Density

```tsx
<ObjectTable
  objectSet={studentSet}
  interaction={{ density: "compact" }}   // "compact" | "comfortable"
/>
```

#### Custom cell rendering

```tsx
<ObjectTable
  objectSet={studentSet}
  renderCell={(field, value, row) => {
    if (field === "status") {
      return <span className={`badge badge-${value}`}>{value}</span>;
    }
    return undefined;   // fall back to default rendering
  }}
/>
```

Return `undefined` to use the default renderer for that field.

#### Computed columns

Computed column endpoints are called automatically with the visible rows' PKs:

```tsx
import { bindState } from "@forge-suite/ts";

const [timeframe, setTimeframe] = useState("all");

<ObjectTable
  objectSet={studentSet}
  computedColumns={[
    {
      endpointId: "22222222-0000-0000-0000-000000000002",
      params: {
        timeframe: bindState("timeframe"),   // re-fetches when timeframe changes
      },
    },
  ]}
  localState={{ timeframe }}
/>
```

When the `timeframe` state value changes, `ObjectTable` detects the resolved value differs and re-calls the endpoint. Use `bindState(key)` to create a `StateBinding` that reads from `localState`.

---

### ObjectCard

Detail views or card-grid layouts:

```tsx
import { ObjectCard } from "@forge-suite/ts";

<ObjectCard
  object={student}
  schema={studentSet.schema}
  layout="detail"             // "default" | "compact" | "detail"
  interaction={{
    onClick: { kind: "ui", handler: (s) => openDetail(s) },
    visibleFields: ["name", "email", "major", "status"],
  }}
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `object` | `T` | The record to display |
| `schema` | `ForgeSchema` | Schema from the object set |
| `layout` | `"default" \| "compact" \| "detail"` | Display density |
| `interaction` | `InteractionConfig<T>` | Click handler and display options |
| `className` | `string` | Extra CSS class |

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

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `label` | `string` | Display label |
| `value` | `number` | Static value (mutually exclusive with `objectSet` mode) |
| `objectSet` | `ForgeObjectSet<T>` | Source data for aggregation |
| `field` | `string` | Field to aggregate |
| `aggregation` | `"count" \| "sum" \| "avg" \| "min" \| "max"` | Aggregation function |
| `format` | `"number" \| "currency" \| "percent"` | Display format |
| `className` | `string` | Extra CSS class |

---

### Chart

Line, bar, or area chart from an object set:

```tsx
import { Chart } from "@forge-suite/ts";

<Chart
  objectSet={priceSet}
  chartType="line"          // "line" | "bar" | "area" — default "line"
  xField="ts"
  series={[
    { field: "close",  label: "Close Price", color: "#6366f1" },
    { field: "volume", label: "Volume" },
  ]}
  height={300}
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `objectSet` | `ForgeObjectSet<T>` | Data source |
| `chartType` | `"line" \| "bar" \| "area"` | Chart type; default `"line"` |
| `xField` | `string` | Field for the x-axis |
| `series` | `ChartSeries[]` | One entry per line/bar/area |
| `height` | `number` | Height in pixels; default `300` |
| `className` | `string` | Extra CSS class |

`ChartSeries = { field: string; label?: string; color?: string }`. Default colors cycle through `["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"]`.

---

### FilterBar

Client-side text filtering over an object set:

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

Filters are applied as AND conditions with case-insensitive substring matching. `applyFilterState` is a pure function — pass its result to any widget that accepts rows.

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `schema` | `ForgeSchema` | Schema from the object set |
| `fields` | `string[]` | Fields to expose as filter inputs |
| `onChange` | `(state: FilterState) => void` | Called on every filter change |
| `className` | `string` | Extra CSS class |

---

## Mutation Widgets

### Form

Fetches the endpoint descriptor and renders typed inputs automatically — no manual form building:

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

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `endpointId` | `string` | UUID of the action endpoint |
| `prefill` | `Record<string, unknown>` | Initial field values |
| `submitLabel` | `string` | Button label; default `"Submit"` |
| `onSuccess` | `(result: unknown) => void` | Called with the endpoint response |
| `onError` | `(err: unknown) => void` | Called on failure |
| `className` | `string` | Extra CSS class |

---

## Input Widgets

Use standalone input widgets when `<Form>` auto-rendering is not sufficient.

### TextInput

```tsx
import { TextInput } from "@forge-suite/ts";

<TextInput
  value={name}
  onChange={setName}
  label="Full Name"
  placeholder="Enter name..."
/>
```

**Props:** `value`, `onChange`, `placeholder?`, `label?`, `disabled?`, `className?`

---

### TextArea

```tsx
import { TextArea } from "@forge-suite/ts";

<TextArea
  value={notes}
  onChange={setNotes}
  label="Notes"
  placeholder="Enter notes..."
  rows={4}
/>
```

**Props:** `value`, `onChange`, `placeholder?`, `label?`, `rows?`, `disabled?`, `className?`, `style?`

---

### NumberInput

```tsx
import { NumberInput } from "@forge-suite/ts";

<NumberInput
  value={credits}
  onChange={setCredits}
  min={1}
  max={6}
  step={1}
  label="Credits"
/>
```

**Props:** `value`, `onChange`, `min?`, `max?`, `step?`, `label?`, `className?`

---

### DateInput

```tsx
import { DateInput } from "@forge-suite/ts";

<DateInput
  value={enrolledAt}
  onChange={setEnrolledAt}
  label="Enrolled At"
/>
```

Value is a date string in `YYYY-MM-DD` format.

**Props:** `value: string`, `onChange`, `label?`, `className?`

---

### Toggle

```tsx
import { Toggle } from "@forge-suite/ts";

<Toggle
  checked={active}
  onChange={setActive}
  label="Active"
/>
```

**Props:** `checked`, `onChange`, `label?`, `className?`

---

### Selector

Single-value dropdown:

```tsx
import { Selector } from "@forge-suite/ts";

<Selector
  value={major}
  options={[
    { value: "cs",   label: "Computer Science" },
    { value: "math", label: "Mathematics" },
  ]}
  onChange={setMajor}
  label="Major"
  placeholder="Select major..."
  size="md"              // "sm" | "md" | "lg"
  variant="default"      // "default" | "ghost"
/>
```

**Props:** `value`, `options`, `onChange`, `label?`, `placeholder?`, `size?`, `variant?`, `className?`

---

### MultiSelector

Multi-value checkbox dropdown:

```tsx
import { MultiSelector } from "@forge-suite/ts";

<MultiSelector
  value={selectedSemesters}
  options={semesterOptions}
  onChange={setSelectedSemesters}
  label="Semesters"
/>
```

**Props:** `value: string[]`, `options`, `onChange`, `label?`, `className?`

---

### RadioGroup

```tsx
import { RadioGroup } from "@forge-suite/ts";

<RadioGroup
  name="status"
  value={status}
  options={[
    { value: "active",    label: "Active" },
    { value: "graduated", label: "Graduated" },
    { value: "inactive",  label: "Inactive" },
  ]}
  onChange={setStatus}
  label="Status"
/>
```

The `name` prop is required (used for HTML radio group semantics).

**Props:** `value`, `options`, `onChange`, `name: string`, `label?`, `className?`

---

### FileUpload

Upload a CSV, Parquet, or JSON file as a new dataset:

```tsx
import { FileUpload } from "@forge-suite/ts";

<FileUpload
  label="Upload Roster"
  datasetName="student_roster"
  onSuccess={(datasetId) => console.log("Dataset ID:", datasetId)}
  onError={(err) => console.error(err)}
/>
```

POSTs to `/api/datasets/upload`. `onSuccess` receives the new dataset UUID as a plain string.

**Props:** `label?`, `datasetName?`, `onSuccess?: (datasetId: string) => void`, `onError?`, `className?`

---

## Layout Widgets

### Container

Flex row or CSS grid layout. Supports panel/card variants, pinned groups, dividers, and section titles.

**Flex row (default):**

```tsx
import { Container } from "@forge-suite/ts";

<Container direction="row" gap={16} padding={24}>
  <MetricTile label="Students" value={studentSet.total} />
  <MetricTile label="Courses"  value={courseSet.total} />
</Container>
```

**CSS grid:**

```tsx
<Container layout="grid" columns={3} gap={16} padding={24}>
  <ObjectCard object={s1} schema={schema} />
  <ObjectCard object={s2} schema={schema} />
  <ObjectCard object={s3} schema={schema} />
</Container>
```

**Column layout with title and card variant:**

```tsx
<Container
  direction="column"
  variant="card"
  title="Student Details"
  titleSize="md"
  gap={12}
  padding={20}
>
  <TextInput value={name} onChange={setName} label="Name" />
  <TextInput value={email} onChange={setEmail} label="Email" />
</Container>
```

**Pinned groups** — `startChildren` are left-aligned, `endChildren` right-aligned:

```tsx
<Container
  direction="row"
  startChildren={[<span key="title">Student Manager</span>]}
  endChildren={[
    <ButtonGroup key="actions" buttons={[...]} />,
  ]}
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `layout` | `"flex" \| "grid"` | Layout mode; default `"flex"` |
| `direction` | `"row" \| "column"` | Flex direction; default `"row"` |
| `columns` | `number` | Grid columns; default `2` |
| `gap` | `number \| string` | Gap between children |
| `padding` | `number \| string` | Inner padding |
| `size` | `number \| string` | Flex ratio (number) or fixed CSS size (string) |
| `alignItems` | `"left" \| "center" \| "right" \| "top" \| "bottom"` | Alignment |
| `separator` | `boolean` | Draws a border between children |
| `variant` | `"none" \| "panel" \| "card" \| "surface"` | Background fill style |
| `title` | `string` | Section title |
| `titleSize` | `"sm" \| "md" \| "lg"` | Title size |
| `titleIcon` | `string` | Icon string (emoji or text) |
| `titleIconColor` | `string` | CSS color for the icon |
| `children` | `ReactNode` | Shorthand for `startChildren` when not using pinned groups |
| `startChildren` | `ReactNode[]` | Left/top-pinned group |
| `endChildren` | `ReactNode[]` | Right/bottom-pinned group |
| `className` | `string` | Extra CSS class |
| `style` | `CSSProperties` | Inline styles |

---

### Navbar

```tsx
import { Navbar } from "@forge-suite/ts";

<Navbar
  title="Student Manager"
  items={[
    { label: "Students", href: "/students", active: true },
    { label: "Reports",  href: "/reports" },
    { label: "Settings", onClick: () => openSettings() },
    { label: "🏠",       icon: "🏠", href: "/" },
  ]}
  rightContent={<span>{user.email}</span>}
/>
```

**Vertical sidebar navigation:**

```tsx
<Navbar
  title="Suite"
  orientation="vertical"
  size="sm"
  items={[
    { label: "Pipelines", href: "/pipelines" },
    { label: "Models",    href: "/models" },
    { label: "Endpoints", href: "/endpoints" },
  ]}
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `title` | `string` | App/section title |
| `items` | `NavItem[]` | Navigation items |
| `orientation` | `"horizontal" \| "vertical"` | Layout; default `"horizontal"` |
| `size` | `"sm" \| "md" \| "lg"` | Font/spacing size; default `"md"` |
| `rightContent` | `ReactNode` | Content pinned to the trailing edge |
| `className` | `string` | Extra CSS class |
| `style` | `CSSProperties` | Inline styles |

`NavItem`: `{ id?, label: string, icon?: string, href?: string, onClick?: () => void, active?: boolean }`

---

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

**Props:** `open: boolean`, `onClose: () => void`, `title?`, `children?`, `size?: "sm" | "md" | "lg" | "xl"`, `className?`

---

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
  orientation="horizontal"  // "horizontal" | "vertical"
  size="md"                 // "sm" | "md" | "lg"
/>
```

`renderMode="menu"` collapses all buttons into a single `⋮ Actions` dropdown.

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `buttons` | `ButtonConfig[]` | Button definitions |
| `renderMode` | `"inline" \| "menu"` | Display mode; default `"inline"` |
| `orientation` | `"horizontal" \| "vertical"` | Flex direction; default `"horizontal"` |
| `size` | `"sm" \| "md" \| "lg"` | Size; default `"md"` |
| `opacity` | `number` | Global opacity override |
| `onAction` | `(action: ForgeAction) => void` | Callback fired before any action runs |
| `className` | `string` | Extra CSS class |

`ButtonConfig`: `{ label?, icon?, tooltip?, variant?: "primary" | "secondary" | "danger" | "ghost", disabled?, action: ForgeAction }`

---

## Runtime API

### loadModelSet / fetchObjectSet

Generated loader functions are the primary way to load data:

```typescript
import { loadStudentSet } from "../.forge/generated/typescript/Student";

const studentSet = await loadStudentSet({ limit: 100, offset: 0 });
// studentSet.rows    → Student[]
// studentSet.schema  → ForgeSchema
// studentSet.total   → number
// studentSet.mode    → "snapshot" | "stream"
```

Never write raw `fetch` calls for object data — use the generated loader.

**Pagination:**

```typescript
const page1 = await loadStudentSet({ limit: 50, offset: 0 });
const page2 = await loadStudentSet({ limit: 50, offset: 50 });
// studentSet.total gives the full row count
```

---

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

---

### callStreamingEndpoint

Invoke a streaming endpoint over SSE:

```typescript
import { callStreamingEndpoint } from "@forge-suite/ts";

await callStreamingEndpoint(
  "33333333-0000-0000-0000-000000000001",
  { query: "summarize students" },
  {
    onEvent: (chunk) => setOutput((prev) => prev + chunk),
    onDone:  ()      => setLoading(false),
    onError: (err)   => console.error(err),
  }
);
```

---

### triggerPipeline

```typescript
import { triggerPipeline } from "@forge-suite/ts";

await triggerPipeline("normalize_students");
```

POSTs to `/api/pipelines/{name}/run`. Useful for "Refresh Data" buttons that re-pull from an external source.

---

### configureForge

By default, the Forge client targets `window.location.origin`. Only call `configureForge` when you need to override the target explicitly:

```typescript
import { configureForge } from "@forge-suite/ts";

configureForge({ baseUrl: "https://my-server.example.com" });
```

When using the Vite dev server, all `/api/*` and `/endpoints/*` requests are automatically proxied to the Forge backend — no configuration needed.

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

// Call an action endpoint
const endpointAction: ForgeAction = {
  kind: "endpoint",
  endpointId: "11111111-0000-0000-0000-000000000001",
  prefill: { status: "graduated" },
};

// Client-side navigation
const navAction: ForgeAction = {
  kind: "navigation",
  to: "/students/:id",
  params: { id: student.id },
};
```

---

## Key TypeScript Types

```typescript
// From @forge-suite/ts

interface ForgeObjectSet<T> {
  rows:      T[];
  schema:    ForgeSchema;
  datasetId: string;
  mode:      "snapshot" | "stream";
  total?:    number;
}

interface ForgeSchema {
  name:        string;
  mode:        "snapshot" | "stream";
  fields:      Record<string, ForgeFieldMeta>;
  primary_key?: string;
}

interface ForgeFieldMeta {
  type:          "string" | "integer" | "float" | "boolean" | "datetime";
  nullable:      boolean;
  display?:      string;
  display_hint?: string;
}

type ForgeAction =
  | { kind: "ui";         handler: (item?: any) => void | Promise<void> }
  | { kind: "endpoint";   endpointId: string; prefill?: Record<string, unknown> }
  | { kind: "navigation"; to: string; params?: Record<string, string> };

interface StateBinding {
  __forge_binding: true;
  stateKey: string;
}

// Create a StateBinding:
// import { bindState } from "@forge-suite/ts";
// bindState("myKey")  →  { __forge_binding: true, stateKey: "myKey" }

interface InteractionConfig<T> {
  selectable?:        "none" | "single" | "multi";
  onClick?:           ForgeAction;
  onDoubleClick?:     ForgeAction;
  onSelectionChange?: (rows: T[]) => void;
  contextMenu?:       ContextMenuItem[] | ((row: T) => ContextMenuItem[]);
  tooltip?:           (row: T) => string;
  colorScheme?:       (row: T) => string;
  visibleFields?:     string[];
  sortField?:         string;
  sortOrder?:         "asc" | "desc";
  density?:           "compact" | "comfortable";
}

interface ComputedAttributeAttachment {
  endpointId: string;
  params?:    Record<string, unknown | StateBinding>;
}
```
