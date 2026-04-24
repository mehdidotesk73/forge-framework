import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  Container,
  Navbar,
  Modal,
  TextInput,
  ButtonGroup,
} from "@forge-suite/ts";
import type { Page } from "../App.js";

const GET_DOCS_ID = "cccccccc-0019-0000-0000-000000000000";
const REGISTER_ID = "cccccccc-0001-0000-0000-000000000000";
const SET_ACTIVE_ID = "cccccccc-0003-0000-0000-000000000000";
const SYNC_ID = "cccccccc-0004-0000-0000-000000000000";

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: "◈" },
  { id: "pipelines", label: "Pipelines", icon: "⟶" },
  { id: "model", label: "Model", icon: "⬡" },
  { id: "endpoints", label: "Endpoints", icon: "⚡" },
  { id: "apps", label: "Apps", icon: "▣" },
  { id: "modules", label: "Modules", icon: "⬡" },
  { id: "datasets", label: "Datasets", icon: "⊞" },
  { id: "files", label: "Files", icon: "◻" },
] as const;

interface Props {
  activePage: Page;
  onNavigate: (p: Page) => void;
}

export function Sidebar({ activePage, onNavigate }: Props) {
  const qc = useQueryClient();
  const [registerPath, setRegisterPath] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const [registerMsg, setRegisterMsg] = useState<{
    text: string;
    ok: boolean;
  } | null>(null);
  const [uuidModal, setUuidModal] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [docsOpen, setDocsOpen] = useState(false);
  const [docsTab, setDocsTab] = useState(0);
  const [syncing, setSyncing] = useState(false);

  function generateUuid(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function handleCopy(uuid: string) {
    navigator.clipboard.writeText(uuid).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const { data } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () =>
      fetchObjectSet<{ id: string; name: string; is_active: string }>(
        "ForgeProject",
      ),
    refetchInterval: 5000,
  });

  const projects = (data?.rows ?? []) as Array<{
    id: string;
    name: string;
    is_active: string;
  }>;
  const active = projects.find((p) => p.is_active === "true");

  const setActive = useMutation({
    mutationFn: (project_id: string) =>
      callEndpoint(SET_ACTIVE_ID, { project_id }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const handleSync = async () => {
    if (!active || syncing) return;
    setSyncing(true);
    try {
      await callEndpoint(SYNC_ID, { project_id: active.id });
      qc.invalidateQueries();
    } finally {
      setSyncing(false);
    }
  };

  const { data: docsData } = useQuery({
    queryKey: ["forge_docs"],
    queryFn: () =>
      callEndpoint<{
        docs?: Array<{ name: string; title: string; content: string }>;
        error?: string;
      }>(GET_DOCS_ID, {}),
    enabled: docsOpen,
    staleTime: Infinity,
  });
  const docs = docsData?.docs ?? [];

  const register = useMutation({
    mutationFn: (root_path: string) => callEndpoint(REGISTER_ID, { root_path }),
    onSuccess: (result: unknown) => {
      const r = result as Record<string, unknown>;
      if (r?.error) {
        setRegisterMsg({ text: String(r.error), ok: false });
      } else {
        qc.invalidateQueries();
        setRegisterPath("");
        setShowRegister(false);
        setRegisterMsg(null);
      }
    },
    onError: (err: unknown) => {
      setRegisterMsg({ text: String(err), ok: false });
    },
  });

  return (
    <>
      <Container
        direction="column"
        size="220px"
        separator
        style={{
          minHeight: "100vh",
          background: "var(--bg-panel)",
          borderRight: "1px solid var(--border)",
        }}
        startChildren={
          <>
            {/* Logo */}
            <Container direction="row" gap={8} padding="18px 16px 14px">
              <span style={{ fontSize: 18, color: "var(--accent)" }}>◈</span>
              <span style={{ fontWeight: 700, fontSize: 15 }}>Forge</span>
            </Container>

            {/* Project section */}
            <Container
              direction="column"
              padding="0 16px 8px"
              title="Project"
              titleSize="sm"
            >
              {projects.length === 0 ? null : (
                <Navbar
                  orientation="vertical"
                  size="sm"
                  items={projects.map((p) => ({
                    id: p.id,
                    label: p.name,
                    active: p.is_active === "true",
                    onClick: () => setActive.mutate(p.id),
                  }))}
                />
              )}
              {showRegister ? (
                <Container direction="column" gap={4} padding="4px 12px 0">
                  <TextInput
                    value={registerPath}
                    onChange={(v) => {
                      setRegisterPath(v);
                      setRegisterMsg(null);
                    }}
                    placeholder="Absolute path (created if new)"
                  />
                  {registerMsg && (
                    <div
                      style={{
                        fontSize: 11,
                        color: registerMsg.ok
                          ? "var(--accent-green)"
                          : "var(--accent-red)",
                        padding: "2px 0",
                      }}
                    >
                      {registerMsg.text}
                    </div>
                  )}
                  <ButtonGroup
                    size="sm"
                    buttons={[
                      {
                        label: register.isPending ? "…" : "Create / Register",
                        variant: "primary",
                        disabled: !registerPath || register.isPending,
                        action: {
                          kind: "ui",
                          handler: () => register.mutate(registerPath),
                        },
                      },
                      {
                        label: "✕",
                        action: {
                          kind: "ui",
                          handler: () => {
                            setShowRegister(false);
                            setRegisterMsg(null);
                          },
                        },
                      },
                    ]}
                  />
                </Container>
              ) : (
                <Container padding="4px 12px 0">
                  <ButtonGroup
                    size="sm"
                    buttons={[
                      {
                        label: "+ Add project",
                        action: {
                          kind: "ui",
                          handler: () => setShowRegister(true),
                        },
                      },
                    ]}
                  />
                </Container>
              )}
            </Container>

            {/* Main nav */}
            <Navbar
              orientation="vertical"
              items={NAV_ITEMS.map((item) => ({
                id: item.id,
                label: item.label,
                icon: item.icon,
                active: activePage === item.id,
                onClick: () => onNavigate(item.id as Page),
              }))}
              style={{ padding: "4px 0" }}
            />
          </>
        }
        endChildren={
          <>
            {/* Active project label */}
            {active && (
              <Container
                direction="row"
                startChildren={
                  <Container direction="column" gap={6} padding="10px 16px">
                    <span
                      style={{
                        color: "var(--accent-green)",
                        fontWeight: 600,
                        fontSize: 11,
                      }}
                    >
                      ● Active
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        color: "var(--text-muted)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {active.name}
                    </span>
                  </Container>
                }
                endChildren={
                  <ButtonGroup
                    size="sm"
                    buttons={[
                      {
                        label: syncing ? "Syncing…" : "↻ Sync",
                        variant: "ghost",
                        disabled: syncing,
                        action: { kind: "ui", handler: handleSync },
                      },
                    ]}
                  />
                }
              ></Container>
            )}

            {/* Utility buttons */}
            <Container padding="10px 16px">
              <ButtonGroup
                size="sm"
                buttons={[
                  {
                    label: "# UUID",
                    variant: "ghost",
                    action: {
                      kind: "ui",
                      handler: () => {
                        setUuidModal(generateUuid());
                        setCopied(false);
                      },
                    },
                  },
                  {
                    label: "? Docs",
                    variant: "ghost",
                    action: {
                      kind: "ui",
                      handler: () => {
                        setDocsOpen(true);
                        setDocsTab(0);
                      },
                    },
                  },
                ]}
              />
            </Container>
          </>
        }
      />

      {/* Docs modal */}
      <Modal
        open={docsOpen}
        onClose={() => setDocsOpen(false)}
        title="Forge Docs"
        size="lg"
      >
        {docs.length === 0 ? (
          <Container padding={24}>
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
              Loading…
            </span>
          </Container>
        ) : (
          <Container
            direction="row"
            style={{ flex: 1, overflow: "hidden", height: "100%" }}
          >
            <Container
              direction="column"
              size="160px"
              gap={2}
              padding="10px 8px"
              style={{ borderRight: "1px solid var(--border)" }}
            >
              {docs.map((doc, i) => (
                <button
                  key={doc.name}
                  onClick={() => setDocsTab(i)}
                  style={{
                    textAlign: "left",
                    padding: "6px 10px",
                    borderRadius: 5,
                    border: "none",
                    background:
                      docsTab === i ? "var(--bg-hover)" : "transparent",
                    color: docsTab === i ? "var(--text)" : "var(--text-muted)",
                    fontSize: 12,
                    fontWeight: docsTab === i ? 600 : 400,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {doc.name}
                </button>
              ))}
            </Container>
            <Container
              size={1}
              padding="20px 24px"
              style={{ overflow: "auto" }}
            >
              {docs[docsTab] && (
                <pre
                  style={{
                    margin: 0,
                    fontFamily: "monospace",
                    fontSize: 12,
                    lineHeight: 1.65,
                    color: "var(--text)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {docs[docsTab].content}
                </pre>
              )}
            </Container>
          </Container>
        )}
      </Modal>

      {/* UUID modal */}
      <Modal
        open={!!uuidModal}
        onClose={() => setUuidModal(null)}
        title="Generated UUID"
        size="sm"
      >
        <Container direction="column" gap={16}>
          <code
            style={{
              fontSize: 13,
              background: "var(--bg-hover)",
              padding: "10px 12px",
              borderRadius: 6,
              letterSpacing: "0.04em",
              userSelect: "all",
            }}
          >
            {uuidModal}
          </code>
          <ButtonGroup
            size="sm"
            buttons={[
              {
                label: copied ? "Copied!" : "Copy to clipboard",
                variant: "primary",
                action: { kind: "ui", handler: () => handleCopy(uuidModal!) },
              },
              {
                label: "Regenerate",
                action: {
                  kind: "ui",
                  handler: () => {
                    setUuidModal(generateUuid());
                    setCopied(false);
                  },
                },
              },
              {
                label: "✕",
                action: { kind: "ui", handler: () => setUuidModal(null) },
              },
            ]}
          />
        </Container>
      </Modal>
    </>
  );
}
