import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type {
  ComputedColumnAttachment,
  ForgeObjectSet,
  InteractionConfig,
} from "../types/index.js";
import { callEndpoint } from "../runtime/client.js";
import { getDisplayFields, getFieldLabel, isStateBinding } from "../runtime/schema.js";

interface ContextMenuState {
  x: number;
  y: number;
  row: Record<string, unknown>;
}

export interface ObjectTableProps<T extends Record<string, unknown>> {
  objectSet: ForgeObjectSet<T>;
  interaction?: InteractionConfig<T>;
  computedColumns?: ComputedColumnAttachment[];
  localState?: Record<string, unknown>;
  className?: string;
}

export function ObjectTable<T extends Record<string, unknown>>({
  objectSet,
  interaction = {},
  computedColumns = [],
  localState = {},
  className = "",
}: ObjectTableProps<T>) {
  const { schema, rows } = objectSet;
  const visibleFields = interaction.visibleFields ?? getDisplayFields(schema);

  // ── Computed columns ─────────────────────────────────────────────────────
  const [computedData, setComputedData] = useState<Record<string, Record<string, Record<string, unknown>>>>({});

  const fetchComputed = useCallback(async () => {
    const next: Record<string, Record<string, Record<string, unknown>>> = {};
    for (const attachment of computedColumns) {
      const resolvedParams: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(attachment.params ?? {})) {
        resolvedParams[k] = isStateBinding(v) ? localState[v.stateKey] : v;
      }
      try {
        const pk = objectSet.schema.primary_key!;
        const payload = { primary_keys: rows.map(r => r[pk]), ...resolvedParams };

        const result = await callEndpoint<{ columns: Record<string, Record<string, unknown>> }>(
          attachment.endpointId,
          payload
        );
        next[attachment.endpointId] = result.columns ?? {};
      } catch (e) {
        console.error(`Computed column ${attachment.endpointId} failed:`, e);
      }
    }
    setComputedData(next);
  }, [rows, computedColumns, localState]);

  useEffect(() => {
    if (computedColumns.length > 0) fetchComputed();
  }, [fetchComputed]);

  const computedColumnNames = useMemo(() => {
    const names: string[] = [];
    for (const pkMap of Object.values(computedData))
      for (const colMap of Object.values(pkMap))
        for (const col of Object.keys(colMap))
          if (!names.includes(col)) names.push(col);
    return names;
  }, [computedData]);

  // ── Sorting ───────────────────────────────────────────────────────────────
  const [sortField, setSortField] = useState(interaction.sortField ?? "");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(interaction.sortOrder ?? "asc");

  const sorted = useMemo(() => {
    if (!sortField) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortField], bv = b[sortField];
      if (av === bv) return 0;
      return (av! < bv! ? -1 : 1) * (sortOrder === "asc" ? 1 : -1);
    });
  }, [rows, sortField, sortOrder]);

  // ── Selection ─────────────────────────────────────────────────────────────
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());

  const handleRowClick = (rowIdx: number, row: T) => {
    if (interaction.selectable === "multi") {
      setSelectedRows(prev => {
        const next = new Set(prev);
        next.has(rowIdx) ? next.delete(rowIdx) : next.add(rowIdx);
        return next;
      });
    } else if (interaction.selectable === "single") {
      setSelectedRows(new Set([rowIdx]));
    }
    if (interaction.onClick?.kind === "ui") interaction.onClick.handler(row);
  };

  // ── Context menu ──────────────────────────────────────────────────────────
  const [ctxMenu, setCtxMenu] = useState<ContextMenuState | null>(null);
  const ctxRef = useRef<HTMLDivElement>(null);

  const handleContextMenu = (e: React.MouseEvent, row: T) => {
    if (!interaction.contextMenu?.length) return;
    e.preventDefault();
    setCtxMenu({ x: e.clientX, y: e.clientY, row: row as Record<string, unknown> });
  };

  // Close on click outside or Escape
  useEffect(() => {
    if (!ctxMenu) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key !== "Escape") return;
      if (e instanceof MouseEvent && ctxRef.current?.contains(e.target as Node)) return;
      setCtxMenu(null);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [ctxMenu]);

  const densityClass =
    interaction.density === "compact" ? "forge-table-compact" :
    interaction.density === "comfortable" ? "forge-table-comfortable" : "";

  return (
    <>
      <div className={`forge-object-table ${densityClass} ${className}`}>
        <table>
          <thead>
            <tr>
              {[...visibleFields, ...computedColumnNames].map((col) => (
                <th
                  key={col}
                  onClick={() => {
                    if (sortField === col) setSortOrder(o => o === "asc" ? "desc" : "asc");
                    else { setSortField(col); setSortOrder("asc"); }
                  }}
                >
                  {getFieldLabel(schema, col)}
                  {sortField === col ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={selectedRows.has(rowIdx) ? "forge-row-selected" : ""}
                onClick={() => handleRowClick(rowIdx, row)}
                onContextMenu={(e) => handleContextMenu(e, row)}
              >
                {visibleFields.map((col) => (
                  <td key={col}>{String(row[col] ?? "")}</td>
                ))}
                {computedColumnNames.map((col) => {
                  const pk = objectSet.schema.primary_key!;
                  const pkVal = String(row[pk]);
                  const value = Object.values(computedData)
                    .map(d => d[pkVal]?.[col])
                    .find(v => v !== undefined);
                  return <td key={col}>{String(value ?? "")}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Context menu — portalled to body so it's never clipped */}
      {ctxMenu && interaction.contextMenu?.length && createPortal(
        <div
          ref={ctxRef}
          className="forge-context-menu"
          style={{ top: ctxMenu.y, left: ctxMenu.x }}
        >
          {interaction.contextMenu.map((item, i) => (
            <button
              key={i}
              type="button"
              className="forge-context-menu-item"
              disabled={item.disabled}
              onClick={() => {
                setCtxMenu(null);
                if (item.action.kind === "ui") item.action.handler(ctxMenu.row);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}
