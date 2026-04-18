/**
 * Schema inspection helpers.
 * Smart widgets call these internally; UI developers never call them directly.
 */

import type { ForgeObjectSet, ForgeSchema } from "../types/index.js";

export { isStateBinding } from "../types/index.js";

export function getDisplayFields(schema: ForgeSchema): string[] {
  return Object.keys(schema.fields);
}

export function getFieldLabel(schema: ForgeSchema, fieldName: string): string {
  return schema.fields[fieldName]?.display ?? fieldName;
}

export function getPrimaryKey(schema: ForgeSchema): string | undefined {
  return schema.primary_key ?? undefined;
}

export function isNumericField(schema: ForgeSchema, fieldName: string): boolean {
  const t = schema.fields[fieldName]?.type;
  return t === "integer" || t === "float";
}

export function createObjectSet<T>(
  rows: T[],
  schema: ForgeSchema,
  datasetId: string,
  mode: "snapshot" | "stream"
): ForgeObjectSet<T> {
  return { rows, schema, datasetId, mode, total: rows.length };
}
