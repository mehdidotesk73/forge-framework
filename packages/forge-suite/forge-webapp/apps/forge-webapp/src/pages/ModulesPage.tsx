import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  Container,
  MetricTile,
  Markdown,
  ButtonGroup,
  Modal,
} from "@forge-suite/ts";

const HEALTH_ID = "cccccccc-0010-0000-0000-000000000000";

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
  const [cliOpen, setCliOpen] = React.useState(false);

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
                label: "CLI Reference",
                variant: "secondary",
                action: { kind: "ui", handler: () => setCliOpen(true) },
              },
            ]}
          />
        }
      />
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
