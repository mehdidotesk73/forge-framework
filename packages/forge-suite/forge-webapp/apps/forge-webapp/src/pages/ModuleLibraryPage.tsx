import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  ObjectTable,
  Container,
  Markdown,
  ButtonGroup,
  TextInput,
  Modal,
} from "@forge-suite/ts";
import type { InteractionConfig, ForgeObjectSet } from "@forge-suite/ts";

const ABSORB_MODULE_ID = "cccccccc-0029-0000-0000-000000000000";
const SHED_MODULE_ID = "cccccccc-0030-0000-0000-000000000000";

type LibModule = {
  id: string;
  name: string;
  package: string;
  version: string;
  source_path: string;
  namespace_path: string;
  absorbed_at: string;
  description: string;
};

export function ModuleLibraryPage() {
  const qc = useQueryClient();

  const [absorbOpen, setAbsorbOpen] = React.useState(false);
  const [absorbPath, setAbsorbPath] = React.useState("");
  const [absorbName, setAbsorbName] = React.useState("");
  const [absorbDesc, setAbsorbDesc] = React.useState("");
  const [absorbMsg, setAbsorbMsg] = React.useState<{
    text: string;
    ok: boolean;
  } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["library_modules"],
    queryFn: () => fetchObjectSet<LibModule>("ForgeModule"),
    refetchInterval: 15000,
  });
  const objectSet: ForgeObjectSet<LibModule> = (data ?? {
    rows: [],
    total: 0,
    schema: { name: "", mode: "snapshot", primary_key: null, fields: {} },
    datasetId: "",
    mode: "snapshot",
  }) as ForgeObjectSet<LibModule>;

  const shed = useMutation({
    mutationFn: (module_id: string) =>
      callEndpoint<{ ok?: boolean; error?: string }>(SHED_MODULE_ID, {
        module_id,
        drop_datasets: false,
      }),
    onSuccess: (result) => {
      if (result?.error) {
        alert(`Remove failed: ${result.error}`);
      } else {
        qc.invalidateQueries({ queryKey: ["library_modules"] });
      }
    },
    onError: (err) => alert(`Remove failed: ${String(err)}`),
  });

  const absorb = useMutation({
    mutationFn: ({
      source_path,
      name,
      description,
    }: {
      source_path: string;
      name: string;
      description: string;
    }) =>
      callEndpoint<{ ok?: boolean; id?: string; error?: string }>(
        ABSORB_MODULE_ID,
        { source_path, name, description },
      ),
    onSuccess: (result) => {
      if (result?.error) {
        setAbsorbMsg({ text: result.error, ok: false });
      } else {
        setAbsorbMsg({ text: "Module absorbed successfully.", ok: true });
        setAbsorbPath("");
        setAbsorbName("");
        setAbsorbDesc("");
        qc.invalidateQueries({ queryKey: ["library_modules"] });
      }
    },
    onError: (err) => setAbsorbMsg({ text: String(err), ok: false }),
  });

  const interaction: InteractionConfig<LibModule> = {
    visibleFields: ["name", "package", "version", "description", "absorbed_at"],
    contextMenu: (row) => [
      {
        label: "Remove module",
        action: {
          kind: "ui",
          handler: () => shed.mutate(row.id),
        },
      },
    ],
  };

  return (
    <>
      <Modal
        open={absorbOpen}
        onClose={() => {
          setAbsorbOpen(false);
          setAbsorbMsg(null);
        }}
        title="Absorb Module"
      >
        <Container direction="column" gap={10} padding="0">
          <TextInput
            label="Source path"
            value={absorbPath}
            onChange={(v) => {
              setAbsorbPath(v);
              setAbsorbMsg(null);
            }}
            placeholder="Absolute path to the Forge project"
          />
          <TextInput
            label="Name (optional)"
            value={absorbName}
            onChange={setAbsorbName}
            placeholder="Inferred from forge.toml if omitted"
          />
          <TextInput
            label="Description (optional)"
            value={absorbDesc}
            onChange={setAbsorbDesc}
            placeholder=""
          />
          {absorbMsg && (
            <div
              style={{
                fontSize: 12,
                color: absorbMsg.ok
                  ? "var(--accent-green)"
                  : "var(--accent-red)",
                padding: "2px 0",
              }}
            >
              {absorbMsg.text}
            </div>
          )}
          <ButtonGroup
            size="sm"
            buttons={[
              {
                label: absorb.isPending ? "Absorbing..." : "Absorb",
                variant: "primary",
                disabled: !absorbPath || absorb.isPending,
                action: {
                  kind: "ui",
                  handler: () =>
                    absorb.mutate({
                      source_path: absorbPath,
                      name: absorbName,
                      description: absorbDesc,
                    }),
                },
              },
            ]}
          />
        </Container>
      </Modal>

      <Container direction="column" gap={20} padding={20}>
        <Container
          direction="column"
          title="Module Library"
          titleSize="lg"
          gap={8}
          headerRight={
            <ButtonGroup
              size="sm"
              buttons={[
                {
                  label: "+ Absorb Module",
                  variant: "primary",
                  action: {
                    kind: "ui",
                    handler: () => {
                      setAbsorbPath("");
                      setAbsorbName("");
                      setAbsorbDesc("");
                      setAbsorbMsg(null);
                      setAbsorbOpen(true);
                    },
                  },
                },
              ]}
            />
          }
        >
          {isLoading && <Markdown>{"Loading..."}</Markdown>}

          {!isLoading && (objectSet.rows?.length ?? 0) === 0 && (
            <Container direction="column" variant="panel" padding="16px 20px">
              <Markdown>
                {
                  "No modules absorbed yet.\n\nUse **+ Absorb Module** to add a Forge project as a reusable module."
                }
              </Markdown>
            </Container>
          )}

          {!isLoading && (objectSet.rows?.length ?? 0) > 0 && (
            <ObjectTable objectSet={objectSet} interaction={interaction} />
          )}
        </Container>
      </Container>
    </>
  );
}
