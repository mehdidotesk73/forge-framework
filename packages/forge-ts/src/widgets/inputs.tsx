/**
 * Atomic input widgets: TextInput, NumberInput, DateInput, Toggle,
 * Selector, MultiSelector, FileUpload
 */
import React, { useRef } from "react";
import { callEndpoint } from "../runtime/client.js";

// ── TextInput ────────────────────────────────────────────────────────────────

export interface TextInputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
}
export function TextInput({ value, onChange, placeholder, label, disabled, className = "" }: TextInputProps) {
  return (
    <div className={`forge-input forge-text-input ${className}`}>
      {label && <label>{label}</label>}
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} disabled={disabled} />
    </div>
  );
}

// ── NumberInput ──────────────────────────────────────────────────────────────

export interface NumberInputProps {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  className?: string;
}
export function NumberInput({ value, onChange, min, max, step, label, className = "" }: NumberInputProps) {
  return (
    <div className={`forge-input forge-number-input ${className}`}>
      {label && <label>{label}</label>}
      <input type="number" value={value} min={min} max={max} step={step}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

// ── DateInput ────────────────────────────────────────────────────────────────

export interface DateInputProps {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  className?: string;
}
export function DateInput({ value, onChange, label, className = "" }: DateInputProps) {
  return (
    <div className={`forge-input forge-date-input ${className}`}>
      {label && <label>{label}</label>}
      <input type="date" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

// ── Toggle ───────────────────────────────────────────────────────────────────

export interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  className?: string;
}
export function Toggle({ checked, onChange, label, className = "" }: ToggleProps) {
  return (
    <div className={`forge-toggle ${className}`}>
      {label && <label>{label}</label>}
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </div>
  );
}

// ── Selector ─────────────────────────────────────────────────────────────────

export interface SelectorOption {
  value: string;
  label: string;
}
export interface SelectorProps {
  value: string;
  options: SelectorOption[];
  onChange: (v: string) => void;
  label?: string;
  placeholder?: string;
  className?: string;
}
export function Selector({ value, options, onChange, label, placeholder, className = "" }: SelectorProps) {
  return (
    <div className={`forge-selector ${className}`}>
      {label && <label>{label}</label>}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

// ── MultiSelector ─────────────────────────────────────────────────────────────

export interface MultiSelectorProps {
  value: string[];
  options: SelectorOption[];
  onChange: (v: string[]) => void;
  label?: string;
  className?: string;
}
export function MultiSelector({ value, options, onChange, label, className = "" }: MultiSelectorProps) {
  const toggle = (v: string) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div className={`forge-multi-selector ${className}`}>
      {label && <label>{label}</label>}
      <div className="forge-multi-options">
        {options.map((o) => (
          <label key={o.value} className="forge-multi-option">
            <input type="checkbox" checked={value.includes(o.value)} onChange={() => toggle(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </div>
  );
}

// ── FileUpload ────────────────────────────────────────────────────────────────

export interface FileUploadProps {
  label?: string;
  datasetName?: string;
  onSuccess?: (datasetId: string) => void;
  onError?: (err: string) => void;
  className?: string;
}
export function FileUpload({ label, datasetName, onSuccess, onError, className = "" }: FileUploadProps) {
  const ref = useRef<HTMLInputElement>(null);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", datasetName ?? file.name.replace(/\.[^.]+$/, ""));
    try {
      const res = await fetch("/api/datasets/upload", { method: "POST", body: formData });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onSuccess?.(data.id);
    } catch (err) {
      onError?.(String(err));
    }
  };

  return (
    <div className={`forge-file-upload ${className}`}>
      {label && <label>{label}</label>}
      <input type="file" ref={ref} accept=".csv,.parquet,.json" onChange={handleChange} />
    </div>
  );
}
