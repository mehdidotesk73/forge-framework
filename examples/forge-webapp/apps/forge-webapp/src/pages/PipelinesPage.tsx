import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchObjectSet, callEndpoint, callStreamingEndpoint, ObjectTable, ButtonGroup, TextInput, createObjectSet } from "@forge-framework/ts";
import type { ContextMenuItem } from "@forge-framework/ts";
import type { ForgeSchema } from "@forge-framework/ts";
import { LogPanel, type LogLine } from "../components/LogPanel.js";
import { DAGVisualization } from "../components/DAGVisualization.js";

const DAG_ID             = "cccccccc-0008-0000-0000-000000000000";
const RUN_PIPELINE_ID    = "cccccccc-0005-0000-0000-000000000000";
const CREATE_PIPELINE_ID = "cccccccc-0011-0000-0000-000000000000";
const SYNC_PROJECT_ID    = "cccccccc-0004-0000-0000-000000000000";
const OPEN_IN_VSCODE_ID  = "cccccccc-0017-0000-0000-000000000000";

type ProjectRow  = { id: string; name: string; is_active: string; root_path: string };
type PipelineRow = { id: string; project_id: string; name: string; module: string; function_name: string; schedule: string };
type RunRow      = { id: string; project_id: string; pipeline_name: string; started_at: string; status: string; row_count: string; error_msg: string };
type DAGData     = { nodes: Array<{ id: string; kind: "pipeline" | "dataset"; label: string; schedule?: string }>; edges: Array<{ source: string; target: string }> };

const PIPELINE_SCHEMA: ForgeSchema = {
  name: "Pipeline",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    name:     { type: "string", display: "Name" },
    module:   { type: "string", display: "Module" },
    schedule: { type: "string", display: "Schedule" },
  },
};

const RUN_SCHEMA: ForgeSchema = {
  name: "PipelineRun",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    pipeline_name: { type: "string",   display: "Pipeline" },
    started_at:    { type: "datetime", display: "Started" },
    status:        { type: "string",   display: "Status" },
    row_count:     { type: "string",   display: "Rows" },
    error_msg:     { type: "string",   display: "Error" },
  },
};

export function PipelinesPage() {
  const qc = useQueryClient();
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [activePipeline, setActivePipeline] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newResult, setNewResult] = useState<{ file?: string; error?: string } | null>(null);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: pipelineData } = useQuery({
    queryKey: ["pipelines", active?.id],
    queryFn: async () => {
      await callEndpoint(SYNC_PROJECT_ID, { project_id: active?.id ?? "" });
      return fetchObjectSet<PipelineRow>("Pipeline");
    },
    enabled: !!active,
  });
  const pipelines = (pipelineData?.rows ?? []).filter((p) => p.project_id === active?.id);

  const { data: runData, refetch: refetchRuns } = useQuery({
    queryKey: ["pipeline_runs", active?.id],
    queryFn: () => fetchObjectSet<RunRow>("PipelineRun"),
    enabled: !!active,
    refetchInterval: 5000,
  });
  const runs = (runData?.rows ?? [])
    .filter((r) => r.project_id === active?.id)
    .sort((a, b) => b.started_at.localeCompare(a.started_at))
    .slice(0, 20);

  const { data: dagData } = useQuery({
    queryKey: ["dag", active?.id],
    queryFn: () => callEndpoint<DAGData>(DAG_ID, { project_id: active?.id ?? "" }),
    enabled: !!active,
    refetchInterval: 10000,
  });

  const createPipeline = useMutation({
    mutationFn: (name: string) =>
      callEndpoint<{ file?: string; error?: string }>(CREATE_PIPELINE_ID, {
        project_id: active?.id ?? "",
        pipeline_name: name,
      }),
    onSuccess: (result) => {
      if (result?.error) {
        setNewResult({ error: result.error });
      } else {
        setNewResult({ file: result?.file });
        setNewName("");
        qc.invalidateQueries({ queryKey: ["pipelines"] });
      }
    },
  });

  const handleRun = (name: string) => {
    if (!active || running) return;
    setActivePipeline(name);
    setLogs([]);
    setRunning(true);
    callStreamingEndpoint(
      RUN_PIPELINE_ID,
      { project_id: active.id, pipeline_name: name },
      {
        onEvent: (event, data) => setLogs((prev) => [...prev, { event, data, ts: Date.now() }]),
        onDone: () => { setRunning(false); refetchRuns(); },
        onError: (err) => {
          setLogs((prev) => [...prev, { event: "error", data: err.message, ts: Date.now() }]);
          setRunning(false);
        },
      }
    );
  };

  const pipelineObjectSet = createObjectSet(pipelines, PIPELINE_SCHEMA, "pipelines", "snapshot");
  const runObjectSet = createObjectSet(runs, RUN_SCHEMA, "pipeline-runs", "snapshot");

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Pipelines</h1>
        {active && (
          <ButtonGroup
            size="sm"
            buttons={[{ label: "+ New Pipeline", variant: "primary", action: { kind: "ui", handler: () => { setShowNew(true); setNewResult(null); setNewName(""); } } }]}
          />
        )}
      </div>

      {!active ? (
        <div className="empty-state">No active project.</div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="section-title" style={{ marginBottom: 16 }}>Pipeline DAG</div>
            <DAGVisualization nodes={dagData?.nodes ?? []} edges={dagData?.edges ?? []} />
          </div>

          {showNew && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="section-title" style={{ marginBottom: 12 }}>New Pipeline</div>
              {newResult?.file ? (
                <div>
                  <div style={{ color: "var(--accent-green)", marginBottom: 8, fontSize: 13 }}>Pipeline created.</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>Open in VS Code:</div>
                  <code style={{ fontSize: 12, background: "var(--bg-hover)", padding: "4px 8px", borderRadius: 4, display: "block", marginBottom: 12 }}>
                    code "{newResult.file}"
                  </code>
                  <ButtonGroup
                    size="sm"
                    buttons={[{ label: "Close", action: { kind: "ui", handler: () => { setShowNew(false); setNewResult(null); } } }]}
                  />
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
                  <TextInput
                    value={newName}
                    onChange={(v) => { setNewName(v); setNewResult(null); }}
                    placeholder="pipeline_name (snake_case)"
                  />
                  {newResult?.error && (
                    <div style={{ fontSize: 12, color: "var(--accent-red)" }}>{newResult.error}</div>
                  )}
                  <ButtonGroup
                    size="sm"
                    buttons={[
                      { label: createPipeline.isPending ? "Creating…" : "Create Pipeline", variant: "primary", disabled: !newName || createPipeline.isPending, action: { kind: "ui", handler: () => createPipeline.mutate(newName) } },
                      { label: "Cancel", action: { kind: "ui", handler: () => { setShowNew(false); setNewResult(null); } } },
                    ]}
                  />
                </div>
              )}
            </div>
          )}

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="section-title" style={{ marginBottom: 12 }}>Pipelines</div>
            {pipelines.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px 0" }}>No pipelines found.</div>
            ) : (
              <ObjectTable
                objectSet={pipelineObjectSet}
                interaction={{
                  visibleFields: ["name", "module", "schedule"],
                  contextMenu: (row) => {
                    const items: ContextMenuItem[] = [
                      {
                        label: "↗ Open in VS Code",
                        action: { kind: "ui", handler: () => callEndpoint(OPEN_IN_VSCODE_ID, { folder_path: active!.root_path, file_path: `${active!.root_path}/${String(row.module ?? "").replace(/\./g, "/")}.py` }) },
                      },
                      {
                        label: running && activePipeline === String(row.name) ? "Running…" : "▶ Run",
                        disabled: running,
                        action: { kind: "ui", handler: () => handleRun(String(row.name)) },
                      },
                    ];
                    return items;
                  },
                }}
                renderCell={(field, value) => {
                  if (field === "module") return <span className="mono" style={{ color: "var(--text-muted)" }}>{String(value ?? "")}</span>;
                  if (field === "schedule") return <span className="mono">{String(value || "—")}</span>;
                  if (field === "name") return <span style={{ fontWeight: 500 }}>{String(value ?? "")}</span>;
                  return null;
                }}
              />
            )}
          </div>

          {(logs.length > 0 || running) && (
            <div style={{ marginBottom: 20 }}>
              <div className="section-title" style={{ marginBottom: 8 }}>
                {activePipeline ? `Output — ${activePipeline}` : "Output"}
              </div>
              <LogPanel lines={logs} running={running} />
            </div>
          )}

          <div className="card">
            <div className="section-title" style={{ marginBottom: 12 }}>Run History</div>
            {runs.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px 0" }}>No runs yet.</div>
            ) : (
              <ObjectTable
                objectSet={runObjectSet}
                interaction={{ visibleFields: ["pipeline_name", "started_at", "status", "row_count", "error_msg"] }}
                renderCell={(field, value, _row) => {
                  if (field === "pipeline_name") return <span style={{ fontWeight: 500 }}>{String(value ?? "")}</span>;
                  if (field === "started_at") return <span className="mono" style={{ color: "var(--text-muted)" }}>{value ? String(value).slice(0, 19).replace("T", " ") : "—"}</span>;
                  if (field === "status") {
                    const s = String(value ?? "");
                    const cls = s === "ok" ? "badge-ok" : s === "error" ? "badge-error" : "badge-warn";
                    return <span className={`badge ${cls}`}>{s}</span>;
                  }
                  if (field === "row_count") return <span className="mono">{String(value || "—")}</span>;
                  if (field === "error_msg") return <span style={{ color: "var(--accent-red)", fontSize: 12 }}>{String(value || "")}</span>;
                  return null;
                }}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
