import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  ObjectTable,
  MetricTile,
  Container,
  ButtonGroup,
  createObjectSet,
} from "@forge-framework/ts";
import type { ContextMenuItem } from "@forge-framework/ts";
import type { ForgeSchema } from "@forge-framework/ts";
import { LayerLineage } from "../components/LayerLineage.js";

const SYNC_ID = "cccccccc-0004-0000-0000-000000000000";
const HEALTH_ID = "cccccccc-0010-0000-0000-000000000000";
const LINEAGE_ID = "cccccccc-0009-0000-0000-000000000000";
const UNREGISTER_ID = "cccccccc-0002-0000-0000-000000000000";

type ProjectRow = {
  id: string;
  name: string;
  root_path: string;
  forge_version: string;
  is_active: string;
  registered_at: string;
};
type HealthResult = {
  status: string;
  project_name: string;
  project_id: string;
  pipeline_count: number;
  model_count: number;
  models_built: number;
  repo_count: number;
  endpoint_count: number;
  endpoints_built: boolean;
  run_count: number;
  last_run: string;
  failed_runs: number;
};

const PROJECT_SCHEMA: ForgeSchema = {
  name: "Project",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    name: { type: "string", display: "Name" },
    root_path: { type: "string", display: "Path" },
    forge_version: { type: "string", display: "Version" },
    is_active: { type: "string", display: "Active" },
  },
};

export function OverviewPage() {
  const { data: projectData, refetch: refetchProjects } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
    refetchInterval: 5000,
  });

  const projects = projectData?.rows ?? [];
  const active = projects.find((p) => p.is_active === "true");

  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: ["health", active?.id],
    queryFn: () =>
      callEndpoint<HealthResult>(HEALTH_ID, { project_id: active?.id ?? "" }),
    enabled: !!active,
    refetchInterval: 10000,
  });

  const { data: lineageData } = useQuery({
    queryKey: ["lineage", active?.id],
    queryFn: () =>
      callEndpoint<{
        layers: Array<{
          name: string;
          color: string;
          items: Array<{ label: string; detail: string }>;
        }>;
      }>(LINEAGE_ID, { project_id: active?.id ?? "" }),
    enabled: !!active,
    refetchInterval: 10000,
  });

  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const handleSync = async () => {
    if (!active) return;
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await callEndpoint<{ synced?: string; error?: string }>(SYNC_ID, { project_id: active.id });
      if (res.error) {
        setSyncMsg({ ok: false, text: `Sync failed: ${res.error}` });
      } else {
        setSyncMsg({ ok: true, text: "Project synced." });
        refetchProjects();
        refetchHealth();
      }
    } catch (e: unknown) {
      setSyncMsg({ ok: false, text: `Sync error: ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  };

  const handleUnregister = async (id: string) => {
    if (!confirm("Remove this project?")) return;
    await callEndpoint(UNREGISTER_ID, { project_id: id });
    refetchProjects();
  };

  const projectObjectSet = createObjectSet(
    projects,
    PROJECT_SCHEMA,
    "projects",
    "snapshot",
  );

  return (
    <div className='page'>
      <div className='page-header'>
        <h1 className='page-title'>Overview</h1>
        {active && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {syncMsg && (
              <span style={{ fontSize: 12, color: syncMsg.ok ? "var(--accent)" : "var(--accent-red)" }}>
                {syncMsg.text}
              </span>
            )}
            <ButtonGroup
              size='sm'
              buttons={[
                {
                  label: syncing ? "Syncing…" : "↻ Sync project",
                  variant: "secondary",
                  disabled: syncing,
                  action: { kind: "ui", handler: handleSync },
                },
              ]}
            />
          </div>
        )}
      </div>

      {!active ? (
        <div className='empty-state'>
          <div style={{ marginBottom: 8 }}>No active project.</div>
          <div style={{ fontSize: 12 }}>
            Add a project from the sidebar to get started.
          </div>
        </div>
      ) : (
        <>
          {health && (
            <div className='card' style={{ marginBottom: 20 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 16,
                }}
              >
                <div style={{ fontWeight: 600 }}>{health.project_name}</div>
                <span
                  className={`badge ${health.status === "ok" ? "badge-ok" : health.status === "warn" ? "badge-warn" : "badge-error"}`}
                >
                  {health.status}
                </span>
              </div>
              <Container layout='grid' columns={3} gap='12px' padding='0'>
                <MetricTile label='Pipelines' value={health.pipeline_count} />
                <MetricTile
                  label='Models Built'
                  value={`${health.models_built}/${health.model_count}`}
                />
                <MetricTile label='Endpoints' value={health.endpoint_count} />
                <MetricTile label='Runs' value={health.run_count} />
                <MetricTile label='Failed Runs' value={health.failed_runs} />
                <MetricTile
                  label='Last Run'
                  value={
                    health.last_run
                      ? health.last_run.slice(0, 19).replace("T", " ")
                      : "—"
                  }
                />
              </Container>
            </div>
          )}

          <div className='card' style={{ marginBottom: 20 }}>
            <div className='section-title' style={{ marginBottom: 16 }}>
              Layer Lineage
            </div>
            <LayerLineage layers={lineageData?.layers ?? []} />
          </div>
        </>
      )}

      <div className='card'>
        <div className='section-title' style={{ marginBottom: 12 }}>
          Registered Projects
        </div>
        {projects.length === 0 ? (
          <div className='empty-state' style={{ padding: "24px 0" }}>
            No projects registered.
          </div>
        ) : (
          <ObjectTable
            objectSet={projectObjectSet}
            interaction={{
              visibleFields: ["name", "root_path", "forge_version", "is_active"],
              contextMenu: (row): ContextMenuItem[] => [
                {
                  label: "Offload project",
                  action: { kind: "ui", handler: () => handleUnregister(row.id as string) },
                },
              ],
            }}
            renderCell={(field, value) => {
              if (field === "root_path")
                return <span className='mono' style={{ color: "var(--text-muted)" }}>{String(value ?? "")}</span>;
              if (field === "forge_version")
                return <span className='mono'>{String(value || "—")}</span>;
              if (field === "is_active")
                return value === "true"
                  ? <span className='badge badge-ok'>active</span>
                  : <span style={{ color: "var(--text-muted)", fontSize: 12 }}>—</span>;
              if (field === "name")
                return <span style={{ fontWeight: 500 }}>{String(value ?? "")}</span>;
              return null;
            }}
          />
        )}
      </div>
    </div>
  );
}
