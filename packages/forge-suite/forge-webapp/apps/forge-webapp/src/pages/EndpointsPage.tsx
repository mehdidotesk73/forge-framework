import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  callStreamingEndpoint,
  ButtonGroup,
  TextInput,
  TextArea,
  RadioGroup,
  Container,
  LogPanel,
} from "@forge-suite/ts";
import type { LogLine } from "@forge-suite/ts";

const RUN_ENDPOINT_BUILD_ID      = "cccccccc-0007-0000-0000-000000000000";
const CREATE_ENDPOINT_ID         = "cccccccc-0018-0000-0000-000000000000";
const CALL_PROJECT_ENDPOINT_ID   = "cccccccc-0026-0000-0000-000000000000";

type ProjectRow      = { id: string; name: string; is_active: string; root_path: string };
type EndpointRepoRow = { id: string; project_id: string; name: string; path: string; endpoint_count: string };
type EndpointRow     = { id: string; project_id: string; repo_name: string; endpoint_id: string; name: string; kind: string; description: string; object_type: string };

type TestState = {
  payload: string;
  loading: boolean;
  response: { status?: number; result?: unknown; error?: unknown } | null;
};

function defaultPayload(kind: string): string {
  if (kind === "computed_attribute") return JSON.stringify({ primary_keys: [""] }, null, 2);
  return "{}";
}

function kindColor(kind: string): string {
  if (kind === "action")          return "var(--accent)";
  if (kind === "streaming")       return "var(--accent-green)";
  if (kind === "computed_attribute") return "var(--accent-purple, #a855f7)";
  return "var(--text-muted)";
}

function ResponseViewer({ resp }: { resp: TestState["response"] }) {
  if (!resp) return null;
  const isError = resp.error !== undefined;
  const content = isError ? resp.error : resp.result;
  const color   = isError ? "var(--accent-red, #f87171)" : "var(--accent-green, #4ade80)";
  const label   = isError
    ? `Error${resp.status ? ` ${resp.status}` : ""}`
    : `${resp.status ?? 200} OK`;
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </div>
      <pre style={{
        margin: 0, padding: "10px 12px", borderRadius: 6,
        background: "var(--bg-hover)", fontSize: 12,
        color: isError ? color : "var(--text)",
        whiteSpace: "pre-wrap", wordBreak: "break-word",
        maxHeight: 320, overflowY: "auto",
        border: `1px solid ${color}44`,
      }}>
        {typeof content === "string" ? content : JSON.stringify(content, null, 2)}
      </pre>
    </div>
  );
}

function EndpointTestPanel({
  endpoint,
  projectId,
  testState,
  onPayloadChange,
  onSend,
}: {
  endpoint: EndpointRow;
  projectId: string;
  testState: TestState;
  onPayloadChange: (v: string) => void;
  onSend: () => void;
}) {
  return (
    <div style={{
      padding: "12px 14px",
      borderTop: "1px solid var(--border)",
      background: "var(--bg-hover)",
    }}>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
        <code style={{ fontSize: 11 }}>{endpoint.endpoint_id}</code>
        {endpoint.description && (
          <span style={{ marginLeft: 8 }}>{endpoint.description}</span>
        )}
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-muted)", marginBottom: 4 }}>
        Request payload (JSON)
        {endpoint.kind === "computed_attribute" && (
          <span style={{ marginLeft: 6, color: "var(--accent-purple, #a855f7)", fontWeight: 400 }}>
            — include <code>primary_keys</code>
          </span>
        )}
      </div>
      <TextArea
        value={testState.payload}
        onChange={onPayloadChange}
        rows={5}
      />
      <Container direction="row" alignItems="center" gap="10px" padding="0" style={{ marginTop: 8 }}>
        <ButtonGroup
          size="sm"
          buttons={[{
            label: testState.loading ? "Sending…" : "Send",
            variant: "primary",
            disabled: testState.loading,
            action: { kind: "ui", handler: onSend },
          }]}
        />
        {testState.loading && (
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Waiting for response…</span>
        )}
      </Container>
      <ResponseViewer resp={testState.response} />
    </div>
  );
}

export function EndpointsPage() {
  const qc = useQueryClient();
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newEndpointName, setNewEndpointName] = useState("");
  const [newRepoName, setNewRepoName] = useState("");
  const [newKind, setNewKind] = useState<"action" | "streaming" | "computed_attribute">("action");
  const [newResult, setNewResult] = useState<{ file?: string; name?: string; repo?: string; error?: string } | null>(null);

  const [testStates, setTestStates] = useState<Record<string, TestState>>({});
  const [openTestId, setOpenTestId] = useState<string | null>(null);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: repoData, refetch } = useQuery({
    queryKey: ["endpoint_repos", active?.id],
    queryFn: () => fetchObjectSet<EndpointRepoRow>("EndpointRepo"),
    enabled: !!active,
    refetchInterval: 5000,
  });
  const repos = (repoData?.rows ?? []).filter((r) => r.project_id === active?.id);

  const { data: endpointData } = useQuery({
    queryKey: ["endpoints", active?.id],
    queryFn: () => fetchObjectSet<EndpointRow>("Endpoint"),
    enabled: !!active,
  });
  const endpoints = (endpointData?.rows ?? []).filter((e) => e.project_id === active?.id);

  function getTestState(ep: EndpointRow): TestState {
    return testStates[ep.id] ?? {
      payload: defaultPayload(ep.kind),
      loading: false,
      response: null,
    };
  }

  function setTestState(epId: string, patch: Partial<TestState>) {
    setTestStates((prev) => ({ ...prev, [epId]: { ...getTestState({ id: epId } as EndpointRow), ...patch } }));
  }

  async function handleSend(ep: EndpointRow) {
    if (!active) return;
    const state = getTestState(ep);
    setTestState(ep.id, { loading: true, response: null });
    try {
      const result = await callEndpoint<{ status?: number; result?: unknown; error?: unknown }>(
        CALL_PROJECT_ENDPOINT_ID,
        {
          project_id: active.id,
          endpoint_id: ep.endpoint_id,
          payload_json: state.payload,
        }
      );
      setTestState(ep.id, { loading: false, response: result ?? null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setTestState(ep.id, { loading: false, response: { error: msg } });
    }
  }

  const handleBuild = () => {
    if (!active || running) return;
    setLogs([]);
    setRunning(true);
    callStreamingEndpoint(
      RUN_ENDPOINT_BUILD_ID,
      { project_id: active.id },
      {
        onEvent: (event, data) => setLogs((prev) => [...prev, { event, data, ts: Date.now() }]),
        onDone: () => { setRunning(false); refetch(); },
        onError: (err) => {
          setLogs((prev) => [...prev, { event: "error", data: err.message, ts: Date.now() }]);
          setRunning(false);
        },
      }
    );
  };

  const createEndpoint = useMutation({
    mutationFn: () =>
      callEndpoint<{ file?: string; name?: string; repo?: string; kind?: string; error?: string }>(
        CREATE_ENDPOINT_ID,
        {
          project_id: active?.id ?? "",
          endpoint_name: newEndpointName,
          repo_name: newRepoName,
          kind: newKind,
        }
      ),
    onSuccess: (result) => {
      if (result?.error) { setNewResult({ error: result.error }); return; }
      setNewResult({ file: result?.file, name: result?.name, repo: result?.repo });
      qc.invalidateQueries({ queryKey: ["endpoint_repos"] });
      qc.invalidateQueries({ queryKey: ["endpoints"] });
      refetch();
    },
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Endpoints</h1>
        {active && (
          <ButtonGroup
            size="sm"
            buttons={[
              {
                label: "+ New Endpoint",
                variant: "primary",
                action: { kind: "ui", handler: () => { setShowNew(true); setNewResult(null); setNewEndpointName(""); setNewRepoName(""); setNewKind("action"); } },
              },
              {
                label: running ? "Building…" : "⚙ Build endpoints",
                disabled: running,
                action: { kind: "ui", handler: handleBuild },
              },
            ]}
          />
        )}
      </div>

      {!active ? (
        <div className="empty-state">No active project.</div>
      ) : (
        <>
          {showNew && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="section-title" style={{ marginBottom: 12 }}>New Endpoint</div>
              {newResult?.file ? (
                <div>
                  <div style={{ color: "var(--accent-green)", marginBottom: 8, fontSize: 13 }}>
                    Endpoint <strong>{newResult.name}</strong> scaffolded in repo <strong>{newResult.repo}</strong>.
                  </div>
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
                <Container direction="column" gap="8px" padding="0" style={{ maxWidth: 420 }}>
                  <TextInput
                    value={newEndpointName}
                    onChange={(v) => { setNewEndpointName(v); setNewResult(null); }}
                    placeholder="endpoint_name (snake_case, e.g. get_summary)"
                  />
                  <TextInput
                    value={newRepoName}
                    onChange={(v) => { setNewRepoName(v); setNewResult(null); }}
                    placeholder="repo_name (existing or new snake_case name)"
                  />
                  <RadioGroup
                    name="endpoint-kind"
                    value={newKind}
                    onChange={(v) => setNewKind(v as "action" | "streaming" | "computed_attribute")}
                    options={[
                      { value: "action", label: "action" },
                      { value: "streaming", label: "streaming" },
                      { value: "computed_attribute", label: "computed_attribute" },
                    ]}
                  />
                  {newResult?.error && (
                    <div style={{ fontSize: 12, color: "var(--accent-red)" }}>{newResult.error}</div>
                  )}
                  <ButtonGroup
                    size="sm"
                    buttons={[
                      { label: createEndpoint.isPending ? "Creating…" : "Create Endpoint", variant: "primary", disabled: !newEndpointName || !newRepoName || createEndpoint.isPending, action: { kind: "ui", handler: () => createEndpoint.mutate() } },
                      { label: "Cancel", action: { kind: "ui", handler: () => { setShowNew(false); setNewResult(null); } } },
                    ]}
                  />
                </Container>
              )}
            </div>
          )}

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="section-title" style={{ marginBottom: 12 }}>Endpoint Repos</div>
            {repos.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px 0" }}>
                No endpoint repos. Sync the project after running <code>forge endpoint build</code>.
              </div>
            ) : (
              <Container direction="column" gap="8px" padding="0">
                {repos.map((repo) => {
                  const repoEndpoints = endpoints.filter((e) => e.repo_name === repo.name);
                  const expanded = expandedRepo === repo.id;
                  return (
                    <div key={repo.id} style={{ border: "1px solid var(--border)", borderRadius: 6 }}>
                      <button
                        style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between",
                          width: "100%", padding: "10px 14px", background: "transparent",
                          border: "none", color: "var(--text)", cursor: "pointer", textAlign: "left",
                        }}
                        onClick={() => setExpandedRepo(expanded ? null : repo.id)}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontWeight: 600 }}>{repo.name}</span>
                          <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{repo.endpoint_count} endpoints</span>
                        </div>
                        <span style={{ color: "var(--text-muted)" }}>{expanded ? "▲" : "▼"}</span>
                      </button>

                      {expanded && (
                        <div style={{ borderTop: "1px solid var(--border)" }}>
                          {repoEndpoints.length === 0 ? (
                            <div style={{ padding: "12px 14px", color: "var(--text-muted)", fontSize: 12 }}>
                              No endpoints found (build first).
                            </div>
                          ) : (
                            <div>
                              {repoEndpoints.map((ep, idx) => {
                                const isLast     = idx === repoEndpoints.length - 1;
                                const testOpen   = openTestId === ep.id;
                                const state      = getTestState(ep);
                                const kColor     = kindColor(ep.kind);
                                return (
                                  <div key={ep.id} style={{ borderBottom: isLast ? "none" : "1px solid var(--border)" }}>
                                    <div style={{
                                      display: "flex", alignItems: "center", justifyContent: "space-between",
                                      padding: "10px 14px",
                                    }}>
                                      <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                                        <span
                                          className="badge"
                                          style={{
                                            background: kColor + "22", color: kColor,
                                            fontSize: 10, fontWeight: 600, padding: "2px 7px",
                                            borderRadius: 4, whiteSpace: "nowrap",
                                          }}
                                        >
                                          {ep.kind}
                                        </span>
                                        <span style={{ fontWeight: 500, fontSize: 13 }}>{ep.name}</span>
                                        {ep.description && (
                                          <span style={{ color: "var(--text-muted)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                            {ep.description}
                                          </span>
                                        )}
                                      </div>
                                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                                        <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>
                                          {ep.endpoint_id.slice(0, 8)}…
                                        </span>
                                        <button
                                          onClick={() => {
                                            if (!testOpen) {
                                              if (!testStates[ep.id]) {
                                                setTestState(ep.id, { payload: defaultPayload(ep.kind), loading: false, response: null });
                                              }
                                            }
                                            setOpenTestId(testOpen ? null : ep.id);
                                          }}
                                          style={{
                                            fontSize: 11, fontWeight: 600, padding: "3px 10px",
                                            borderRadius: 4, cursor: "pointer",
                                            border: `1px solid ${testOpen ? kColor : "var(--border)"}`,
                                            background: testOpen ? kColor + "22" : "transparent",
                                            color: testOpen ? kColor : "var(--text-muted)",
                                            transition: "all 0.15s",
                                          }}
                                        >
                                          {testOpen ? "Close" : "Test"}
                                        </button>
                                      </div>
                                    </div>

                                    {testOpen && (
                                      <EndpointTestPanel
                                        endpoint={ep}
                                        projectId={active.id}
                                        testState={state}
                                        onPayloadChange={(v) => setTestState(ep.id, { payload: v })}
                                        onSend={() => handleSend(ep)}
                                      />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </Container>
            )}
          </div>

          {(logs.length > 0 || running) && (
            <div>
              <div className="section-title" style={{ marginBottom: 8 }}>Build Output</div>
              <LogPanel lines={logs} running={running} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
