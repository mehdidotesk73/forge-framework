import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type {
  ComputedAttributeAttachment,
  ContextMenuItem,
  ForgeObjectSet,
  InteractionConfig,
} from "../types/index.js";
import { callEndpoint } from "../runtime/client.js";
import {
  getDisplayFields,
  getFieldLabel,
  isStateBinding,
} from "../runtime/schema.js";
import { Selector } from "./inputs.js";
import { ButtonGroup } from "./ButtonGroup.js";
import { Container } from "./layout.js";

function formatLocalDatetime(value: unknown): string {
  if (value == null || value === "") return "";
  const d = new Date(String(value));
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

interface ContextMenuState {
  x: number;
  y: number;
  row: Record<string, unknown>;
}

export interface ObjectTableProps<T extends Record<string, unknown>> {
  objectSet: ForgeObjectSet<T>;
  interaction?: InteractionConfig<T>;
  computedColumns?: ComputedAttributeAttachment[];
  localState?: Record<string, unknown>;
  renderCell?: (field: string, value: unknown, row: T) => React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

function ObjectTableInner<T extends Record<string, unknown>>(
  {
    objectSet,
    interaction = {},
    computedColumns = [],
    localState = {},
    renderCell,
    className = "",
    style,
  }: ObjectTableProps<T>,
  forwardedRef: React.ForwardedRef<HTMLDivElement>,
) {
  const { schema, rows } = objectSet;
  const innerRef = useRef<HTMLDivElement>(null);
  const tableRef = (forwardedRef ??
    innerRef) as React.RefObject<HTMLDivElement>;
  const visibleFields = interaction.visibleFields ?? getDisplayFields(schema);

  // ── Computed columns ─────────────────────────────────────────────────────
  const [computedData, setComputedData] = useState<
    Record<string, Record<string, Record<string, unknown>>>
  >({});

  const fetchComputed = useCallback(async () => {
    const next: Record<string, Record<string, Record<string, unknown>>> = {};
    for (const attachment of computedColumns) {
      const resolvedParams: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(attachment.params ?? {})) {
        resolvedParams[k] = isStateBinding(v) ? localState[v.stateKey] : v;
      }
      try {
        const pk = objectSet.schema.primary_key!;
        const payload = {
          primary_keys: rows.map((r) => r[pk]),
          ...resolvedParams,
        };

        const result = await callEndpoint<{
          columns: Record<string, Record<string, unknown>>;
        }>(attachment.endpointId, payload);
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
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(
    interaction.sortOrder ?? "asc",
  );

  const sorted = useMemo(() => {
    if (!sortField) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortField],
        bv = b[sortField];
      if (av === bv) return 0;
      return (av! < bv! ? -1 : 1) * (sortOrder === "asc" ? 1 : -1);
    });
  }, [rows, sortField, sortOrder]);

  // ── Selection ─────────────────────────────────────────────────────────────
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [copyColumn, setCopyColumn] = useState("");
  const onSelectionChangeRef = useRef(interaction.onSelectionChange);
  onSelectionChangeRef.current = interaction.onSelectionChange;
  const sortedRef = useRef(sorted);
  sortedRef.current = sorted;
  const lastClickedIdx = useRef<number | null>(null);

  useEffect(() => {
    onSelectionChangeRef.current?.(
      sortedRef.current.filter((_, i) => selectedRows.has(i)),
    );
  }, [selectedRows]);

  const handleRowClick = (rowIdx: number, row: T, e: React.MouseEvent) => {
    if (interaction.selectable === "multi") {
      const ctrl = e.ctrlKey || e.metaKey;
      if (e.shiftKey && lastClickedIdx.current !== null) {
        const lo = Math.min(lastClickedIdx.current, rowIdx);
        const hi = Math.max(lastClickedIdx.current, rowIdx);
        setSelectedRows((prev) => {
          const next = ctrl ? new Set(prev) : new Set<number>();
          for (let i = lo; i <= hi; i++) next.add(i);
          return next;
        });
      } else if (ctrl) {
        setSelectedRows((prev) => {
          const next = new Set(prev);
          next.has(rowIdx) ? next.delete(rowIdx) : next.add(rowIdx);
          return next;
        });
        lastClickedIdx.current = rowIdx;
      } else {
        setSelectedRows(new Set([rowIdx]));
        lastClickedIdx.current = rowIdx;
      }
    } else if (interaction.selectable === "single") {
      setSelectedRows(new Set([rowIdx]));
      lastClickedIdx.current = rowIdx;
    }
    if (interaction.onClick?.kind === "ui") interaction.onClick.handler(row);
  };

  // ── Context menu ──────────────────────────────────────────────────────────
  const [ctxMenu, setCtxMenu] = useState<ContextMenuState | null>(null);
  const ctxRef = useRef<HTMLDivElement>(null);

  const resolveContextMenu = (row: T): ContextMenuItem[] => {
    if (!interaction.contextMenu) return [];
    return typeof interaction.contextMenu === "function"
      ? interaction.contextMenu(row)
      : interaction.contextMenu;
  };

  const handleContextMenu = (e: React.MouseEvent, row: T) => {
    const items = resolveContextMenu(row);
    if (!items.length) return;
    e.preventDefault();
    setCtxMenu({
      x: e.clientX,
      y: e.clientY,
      row: row as Record<string, unknown>,
    });
  };

  // Close on click outside or Escape
  useEffect(() => {
    if (!ctxMenu) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key !== "Escape") return;
      if (e instanceof MouseEvent && ctxRef.current?.contains(e.target as Node))
        return;
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
    interaction.density === "compact"
      ? "forge-table-compact"
      : interaction.density === "comfortable"
        ? "forge-table-comfortable"
        : "";

  return (
    <>
      <div
        ref={tableRef}
        className={`forge-object-table ${densityClass} ${className}`}
        style={{ overflow: "auto", ...style }}
      >
        <table>
          <thead
            style={{
              position: "sticky",
              top: 0,
              zIndex: 1,
              background: "var(--bg-panel)",
            }}
          >
            <tr>
              {[...visibleFields, ...computedColumnNames].map((col) => (
                <th
                  key={col}
                  onClick={() => {
                    if (sortField === col)
                      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
                    else {
                      setSortField(col);
                      setSortOrder("asc");
                    }
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
                onClick={(e) => handleRowClick(rowIdx, row, e)}
                onContextMenu={(e) => handleContextMenu(e, row)}
              >
                {visibleFields.map((col) => {
                  const meta = schema.fields[col];
                  const raw = row[col];
                  const defaultContent =
                    meta?.type === "datetime" ||
                    meta?.display_hint === "datetime"
                      ? formatLocalDatetime(raw)
                      : String(raw ?? "");
                  return (
                    <td key={col}>
                      {renderCell
                        ? (renderCell(col, raw, row) ?? defaultContent)
                        : defaultContent}
                    </td>
                  );
                })}
                {computedColumnNames.map((col) => {
                  const pk = objectSet.schema.primary_key!;
                  const pkVal = String(row[pk]);
                  const value = Object.values(computedData)
                    .map((d) => d[pkVal]?.[col])
                    .find((v) => v !== undefined);
                  return <td key={col}>{String(value ?? "")}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Selection footer */}
      {interaction.selectable && selectedRows.size > 0 && (
        <Container
          direction='row'
          layout='flex'
          gap='0px'
          padding='0px'
          style={{
            marginBottom: 24,
            flexWrap: "wrap",
            alignItems: "flex-end",
            fontSize: 11,
            color: "var(--text-muted)",
          }}
        >
          <span>{selectedRows.size} selected —</span>
          <ButtonGroup
            buttons={[
              {
                label: "Clear",
                variant: "ghost",
                action: {
                  kind: "ui",
                  handler: () => {
                    setSelectedRows(new Set());
                    setCopyColumn("");
                  },
                },
              },
            ]}
            size='sm'
            renderMode='inline'
          />

          <Selector
            value={copyColumn}
            options={[...visibleFields, ...computedColumnNames].map((col) => ({
              value: col,
              label: getFieldLabel(schema, col),
            }))}
            onChange={(str) => setCopyColumn(str)}
            placeholder='copy column...'
            size='sm'
            variant='default'
            className='forge-table-copy-select'
          />
          {copyColumn && (
            <ButtonGroup
              buttons={[
                {
                  label: "Copy",
                  variant: "ghost",
                  action: {
                    kind: "ui",
                    handler: () => {
                      const selectedSorted = sorted.filter((_, i) =>
                        selectedRows.has(i),
                      );
                      const values = selectedSorted.map((r) =>
                        r[copyColumn] == null ? "" : String(r[copyColumn]),
                      );
                      navigator.clipboard.writeText(values.join("\n"));
                    },
                  },
                },
              ]}
              size='sm'
              renderMode='inline'
              className='forge-table-selection-copy'
            />
          )}
        </Container>
      )}

      {/* Context menu — portalled to body so it's never clipped */}
      {ctxMenu &&
        createPortal(
          <div
            ref={ctxRef}
            className='forge-context-menu'
            style={{ top: ctxMenu.y, left: ctxMenu.x }}
          >
            {resolveContextMenu(ctxMenu.row as T).map((item, i) => (
              <button
                key={i}
                type='button'
                className='forge-context-menu-item'
                disabled={item.disabled}
                onClick={() => {
                  setCtxMenu(null);
                  if (item.action.kind === "ui")
                    item.action.handler(ctxMenu.row);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}

export const ObjectTable = React.forwardRef(ObjectTableInner) as <
  T extends Record<string, unknown>,
>(
  props: ObjectTableProps<T> & { ref?: React.Ref<HTMLDivElement> },
) => React.ReactElement | null;
