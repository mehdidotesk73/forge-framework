# @forge-suite/ts

The Forge TypeScript/React widget library and runtime.

## What you need to know

UI developers import from this package. They compose widgets on pages using object sets from the generated SDK. They never write fetch logic, never import Python model classes, and never know about dataset UUIDs or DuckDB.

## Install

```bash
npm install @forge-suite/ts
```

## Widget Reference

All widgets are imported from `@forge-suite/ts`. Runtime utilities are imported from `@forge-suite/ts/runtime`.

### Display Widgets

**ObjectTable** — tabular display of an object set. Attach computed column endpoints; bind parameters to local state.

```tsx
<ObjectTable
  objectSet={myObjectSet}
  computedColumns={[{
    endpointId: "uuid-of-endpoint",
    params: { timeframe: bindState("timeframe") },
  }]}
  localState={{ timeframe }}
  interaction={{ visibleFields: ["name", "status"], selectable: "single" }}
/>
```

**ObjectCard** — single object display.

**MetricTile** — single value or aggregation from an object set.

**Chart** — line, bar, or area chart backed by an object set.

### Input Widgets

`TextInput`, `NumberInput`, `DateInput`, `Toggle`, `Selector`, `MultiSelector`, `FileUpload`

### Composite Widgets

**Form** — auto-renders from a call form descriptor. Point at an endpoint UUID:
```tsx
<Form endpointId="uuid" onSuccess={handleSuccess} />
```

**FilterBar** — produces a filter state object consumed by display widgets.

### Action Widget

**ButtonGroup** — one or more buttons. Supports inline or collapsed menu render mode.
```tsx
<ButtonGroup
  buttons={[{
    label: "Create",
    variant: "primary",
    action: { kind: "ui", handler: () => setOpen(true) },
  }]}
/>
```

### Layout Widgets

**Container** — flex or grid box layout.

**Navbar** — navigation shell.

**Modal** — overlay triggered by any action.

## The Action type

Actions connect widgets to behavior without the UI developer writing fetch logic:

```ts
// Local handler
{ kind: "ui", handler: () => void }

// Endpoint call — framework resolves descriptor, renders form, handles submit
{ kind: "endpoint", endpointId: "uuid", prefill?: {} }

// Navigation
{ kind: "navigation", to: "/page", params?: {} }
```

## Binding local state to computed column parameters

```tsx
import { bindState } from "@forge-suite/ts";

// When `days` changes, the endpoint is automatically refetched
<ObjectTable
  computedColumns={[{
    endpointId: MOVING_AVG_ID,
    params: { days: bindState("days") },
  }]}
  localState={{ days: parseInt(selectedDays) }}
/>
```

## Building the package

```bash
npm install
npm run build    # outputs to dist/
npm run dev      # watch mode
npm run typecheck
```
