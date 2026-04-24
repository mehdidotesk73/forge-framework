import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  Container,
  MetricTile,
  Markdown,
  ButtonGroup,
  Modal,
  TextInput,
} from "@forge-suite/ts";

const HEALTH_ID = "cccccccc-0010-0000-0000-000000000000";
const LIST_MODULES_ID = "cccccccc-0028-0000-0000-000000000000";
const IMPLANT_MODULE_ID = "cccccccc-0031-0000-0000-000000000000";

type ProjectRow = {
  id: string;
  name: string;
  is_active: string;
  root_path: string;
};
type ModuleEntry = {
  name: string;
  package: string;
  version: string;
  config_var: string;
};
type LibraryModule = { id: string; name: string; version: string };
type HealthResult = { modules?: ModuleEntry[]; project_name?: string };

const CLI_REFERENCE = `\
### Add a module
\`\`\`
# From your project directory (venv active):
forge module add <name>

# If the package is already installed:
forge module add <name> --no-install
\`\`\`

### Remove a module
\`\`\`
forge module remove <name>

# Also delete dataset files (destructive):
forge module remove <name> --drop-datasets
\`\`\`

### List configured modules
\`\`\`
forge module list
\`\`\`

### After adding a module
\`\`\`
forge model build       # pick up module models
forge endpoint build    # pick up module endpoints
forge dev serve         # datasets bootstrapped on startup
\`\`\`

### Adopt a standalone Forge project as a module
\`\`\`
# From the forge-framework monorepo root:
forge module adopt /path/to/my-project --name my-module

# Add packaging in-place (no copy):
forge module adopt /path/to/my-project --name my-module --in-place
\`\`\`

### Rebuild the module manifest
\`\`\`
# Run inside the module directory:
forge module build
\`\`\``;

export function ModulesPage() {
  const qc = useQueryClient();
  const [cliOpen, setCliOpen] = React.useState(false);
  const [implantOpen, setImplantOpen] = React.useState(false);
  const [implantModule, setImplantModule] = React.useState("");
  const [implantMsg, setImplantMsg] = React.useState<{
    text: string;
    ok: boolean;
  } | null>(null);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: health, isLoading } = useQuery({
    queryKey: ["project_health_modules", active?.id],
    queryFn: () =>
      callEndpoint<HealthResult>(HEALTH_ID, { project_id: active?.id ?? "" }),
    enabled: !!active,
    refetchInterval: 10000,
  });

  const modules: ModuleEntry[] = health?.modules ?? [];

  const { data: libraryData } = useQuery({
    queryKey: ["library_modules"],
    queryFn: () =>
      callEndpoint<{ modules?: LibraryModule[] }>(LIST_MODULES_ID, {}),
    refetchInterval: 15000,
  });
  const libraryModules: LibraryModule[] = libraryData?.modules ?? [];

  const implant = useMutation({
    mutationFn: ({ module_name }: { module_name: string }) =>
      callEndpoint<{ ok?: boolean; note?: string; error?: string }>(
        IMPLANT_MODULE_ID,
        { project_id: active?.id ?? "", module_name },
      ),
    onSuccess: (result) => {
      if (result?.error) {
        setImplantMsg({ text: result.error, ok: false });
      } else {
        setImplantMsg({
          text: result?.note ?? "Module implanted successfully.",
          ok: true,
        });
        qc.invalidateQueries();
      }
    },
    onError: (err) => {
      setImplantMsg({ text: String(err), ok: false });
    },
  });

  return (
    <>
      <Container
        direction="column"
        gap={20}
        padding={20}
        startChildren={
          <>
            <Container
              direction="column"
              title="Modules"
              titleSize="lg"
              gap={8}
            >
              {active ? (
                <Container
                  direction="column"
                  title={active.root_path}
                  titleSize="md"
                ></Container>
              ) : (
                <Markdown>
                  {
                    "No active project. Register a project from the sidebar to get started."
                  }
                </Markdown>
              )}
            </Container>

            {active && isLoading && <Markdown>{"Loading\u2026"}</Markdown>}

            {active && !isLoading && modules.length > 0 && (
              <Container
                direction="column"
                title={`Active modules \u2014 ${modules.length}`}
                titleSize="md"
                gap={8}
              >
                {modules.map((m) => {
                  const versionOk = m.version && m.version !== "unknown";
                  return (
                    <Container
                      key={m.name}
                      direction="row"
                      variant="card"
                      title={m.name}
                      titleSize="md"
                      gap={16}
                      padding="12px 16px"
                    >
                      <MetricTile label="Package" value={m.package} />
                      <MetricTile
                        label="Version"
                        value={versionOk ? `v${m.version}` : "not installed"}
                      />
                      <MetricTile label="Config" value={m.config_var} />
                    </Container>
                  );
                })}
              </Container>
            )}

            {active && !isLoading && modules.length === 0 && (
              <Container direction="column" variant="panel" padding="16px 20px">
                <Markdown>{"No modules added to this project yet."}</Markdown>
              </Container>
            )}
          </>
        }
        endChildren={
          <ButtonGroup
            buttons={[
              {
                label: "⬡ Implant Module",
                variant: "primary",
                disabled: !active,
                action: {
                  kind: "ui",
                  handler: () => {
                    setImplantModule("");
                    setImplantMsg(null);
                    setImplantOpen(true);
                  },
                },
              },
              {
                label: "CLI Reference",
                variant: "secondary",
                action: { kind: "ui", handler: () => setCliOpen(true) },
              },
            ]}
          />
        }
      />
      <Modal
        open={implantOpen}
        onClose={() => {
          setImplantOpen(false);
          setImplantMsg(null);
        }}
        title="Implant Module"
        size="sm"
      >
        <Container direction="column" gap={12}>
          {libraryModules.length === 0 ? (
            <Markdown>
              {
                "No modules are absorbed yet. Visit **Module Library** to absorb one first."
              }
            </Markdown>
          ) : (
            <>
              <Container direction="column" gap={4}>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  Select a module to add to <strong>{active?.name}</strong>
                </span>
                {libraryModules.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setImplantModule(m.name)}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: `1px solid ${implantModule === m.name ? "var(--accent)" : "var(--border)"}`,
                      background:
                        implantModule === m.name
                          ? "var(--accent-subtle)"
                          : "var(--bg-panel)",
                      color: "var(--text)",
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    {m.name}
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 11,
                        color: "var(--text-muted)",
                      }}
                    >
                      v{m.version}
                    </span>
                  </button>
                ))}
              </Container>
              {implantMsg && (
                <div
                  style={{
                    fontSize: 12,
                    color: implantMsg.ok
                      ? "var(--accent-green)"
                      : "var(--accent-red)",
                    padding: "4px 0",
                  }}
                >
                  {implantMsg.text}
                </div>
              )}
              <ButtonGroup
                size="sm"
                buttons={[
                  {
                    label: implant.isPending ? "Implanting…" : "Implant",
                    variant: "primary",
                    disabled: !implantModule || implant.isPending,
                    action: {
                      kind: "ui",
                      handler: () =>
                        implant.mutate({ module_name: implantModule }),
                    },
                  },
                  {
                    label: "Cancel",
                    action: {
                      kind: "ui",
                      handler: () => {
                        setImplantOpen(false);
                        setImplantMsg(null);
                      },
                    },
                  },
                ]}
              />
            </>
          )}
        </Container>
      </Modal>
      <Modal
        open={cliOpen}
        onClose={() => setCliOpen(false)}
        title="CLI Reference"
        size="lg"
      >
        <Markdown>{CLI_REFERENCE}</Markdown>
      </Modal>
    </>
  );
}
