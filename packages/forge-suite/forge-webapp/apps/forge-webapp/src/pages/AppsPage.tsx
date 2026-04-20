import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  ButtonGroup,
  TextInput,
  Container,
} from "@forge-suite/ts";

const CREATE_APP_ID = "cccccccc-0020-0000-0000-000000000000";
const RUN_APP_ID = "cccccccc-0021-0000-0000-000000000000";
const STOP_APP_ID = "cccccccc-0022-0000-0000-000000000000";
const OPEN_APP_ID = "cccccccc-0023-0000-0000-000000000000";
const PING_APP_ID = "cccccccc-0024-0000-0000-000000000000";
const OPEN_IN_VSCODE_ID = "cccccccc-0017-0000-0000-000000000000";

type ProjectRow = {
  id: string;
  name: string;
  is_active: string;
  root_path: string;
};
type AppRow = {
  id: string;
  project_id: string;
  name: string;
  app_id: string;
  path: string;
  port: string;
};
type PingResult = { live: boolean; port?: number };

export function AppsPage() {
  const qc = useQueryClient();
  const [runningApps, setRunningApps] = useState<Set<string>>(new Set());
  const [appLive, setAppLive] = useState<Record<string, PingResult>>({});
  const [appErrors, setAppErrors] = useState<Record<string, string>>({});
  const [fastPolling, setFastPolling] = useState<Set<string>>(new Set());
  const [showNew, setShowNew] = useState(false);
  const [newAppName, setNewAppName] = useState("");
  const [newResult, setNewResult] = useState<{
    path?: string;
    name?: string;
    port?: string;
    error?: string;
  } | null>(null);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: appData } = useQuery({
    queryKey: ["apps", active?.id],
    queryFn: () => fetchObjectSet<AppRow>("App"),
    enabled: !!active,
    refetchInterval: 10000,
  });
  const apps = (appData?.rows ?? []).filter((a) => a.project_id === active?.id);

  useEffect(() => {
    if (apps.length === 0 || !active) return;
    function checkAll() {
      apps.forEach((app) => {
        callEndpoint<PingResult>(PING_APP_ID, {
          project_id: active!.id,
          app_name: app.name,
        })
          .then((res) =>
            setAppLive((prev) => ({
              ...prev,
              [app.id]: res ?? { live: false },
            })),
          )
          .catch(() =>
            setAppLive((prev) => ({ ...prev, [app.id]: { live: false } })),
          );
      });
    }
    checkAll();
    const id = setInterval(checkAll, 5000);
    return () => clearInterval(id);
  }, [apps.map((a) => a.id).join(","), active?.id]);

  useEffect(() => {
    if (fastPolling.size === 0 || !active) return;
    const id = setInterval(() => {
      fastPolling.forEach((appId) => {
        const app = apps.find((a) => a.id === appId);
        if (!app) return;
        callEndpoint<PingResult>(PING_APP_ID, {
          project_id: active!.id,
          app_name: app.name,
        })
          .then((res) => {
            const result = res ?? { live: false };
            setAppLive((prev) => ({ ...prev, [appId]: result }));
            if (result.live)
              setFastPolling((s) => {
                const n = new Set(s);
                n.delete(appId);
                return n;
              });
          })
          .catch(() => {});
      });
    }, 600);
    return () => clearInterval(id);
  }, [fastPolling.size, apps.map((a) => a.id).join(","), active?.id]);

  const createApp = useMutation({
    mutationFn: () =>
      callEndpoint<{
        path?: string;
        name?: string;
        port?: string;
        error?: string;
      }>(CREATE_APP_ID, { project_id: active?.id ?? "", app_name: newAppName }),
    onSuccess: (result) => {
      if (result?.error) {
        setNewResult({ error: result.error });
        return;
      }
      setNewResult({
        path: result?.path,
        name: result?.name,
        port: result?.port,
      });
      qc.invalidateQueries({ queryKey: ["apps"] });
    },
  });

  return (
    <div className='page'>
      <div className='page-header'>
        <h1 className='page-title'>Apps</h1>
        {active && (
          <ButtonGroup
            size='sm'
            buttons={[
              {
                label: "+ New App",
                variant: "primary",
                action: {
                  kind: "ui",
                  handler: () => {
                    setShowNew(true);
                    setNewResult(null);
                    setNewAppName("");
                  },
                },
              },
            ]}
          />
        )}
      </div>

      {!active ? (
        <div className='empty-state'>No active project.</div>
      ) : (
        <>
          {showNew && (
            <div className='card' style={{ marginBottom: 20 }}>
              <div className='section-title' style={{ marginBottom: 12 }}>
                New App
              </div>
              {newResult?.path ? (
                <div>
                  <div
                    style={{
                      color: "var(--accent-green)",
                      marginBottom: 8,
                      fontSize: 13,
                    }}
                  >
                    App <strong>{newResult.name}</strong> scaffolded on port{" "}
                    <strong>{newResult.port}</strong>.
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      marginBottom: 4,
                    }}
                  >
                    To start the dev server:
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
                    cd "{newResult.path}" && npm install && npm run dev
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
                <Container
                  direction='column'
                  gap='8px'
                  padding='0'
                  style={{ maxWidth: 420 }}
                >
                  <TextInput
                    placeholder='app-name (kebab-case, e.g. my-dashboard)'
                    value={newAppName}
                    onChange={(v) => {
                      setNewAppName(v);
                      setNewResult(null);
                    }}
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
                        label: createApp.isPending ? "Creating…" : "Create App",
                        variant: "primary",
                        disabled: !newAppName || createApp.isPending,
                        action: {
                          kind: "ui",
                          handler: () => createApp.mutate(),
                        },
                      },
                      {
                        label: "Cancel",
                        action: {
                          kind: "ui",
                          handler: () => {
                            setShowNew(false);
                            setNewResult(null);
                            setNewAppName("");
                          },
                        },
                      },
                    ]}
                  />
                </Container>
              )}
            </div>
          )}

          {apps.length === 0 ? (
            <div className='empty-state'>
              <div style={{ marginBottom: 8 }}>No apps registered.</div>
              <div style={{ fontSize: 12 }}>
                Create one above or declare apps in <code>forge.toml</code> and
                sync.
              </div>
            </div>
          ) : (
            <Container layout='grid' columns={2} gap='16px' padding='0'>
              {apps.map((app) => {
                const appDir = `${active!.root_path}/${app.path.replace(/^\.\//, "")}`;
                const isRunning = runningApps.has(app.id);
                const pingResult = appLive[app.id];
                const isLive = pingResult?.live === true;
                const livePort = pingResult?.port;
                const appError = appErrors[app.id];
                return (
                  <div
                    key={app.id}
                    className='card'
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    <Container>
                      <Container
                        direction='row'
                        gap='8px'
                        padding='0'
                        alignItems='left'
                      >
                        <div style={{ fontWeight: 700, fontSize: 16 }}>
                          {app.name}
                        </div>
                        <span
                          title={
                            isLive
                              ? "Server is running"
                              : "Server is not running"
                          }
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            flexShrink: 0,
                            background: isLive
                              ? "var(--accent-green)"
                              : "var(--text-muted)",
                            boxShadow: isLive
                              ? "0 0 6px var(--accent-green)"
                              : "none",
                          }}
                        />
                      </Container>
                      <span className='badge badge-ok'>app</span>
                    </Container>

                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <Row label='ID' value={app.app_id} mono />
                      <Row label='Path' value={app.path} mono />
                      <Row
                        label='Port'
                        value={
                          isLive && livePort
                            ? String(livePort)
                            : app.port || "—"
                        }
                        mono
                      />
                      {isLive && livePort && (
                        <Row
                          label='URL'
                          value={`http://localhost:${livePort}`}
                          mono
                        />
                      )}
                    </div>

                    <ButtonGroup
                      size='sm'
                      buttons={[
                        {
                          label: "Open ↗",
                          variant: "primary" as const,
                          disabled: !isLive,
                          action: {
                            kind: "ui" as const,
                            handler: () =>
                              callEndpoint(OPEN_APP_ID, {
                                project_id: active!.id,
                                app_name: app.name,
                              }),
                          },
                        },
                        ...(!isLive
                          ? [
                              {
                                label: isRunning ? "Starting…" : "▶ Run",
                                disabled: isRunning,
                                action: {
                                  kind: "ui" as const,
                                  handler: () => {
                                    setRunningApps((s) =>
                                      new Set(s).add(app.id),
                                    );
                                    setAppErrors((e) => {
                                      const n = { ...e };
                                      delete n[app.id];
                                      return n;
                                    });
                                    callEndpoint<{
                                      ok?: boolean;
                                      error?: string;
                                    }>(RUN_APP_ID, {
                                      project_id: active!.id,
                                      app_name: app.name,
                                    })
                                      .then((res) => {
                                        if (res?.error)
                                          setAppErrors((e) => ({
                                            ...e,
                                            [app.id]: res.error!,
                                          }));
                                        else
                                          setFastPolling((s) =>
                                            new Set(s).add(app.id),
                                          );
                                      })
                                      .catch((err) =>
                                        setAppErrors((e) => ({
                                          ...e,
                                          [app.id]: String(err),
                                        })),
                                      )
                                      .finally(() =>
                                        setRunningApps((s) => {
                                          const n = new Set(s);
                                          n.delete(app.id);
                                          return n;
                                        }),
                                      );
                                  },
                                },
                              },
                            ]
                          : [
                              {
                                label: "■ Stop",
                                variant: "danger" as const,
                                action: {
                                  kind: "ui" as const,
                                  handler: () =>
                                    callEndpoint(STOP_APP_ID, {
                                      project_id: active!.id,
                                      app_name: app.name,
                                    }),
                                },
                              },
                            ]),
                        {
                          label: "</> Code",
                          action: {
                            kind: "ui" as const,
                            handler: () =>
                              callEndpoint(OPEN_IN_VSCODE_ID, {
                                folder_path: appDir,
                                file_path: `${appDir}/src/App.tsx`,
                              }),
                          },
                        },
                      ]}
                    />
                    {appError && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--accent-red)",
                          marginTop: 2,
                        }}
                      >
                        {appError}
                      </div>
                    )}
                  </div>
                );
              })}
            </Container>
          )}
        </>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      <span
        style={{
          width: 48,
          flexShrink: 0,
          color: "var(--text-muted)",
          fontSize: 12,
        }}
      >
        {label}
      </span>
      <span
        className={mono ? "mono" : undefined}
        style={{ color: "var(--text)", fontSize: 12, wordBreak: "break-all" }}
      >
        {value}
      </span>
    </div>
  );
}
