import React, { useState } from "react";
import type { ForgeSchema } from "../types/index.js";
import { getDisplayFields, getFieldLabel } from "../runtime/schema.js";

export interface FilterState {
  [field: string]: string | number | boolean | undefined;
}

export interface FilterBarProps {
  schema?: ForgeSchema;
  fields?: string[];
  onChange: (state: FilterState) => void;
  className?: string;
}

export function FilterBar({ schema, fields, onChange, className = "" }: FilterBarProps) {
  const filterFields = fields ?? (schema ? getDisplayFields(schema) : []);
  const [state, setState] = useState<FilterState>({});

  const update = (field: string, value: string) => {
    const next = { ...state, [field]: value || undefined };
    setState(next);
    onChange(next);
  };

  return (
    <div className={`forge-filter-bar ${className}`}>
      {filterFields.map((field) => (
        <div key={field} className="forge-filter-field">
          <label>{schema ? getFieldLabel(schema, field) : field}</label>
          <input
            type="text"
            value={String(state[field] ?? "")}
            placeholder={`Filter ${field}...`}
            onChange={(e) => update(field, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
}

export function applyFilterState<T extends Record<string, unknown>>(
  rows: T[],
  filters: FilterState
): T[] {
  return rows.filter((row) =>
    Object.entries(filters).every(([field, value]) => {
      if (value === undefined || value === "") return true;
      const cellValue = String(row[field] ?? "").toLowerCase();
      return cellValue.includes(String(value).toLowerCase());
    })
  );
}
