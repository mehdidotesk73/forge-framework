// Core type definitions for the Forge TypeScript SDK

export interface ForgeFieldMeta {
  type: "string" | "integer" | "float" | "boolean" | "datetime";
  nullable?: boolean;
  primary_key?: boolean;
  display?: string;
  display_hint?: string;
}

export interface ForgeSchema {
  name: string;
  mode: "snapshot" | "stream";
  fields: Record<string, ForgeFieldMeta>;
  primary_key?: string | null;
}

export interface ForgeObjectSet<T = Record<string, unknown>> {
  rows: T[];
  schema: ForgeSchema;
  datasetId: string;
  mode: "snapshot" | "stream";
  total?: number;
}

// ── Action types ─────────────────────────────────────────────────────────────

export type UIAction = {
  kind: "ui";
  handler: (item?: unknown) => void;
};

export type EndpointAction = {
  kind: "endpoint";
  endpointId: string;
  prefill?: Record<string, unknown>;
};

export type NavigationAction = {
  kind: "navigation";
  to: string;
  params?: Record<string, unknown>;
};

export type ForgeAction = UIAction | EndpointAction | NavigationAction;

// ── Interaction config ────────────────────────────────────────────────────────

export interface ContextMenuItem {
  label: string;
  action: ForgeAction;
  disabled?: boolean;
}

export interface InteractionConfig<T = unknown> {
  selectable?: "none" | "single" | "multi";
  onClick?: ForgeAction;
  onDoubleClick?: ForgeAction;
  onSelectionChange?: (rows: T[]) => void;
  contextMenu?: ContextMenuItem[] | ((row: T) => ContextMenuItem[]);
  tooltip?: string | ((item: T) => string);
  colorScheme?: string;
  visibleFields?: string[];
  sortField?: string;
  sortOrder?: "asc" | "desc";
  density?: "compact" | "normal" | "comfortable";
}

// ── Computed column endpoint attachment ──────────────────────────────────────

export interface ComputedColumnAttachment {
  endpointId: string;
  params?: Record<string, unknown | StateBinding>;
}

export interface StateBinding {
  __forge_binding: true;
  stateKey: string;
}

export function bindState(stateKey: string): StateBinding {
  return { __forge_binding: true, stateKey };
}

export function isStateBinding(v: unknown): v is StateBinding {
  return typeof v === "object" && v !== null && (v as StateBinding).__forge_binding === true;
}

// ── Endpoint descriptor (from call form registry) ────────────────────────────

export interface ParamDescriptor {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: unknown;
}

export interface EndpointDescriptor {
  id: string;
  name: string;
  kind: "action" | "computed_column" | "streaming";
  description: string;
  repo: string;
  params: ParamDescriptor[];
  path: string;
  object_type?: string;
  columns?: string[];
}
