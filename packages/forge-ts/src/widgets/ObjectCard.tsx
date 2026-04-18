import React from "react";
import type { ForgeSchema, InteractionConfig } from "../types/index.js";
import { getDisplayFields, getFieldLabel } from "../runtime/schema.js";

export interface ObjectCardProps<T extends Record<string, unknown>> {
  object: T;
  schema: ForgeSchema;
  interaction?: InteractionConfig<T>;
  layout?: "default" | "compact" | "detail";
  className?: string;
}

export function ObjectCard<T extends Record<string, unknown>>({
  object,
  schema,
  interaction = {},
  layout = "default",
  className = "",
}: ObjectCardProps<T>) {
  const fields = interaction.visibleFields ?? getDisplayFields(schema);

  return (
    <div
      className={`forge-object-card forge-card-${layout} ${className}`}
      onClick={() => {
        if (interaction.onClick?.kind === "ui") {
          interaction.onClick.handler(object);
        }
      }}
    >
      {fields.map((field) => (
        <div key={field} className="forge-card-field">
          <span className="forge-card-label">{getFieldLabel(schema, field)}</span>
          <span className="forge-card-value">{String(object[field] ?? "")}</span>
        </div>
      ))}
    </div>
  );
}
