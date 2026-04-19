import React, { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  callStreamingEndpoint,
  ObjectTable,
  ButtonGroup,
  TextInput,
  Selector,
  RadioGroup,
  Container,
  Modal,
  LogPanel,
  createObjectSet,
} from "@forge-framework/ts";
import type { ContextMenuItem, LogLine } from "@forge-framework/ts";
import type { ForgeSchema } from "@forge-framework/ts";

function columnarToRecords(
  columns: string[],
  rows: unknown[][],
): Record<string, unknown>[] {
  return rows.map((row) =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]])),
  );
}

function buildPreviewSchema(columns: string[]): ForgeSchema {
  return {
    name: "Preview",
    mode: "snapshot",
    primary_key: null,
    fields: Object.fromEntries(
      columns.map((col) => [col, { type: "string" as const, display: col }]),
    ),
  };
}

const RUN_MODEL_BUILD_ID = "cccccccc-0006-0000-0000-000000000000";
const CREATE_MODEL_ID = "cccccccc-0016-0000-0000-000000000000";
const LIST_PROJECT_DATASETS_ID = "cccccccc-0015-0000-0000-000000000000";
const SYNC_PROJECT_ID = "cccccccc-0004-0000-0000-000000000000";
const OPEN_IN_VSCODE_ID = "cccccccc-0017-0000-0000-000000000000";
const PREVIEW_MODEL_ID = "cccccccc-0027-0000-0000-000000000000";

type ProjectRow = {
  id: string;
  name: string;
  is_active: string;
  root_path: string;
};
type ObjectTypeRow = {
  id: string;
  project_id: string;
  name: string;
  mode: string;
  module: string;
  backing_dataset_id: string;
  field_count: string;
  built_at: string;
};
type DatasetEntry = {
  id: string;
  name: string;
  row_count: number;
  is_snapshot: boolean;
};

const MODEL_SCHEMA: ForgeSchema = {
  name: "ObjectType",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    name: { type: "string", display: "Name" },
    mode: { type: "string", display: "Mode" },
    field_count: { type: "string", display: "Fields" },
    backing_dataset_id: { type: "string", display: "Dataset ID" },
    built_at: { type: "datetime", display: "Built At" },
  },
};

function toPascalCase(s: string): string {
  const result = s
    .replace(/[^a-zA-Z0-9]+(.)/g, (_, c) => c.toUpperCase())
    .replace(/^[0-9]+/, "")
    .replace(/^(.)/, (_, c) => c.toUpperCase());
  return result || "MyModel";
}

export function ModelPage() {
  const qc = useQueryClient();
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [modelName, setModelName] = useState("");
  const [modelMode, setModelMode] = useState<"snapshot" | "immutable">(
    "snapshot",
  );
  const [newResult, setNewResult] = useState<{
    file?: string;
    class_name?: string;
    error?: string;
  } | null>(null);
  const [previewModel, setPreviewModel] = useState<ObjectTypeRow | null>(null);
  const [previewLimit, setPreviewLimit] = useState(200);
  const [selectedPreviewRows, setSelectedPreviewRows] = useState<
    Record<string, unknown>[]
  >([]);
  const [copyColumn, setCopyColumn] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const savedScrollHeight = useRef(0);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: modelData, refetch } = useQuery({
    queryKey: ["object_types", active?.id],
    queryFn: async () => {
      await callEndpoint(SYNC_PROJECT_ID, { project_id: active?.id ?? "" });
      return fetchObjectSet<ObjectTypeRow>("ObjectType");
    },
    enabled: !!active,
    refetchInterval: 5000,
  });
  const models = (modelData?.rows ?? []).filter(
    (m) => m.project_id === active?.id,
  );

  const { data: datasetsResult } = useQuery({
    queryKey: ["project_datasets", active?.id],
    queryFn: () =>
      callEndpoint<{ datasets?: DatasetEntry[]; error?: string }>(
        LIST_PROJECT_DATASETS_ID,
        { project_id: active?.id ?? "" },
      ),
    enabled: !!active && showNew,
  });
  const { data: previewResult, isLoading: previewLoading } = useQuery({
    queryKey: ["preview_model", active?.id, previewModel?.name, previewLimit],
    queryFn: () =>
      callEndpoint<{ columns?: string[]; rows?: unknown[][]; error?: string }>(
        PREVIEW_MODEL_ID,
        {
          project_id: active?.id ?? "",
          model_name: previewModel?.name ?? "",
          limit: previewLimit,
        },
      ),
    enabled: !!active && !!previewModel,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (savedScrollHeight.current > 0 && scrollRef.current) {
      scrollRef.current.scrollTop =
        scrollRef.current.scrollHeight - savedScrollHeight.current;
      savedScrollHeight.current = 0;
    }
  }, [previewResult?.rows?.length]);

  const usedDatasetIds = new Set(
    models.map((m) => m.backing_dataset_id).filter(Boolean),
  );
  const availableDatasets = (datasetsResult?.datasets ?? []).filter(
    (d) => !d.is_snapshot && !usedDatasetIds.has(d.id),
  );

  const runBuild = (projectId: string) => {
    setLogs([]);
    setRunning(true);
    callStreamingEndpoint(
      RUN_MODEL_BUILD_ID,
      { project_id: projectId },
      {
        onEvent: (event, data) =>
          setLogs((prev) => [...prev, { event, data, ts: Date.now() }]),
        onDone: async () => {
          setRunning(false);
          await callEndpoint(SYNC_PROJECT_ID, { project_id: projectId });
          qc.invalidateQueries({ queryKey: ["object_types"] });
          refetch();
        },
        onError: (err) => {
          setLogs((prev) => [
            ...prev,
            { event: "error", data: err.message, ts: Date.now() },
          ]);
          setRunning(false);
        },
      },
    );
  };

  const createModel = useMutation({
    mutationFn: () =>
      callEndpoint<{ file?: string; class_name?: string; error?: string }>(
        CREATE_MODEL_ID,
        {
          project_id: active?.id ?? "",
          dataset_id: selectedDataset,
          model_name: modelName,
          mode: modelMode,
        },
      ),
    onSuccess: async (result) => {
      if (result?.error) {
        setNewResult({ error: result.error });
        return;
      }
      setNewResult({ file: result?.file, class_name: result?.class_name });
      runBuild(active!.id);
    },
  });

  const modelObjectSet = createObjectSet(
    models,
    MODEL_SCHEMA,
    "object-types",
    "snapshot",
  );

  return (
    <div className='page'>
      <div className='page-header'>
        <h1 className='page-title'>Model</h1>
        {active && (
          <ButtonGroup
            size='sm'
            buttons={[
              {
                label: "+ New Model",
                variant: "primary",
                action: {
                  kind: "ui",
                  handler: () => {
                    setShowNew(true);
                    setNewResult(null);
                    setSelectedDataset("");
                    setModelName("");
                    setModelMode("snapshot");
                  },
                },
              },
              {
                label: running ? "Building…" : "⚙ Build models",
                disabled: running,
                action: {
                  kind: "ui",
                  handler: () => {
                    if (active && !running) runBuild(active.id);
                  },
                },
              },
            ]}
          />
        )}
      </div>

      <Modal
        open={!!previewModel}
        onClose={() => {
          setPreviewModel(null);
          setPreviewLimit(200);
          setSelectedPreviewRows([]);
          setCopyColumn("");
        }}
        title={previewModel ? `Preview — ${previewModel.name}` : ""}
        size='xl'
      >
        {previewLoading || !previewResult ? (
          <div
            style={{
              color: "var(--text-muted)",
              padding: "32px 0",
              textAlign: "center",
            }}
          >
            Loading…
          </div>
        ) : previewResult.error ? (
          <div style={{ color: "var(--accent-red)", fontSize: 13 }}>
            {previewResult.error}
          </div>
        ) : previewResult.columns && previewResult.rows ? (
          (() => {
            const records = columnarToRecords(
              previewResult.columns!,
              previewResult.rows!,
            );
            const schema = buildPreviewSchema(previewResult.columns!);
            const objectSet = createObjectSet(
              records,
              schema,
              "preview",
              "snapshot",
            );
            return (
              <>
                <ObjectTable
                  ref={scrollRef}
                  objectSet={objectSet}
                  style={{ maxHeight: "60vh" }}
                  interaction={{
                    selectable: "multi",
                    visibleFields: previewResult.columns,
                    onSelectionChange: setSelectedPreviewRows,
                  }}
                  renderCell={(_, value) =>
                    value == null ? (
                      <span style={{ color: "var(--text-muted)" }}>null</span>
                    ) : null
                  }
                />
                <Container
                  direction="row"
                  alignItems="center"
                  gap="8px"
                  padding="0"
                  style={{ marginTop: 10, justifyContent: "space-between", flexWrap: "wrap" }}
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
                              if (scrollRef.current)
                                savedScrollHeight.current =
                                  scrollRef.current.scrollHeight -
                                  scrollRef.current.scrollTop;
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
          })()
        ) : null}
      </Modal>

      {!active ? (
        <div className='empty-state'>No active project.</div>
      ) : (
        <>
          {showNew && (
            <div className='card' style={{ marginBottom: 20 }}>
              <div className='section-title' style={{ marginBottom: 12 }}>
                New Model
              </div>
              {newResult?.file ? (
                <div>
                  <div
                    style={{
                      color: "var(--accent-green)",
                      marginBottom: 8,
                      fontSize: 13,
                    }}
                  >
                    Model scaffolded — running <code>forge model build</code>…
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      marginBottom: 4,
                    }}
                  >
                    Open in VS Code:
                  </div>
                  <code
                    style={{
                      fontSize: 12,
                      background: "var(--bg-hover)",
                      padding: "4px 8px",
                      borderRadius: 4,
                      display: "block",
                      marginBottom: 12,
                    }}
                  >
                    code "{newResult.file}"
                  </code>
                  <ButtonGroup
                    size='sm'
                    buttons={[
                      {
                        label: "Close",
                        action: {
                          kind: "ui",
                          handler: () => {
                            setShowNew(false);
                            setNewResult(null);
                          },
                        },
                      },
                    ]}
                  />
                </div>
              ) : (
                <Container direction="column" gap="8px" padding="0" style={{ maxWidth: 420 }}>
                  <Selector
                    value={selectedDataset}
                    options={[
                      { value: "", label: "— select a dataset —" },
                      ...availableDatasets.map((d) => ({
                        value: d.id,
                        label: `${d.name || d.id} (${d.row_count?.toLocaleString() ?? "?"} rows)`,
                      })),
                    ]}
                    onChange={(v) => {
                      setSelectedDataset(v);
                      const ds = availableDatasets.find((d) => d.id === v);
                      if (ds && !modelName)
                        setModelName(toPascalCase(ds.name || ""));
                      setNewResult(null);
                    }}
                  />
                  <TextInput
                    value={modelName}
                    onChange={(v) => {
                      setModelName(v);
                      setNewResult(null);
                    }}
                    placeholder='PascalCase class name, e.g. BitcoinPrice'
                  />
                  <RadioGroup
                    name="model-mode"
                    value={modelMode}
                    onChange={(v) => setModelMode(v as "snapshot" | "immutable")}
                    options={[
                      { value: "snapshot", label: "snapshot" },
                      { value: "immutable", label: "immutable" },
                    ]}
                  />
                  {newResult?.error && (
                    <div style={{ fontSize: 12, color: "var(--accent-red)" }}>
                      {newResult.error}
                    </div>
                  )}
                  <ButtonGroup
                    size='sm'
                    buttons={[
                      {
                        label: createModel.isPending
                          ? "Creating…"
                          : "Create Model",
                        variant: "primary",
                        disabled:
                          !selectedDataset ||
                          !modelName ||
                          createModel.isPending,
                        action: {
                          kind: "ui",
                          handler: () => createModel.mutate(),
                        },
                      },
                      {
                        label: "Cancel",
                        action: {
                          kind: "ui",
                          handler: () => {
                            setShowNew(false);
                            setNewResult(null);
                          },
                        },
                      },
                    ]}
                  />
                </Container>
              )}
            </div>
          )}

          <div className='card' style={{ marginBottom: 20 }}>
            <div className='section-title' style={{ marginBottom: 12 }}>
              Object Types
            </div>
            {models.length === 0 ? (
              <div className='empty-state' style={{ padding: "24px 0" }}>
                No models found. Use "+ New Model" or sync after running{" "}
                <code>forge model build</code>.
              </div>
            ) : (
              <ObjectTable
                objectSet={modelObjectSet}
                interaction={{
                  visibleFields: [
                    "name",
                    "mode",
                    "field_count",
                    "backing_dataset_id",
                    "built_at",
                  ],
                  contextMenu: (row): ContextMenuItem[] => [
                    {
                      label: "Preview",
                      action: {
                        kind: "ui",
                        handler: () => setPreviewModel(row),
                      },
                    },
                    ...(row.module
                      ? [
                          {
                            label: "↗ Open in VS Code",
                            action: {
                              kind: "ui" as const,
                              handler: () =>
                                callEndpoint(OPEN_IN_VSCODE_ID, {
                                  folder_path: active!.root_path,
                                  file_path: `${active!.root_path}/${String(row.module ?? "").replace(/\./g, "/")}.py`,
                                }),
                            },
                          },
                        ]
                      : []),
                  ],
                }}
                renderCell={(field, value) => {
                  if (field === "name")
                    return (
                      <span style={{ fontWeight: 600 }}>
                        {String(value ?? "")}
                      </span>
                    );
                  if (field === "mode") {
                    const m = String(value ?? "");
                    return (
                      <span
                        className={`badge ${m === "snapshot" ? "badge-ok" : "badge-warn"}`}
                      >
                        {m}
                      </span>
                    );
                  }
                  if (field === "field_count")
                    return <span className='mono'>{String(value || "—")}</span>;
                  if (field === "backing_dataset_id") {
                    const v = String(value ?? "");
                    return (
                      <span
                        className='mono'
                        style={{ color: "var(--text-muted)", fontSize: 11 }}
                      >
                        {v ? v.slice(0, 8) + "…" : "—"}
                      </span>
                    );
                  }
                  if (field === "built_at") {
                    const v = String(value ?? "");
                    return v ? (
                      <span className='mono' style={{ fontSize: 12 }}>
                        {v.slice(0, 19).replace("T", " ")}
                      </span>
                    ) : (
                      <span
                        style={{ color: "var(--accent-orange)", fontSize: 12 }}
                      >
                        not built
                      </span>
                    );
                  }
                  return null;
                }}
              />
            )}
          </div>

          {(logs.length > 0 || running) && (
            <div>
              <div className='section-title' style={{ marginBottom: 8 }}>
                Build Output
              </div>
              <LogPanel lines={logs} running={running} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
