import React, { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchObjectSet, callEndpoint, ObjectTable, ButtonGroup, Container, createObjectSet, Modal } from "@forge-suite/ts";
import type { ContextMenuItem, ForgeSchema } from "@forge-suite/ts";

function columnarToRecords(columns: string[], rows: unknown[][]): Record<string, unknown>[] {
  return rows.map(row => Object.fromEntries(columns.map((col, i) => [col, row[i]])));
}

function previewSchema(columns: string[]): ForgeSchema {
  return {
    name: "Preview",
    mode: "snapshot",
    primary_key: null,
    fields: Object.fromEntries(columns.map(col => [col, { type: "string" as const, display: col }])),
  };
}

const LIST_PROJECT_DATASETS_ID = "cccccccc-0015-0000-0000-000000000000";
const PREVIEW_DATASET_ID       = "cccccccc-0025-0000-0000-000000000000";

type ProjectRow = { id: string; name: string; is_active: string };
type DatasetEntry = {
  id: string;
  name: string;
  row_count: number;
  created_at: string;
  is_snapshot: boolean;
};

const DATASET_SCHEMA: ForgeSchema = {
  name: "Dataset",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    name:        { type: "string",   display: "Name" },
    id:          { type: "string",   display: "ID" },
    row_count:   { type: "integer",  display: "Rows" },
    is_snapshot: { type: "boolean",  display: "Type" },
    created_at:  { type: "datetime", display: "Created" },
  },
};

export function DatasetsPage() {
  const [previewDataset, setPreviewDataset] = useState<DatasetEntry | null>(null);
  const [previewLimit, setPreviewLimit] = useState(200);
  const scrollRef = useRef<HTMLDivElement>(null);
  const savedScrollHeight = useRef(0);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: datasetsResult } = useQuery({
    queryKey: ["project_datasets", active?.id],
    queryFn: () =>
      callEndpoint<{ datasets?: DatasetEntry[]; error?: string }>(
        LIST_PROJECT_DATASETS_ID,
        { project_id: active?.id ?? "" }
      ),
    enabled: !!active,
    refetchInterval: 10000,
  });

  const { data: previewResult, isLoading: previewLoading } = useQuery({
    queryKey: ["dataset_preview", active?.id, previewDataset?.id, previewLimit],
    queryFn: () =>
      callEndpoint<{ columns?: string[]; rows?: unknown[][]; error?: string }>(
        PREVIEW_DATASET_ID,
        { project_id: active?.id ?? "", dataset_id: previewDataset!.id, limit: previewLimit }
      ),
    enabled: !!active && !!previewDataset,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (savedScrollHeight.current > 0 && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight - savedScrollHeight.current;
      savedScrollHeight.current = 0;
    }
  }, [previewResult?.rows?.length]);

  const datasets = datasetsResult?.datasets ?? [];
  const objectSet = createObjectSet(datasets, DATASET_SCHEMA, "datasets", "snapshot");

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Datasets</h1>
      </div>

      {!active ? (
        <div className="empty-state">No active project.</div>
      ) : datasetsResult?.error ? (
        <div className="empty-state" style={{ color: "var(--accent-red)" }}>
          {datasetsResult.error}
        </div>
      ) : datasets.length === 0 ? (
        <div className="empty-state">No datasets found.</div>
      ) : (
        <div className="card">
          <ObjectTable
            objectSet={objectSet}
            interaction={{
              visibleFields: ["name", "id", "row_count", "is_snapshot", "created_at"],
              contextMenu: (row): ContextMenuItem[] => [
                {
                  label: "Preview",
                  action: {
                    kind: "ui",
                    handler: () => setPreviewDataset(row as unknown as DatasetEntry),
                  },
                },
              ],
            }}
            renderCell={(field, value, _row) => {
              if (field === "id") return <span className="mono" style={{ color: "var(--text-muted)", fontSize: 11 }}>{String(value ?? "")}</span>;
              if (field === "row_count") return <span className="mono">{value == null ? "—" : Number(value).toLocaleString()}</span>;
              if (field === "is_snapshot") return (
                <span className={`badge ${value ? "badge-warn" : "badge-ok"}`}>
                  {value ? "snapshot" : "immutable"}
                </span>
              );
              if (field === "created_at") return <span className="mono" style={{ color: "var(--text-muted)" }}>{value ? String(value).slice(0, 19).replace("T", " ") : "—"}</span>;
              return null;
            }}
          />
        </div>
      )}

      <Modal
        open={!!previewDataset}
        onClose={() => { setPreviewDataset(null); setPreviewLimit(200); }}
        title={previewDataset ? `Preview — ${previewDataset.name || previewDataset.id}` : ""}
        size="xl"
      >
        {previewLoading ? (
          <div style={{ color: "var(--text-muted)", padding: "32px 0", textAlign: "center" }}>Loading…</div>
        ) : previewResult?.error ? (
          <div style={{ color: "var(--accent-red)", fontSize: 13 }}>{previewResult.error}</div>
        ) : previewResult?.columns && previewResult?.rows ? (() => {
          const records = columnarToRecords(previewResult.columns!, previewResult.rows!);
          const schema = previewSchema(previewResult.columns!);
          const objectSet = createObjectSet(records, schema, "preview", "snapshot");
          return (
            <>
              <ObjectTable
                ref={scrollRef}
                objectSet={objectSet}
                style={{ maxHeight: "60vh" }}
                interaction={{
                  selectable: "multi",
                  visibleFields: previewResult.columns,
                }}
                renderCell={(_, value) =>
                  value == null
                    ? <span style={{ color: "var(--text-muted)" }}>null</span>
                    : null
                }
              />
              <Container
                direction="row"
                alignItems="center"
                gap="8px"
                padding="0"
                style={{ marginTop: 4, justifyContent: "space-between" }}
              >
                <div>
                  {previewResult.rows.length === previewLimit && (
                    <ButtonGroup
                      size="sm"
                      buttons={[{
                        label: "Load 200 more",
                        variant: "ghost",
                        action: {
                          kind: "ui",
                          handler: () => {
                            if (scrollRef.current) savedScrollHeight.current = scrollRef.current.scrollHeight - scrollRef.current.scrollTop;
                            setPreviewLimit((l) => l + 200);
                          },
                        },
                      }]}
                    />
                  )}
                </div>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {previewResult.rows.length.toLocaleString()} rows shown
                </span>
              </Container>
            </>
          );
        })() : null}
      </Modal>
    </div>
  );
}
