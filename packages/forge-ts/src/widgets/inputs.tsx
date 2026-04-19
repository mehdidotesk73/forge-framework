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
const SELECTOR_SIZE_STYLES: Record<string, React.CSSProperties> = {
  sm: { fontSize: 11, padding: "2px 4px" },
  md: { fontSize: 13, padding: "6px 12px" },
  lg: { fontSize: 14, padding: "9px 14px" },
};
const SELECTOR_VARIANT_STYLES: Record<string, React.CSSProperties> = {
  ghost: { borderColor: "transparent", background: "transparent" },
};

export interface SelectorProps {
  value: string;
  options: SelectorOption[];
  onChange: (v: string) => void;
  label?: string;
  placeholder?: string;
  size?: "sm" | "md" | "lg";
  variant?: "default" | "ghost";
  className?: string;
}
export function Selector({ value, options, onChange, label, placeholder, size, variant, className = "" }: SelectorProps) {
  const sizeClass = size ? `forge-selector-${size}` : "";
  const variantClass = variant ? `forge-selector-${variant}` : "";
  const selectStyle: React.CSSProperties = {
    ...(size ? SELECTOR_SIZE_STYLES[size] : {}),
    ...(variant && variant !== "default" ? SELECTOR_VARIANT_STYLES[variant] : {}),
  };
  return (
    <div className={`forge-selector ${sizeClass} ${variantClass} ${className}`}>
      {label && <label>{label}</label>}
      <select value={value} onChange={(e) => onChange(e.target.value)} style={selectStyle}>
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

// ── TextArea ─────────────────────────────────────────────────────────────────

export interface TextAreaProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  rows?: number;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
}
export function TextArea({ value, onChange, placeholder, label, rows = 4, disabled, className = "", style }: TextAreaProps) {
  return (
    <div className={`forge-input forge-textarea-input ${className}`}>
      {label && <label>{label}</label>}
      <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} disabled={disabled} style={style} />
    </div>
  );
}

// ── RadioGroup ────────────────────────────────────────────────────────────────

export interface RadioOption { value: string; label: string; }
export interface RadioGroupProps {
  value: string;
  options: RadioOption[];
  onChange: (v: string) => void;
  label?: string;
  name: string;
  className?: string;
}
export function RadioGroup({ value, options, onChange, label, name, className = "" }: RadioGroupProps) {
  return (
    <div className={`forge-radio-group ${className}`}>
      {label && <label className="forge-radio-group-label">{label}</label>}
      <div className="forge-radio-options">
        {options.map((o) => (
          <label key={o.value} className="forge-radio-option">
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
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
