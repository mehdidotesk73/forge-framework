/**
 * Form widget — auto-renders from a call form descriptor.
 * UI developer points it at an endpoint UUID; the widget fetches the
 * descriptor and renders all fields.
 */
import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { EndpointDescriptor, ForgeAction } from "../types/index.js";
import { callEndpoint, fetchAllEndpoints } from "../runtime/client.js";
import { TextInput, NumberInput, Toggle, Selector } from "./inputs.js";

export interface FormProps {
  endpointId: string;
  prefill?: Record<string, unknown>;
  onSuccess?: (result: unknown) => void;
  onError?: (err: string) => void;
  submitLabel?: string;
  className?: string;
}

export function Form({
  endpointId,
  prefill = {},
  onSuccess,
  onError,
  submitLabel = "Submit",
  className = "",
}: FormProps) {
  const { data: registry } = useQuery({
    queryKey: ["forge-endpoints"],
    queryFn: fetchAllEndpoints,
    staleTime: 30_000,
  });

  const descriptor = registry?.[endpointId] as EndpointDescriptor | undefined;
  const [values, setValues] = useState<Record<string, unknown>>({ ...prefill });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (descriptor) {
      const defaults: Record<string, unknown> = {};
      for (const p of descriptor.params) {
        if (!(p.name in values)) {
          defaults[p.name] = p.default ?? "";
        }
      }
      setValues((v) => ({ ...defaults, ...v }));
    }
  }, [descriptor]);

  if (!descriptor) {
    return <div className="forge-form-loading">Loading form...</div>;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const paramNames = new Set(descriptor.params.map((p) => p.name));
      const payload = Object.fromEntries(
        Object.entries(values).filter(([k]) => paramNames.has(k))
      );
      const result = await callEndpoint(endpointId, payload);
      onSuccess?.(result);
    } catch (err) {
      const msg = String(err);
      setError(msg);
      onError?.(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className={`forge-form ${className}`} onSubmit={handleSubmit}>
      <h3 className="forge-form-title">{descriptor.name}</h3>
      {descriptor.description && (
        <p className="forge-form-description">{descriptor.description}</p>
      )}
      {descriptor.params.map((param) => {
        const value = values[param.name];
        const update = (v: unknown) =>
          setValues((prev) => ({ ...prev, [param.name]: v }));

        if (param.type === "boolean") {
          return (
            <Toggle
              key={param.name}
              label={param.name}
              checked={Boolean(value)}
              onChange={update}
            />
          );
        }
        if (param.type === "integer" || param.type === "float") {
          return (
            <NumberInput
              key={param.name}
              label={param.name}
              value={Number(value ?? 0)}
              onChange={update}
            />
          );
        }
        return (
          <TextInput
            key={param.name}
            label={`${param.name}${param.required ? " *" : ""}`}
            value={String(value ?? "")}
            onChange={update}
            placeholder={param.description}
          />
        );
      })}
      {error && <div className="forge-form-error">{error}</div>}
      <button type="submit" disabled={submitting} className="forge-form-submit">
        {submitting ? "Submitting..." : submitLabel}
      </button>
    </form>
  );
}
