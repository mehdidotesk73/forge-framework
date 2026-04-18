import React, { useMemo } from "react";
import type { ForgeObjectSet } from "../types/index.js";

export interface MetricTileProps<T extends Record<string, unknown>> {
  label: string;
  value?: string | number;
  objectSet?: ForgeObjectSet<T>;
  field?: string;
  aggregation?: "count" | "sum" | "avg" | "min" | "max";
  format?: "number" | "currency" | "percent";
  className?: string;
}

export function MetricTile<T extends Record<string, unknown>>({
  label,
  value: staticValue,
  objectSet,
  field,
  aggregation = "count",
  format = "number",
  className = "",
}: MetricTileProps<T>) {
  const computed = useMemo(() => {
    if (staticValue !== undefined) return staticValue;
    if (!objectSet || !field) return objectSet?.rows.length ?? 0;
    const values = objectSet.rows
      .map((r) => Number(r[field]))
      .filter((v) => !isNaN(v));
    switch (aggregation) {
      case "count":
        return values.length;
      case "sum":
        return values.reduce((a, b) => a + b, 0);
      case "avg":
        return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
      case "min":
        return Math.min(...values);
      case "max":
        return Math.max(...values);
    }
  }, [staticValue, objectSet, field, aggregation]);

  const formatted = useMemo(() => {
    const n = Number(computed);
    if (format === "currency") return `$${n.toLocaleString()}`;
    if (format === "percent") return `${n.toFixed(1)}%`;
    return typeof computed === "number" ? n.toLocaleString() : String(computed);
  }, [computed, format]);

  return (
    <div className={`forge-metric-tile ${className}`}>
      <div className="forge-metric-value">{formatted}</div>
      <div className="forge-metric-label">{label}</div>
    </div>
  );
}
