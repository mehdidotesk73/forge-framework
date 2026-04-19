import React, { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchObjectSet, callEndpoint, ObjectTable, ButtonGroup, Container, createObjectSet } from "@forge-framework/ts";
import type { ContextMenuItem } from "@forge-framework/ts";
import type { ForgeSchema } from "@forge-framework/ts";

const SYNC_FILES_ID  = "cccccccc-0012-0000-0000-000000000000";
const UPLOAD_FILE_ID = "cccccccc-0013-0000-0000-000000000000";
const REMOVE_FILE_ID = "cccccccc-0014-0000-0000-000000000000";

type ProjectRow = { id: string; name: string; is_active: string };
type FileRow = { id: string; project_id: string; filename: string; size_bytes: string; added_at: string };

function formatBytes(bytes: string): string {
  const n = parseInt(bytes, 10);
  if (isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const FILE_SCHEMA: ForgeSchema = {
  name: "ProjectFile",
  mode: "snapshot",
  primary_key: "id",
  fields: {
    filename:   { type: "string",   display: "Filename" },
    size_bytes: { type: "string",   display: "Size" },
    added_at:   { type: "datetime", display: "Added" },
  },
};

export function FilesPage() {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: projectData } = useQuery({
    queryKey: ["forge_projects"],
    queryFn: () => fetchObjectSet<ProjectRow>("ForgeProject"),
  });
  const active = (projectData?.rows ?? []).find((p) => p.is_active === "true");

  const { data: filesData } = useQuery({
    queryKey: ["project_files", active?.id],
    queryFn: async () => {
      await callEndpoint(SYNC_FILES_ID, { project_id: active?.id ?? "" });
      return fetchObjectSet<FileRow>("ProjectFile");
    },
    enabled: !!active,
  });
  const files = (filesData?.rows ?? []).filter((f) => f.project_id === active?.id);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const buf = await file.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      const b64 = btoa(binary);
      return callEndpoint<{ filename?: string; error?: string }>(UPLOAD_FILE_ID, {
        project_id: active?.id ?? "",
        filename: file.name,
        content_b64: b64,
      });
    },
    onSuccess: (result) => {
      if (result?.error) {
        setUploadError(result.error);
      } else {
        setUploadError(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        qc.invalidateQueries({ queryKey: ["project_files"] });
      }
    },
    onError: (err: unknown) => setUploadError(String(err)),
  });

  const remove = useMutation({
    mutationFn: (file_id: string) =>
      callEndpoint(REMOVE_FILE_ID, { project_id: active?.id ?? "", file_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project_files"] }),
  });

  const objectSet = createObjectSet(files, FILE_SCHEMA, "project-files", "snapshot");

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Files</h1>
        {active && (
          <Container direction="row" alignItems="center" gap="8px" padding="0">
            {uploadError && (
              <span style={{ fontSize: 12, color: "var(--accent-red)" }}>{uploadError}</span>
            )}
            <ButtonGroup
              size="sm"
              buttons={[{
                label: upload.isPending ? "Uploading…" : "+ Upload File",
                variant: "primary",
                disabled: upload.isPending,
                action: { kind: "ui", handler: () => { setUploadError(null); fileInputRef.current?.click(); } },
              }]}
            />
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: "none" }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); }}
            />
          </Container>
        )}
      </div>

      {!active ? (
        <div className="empty-state">No active project.</div>
      ) : files.length === 0 ? (
        <div className="empty-state">No files yet. Upload a file to get started.</div>
      ) : (
        <div className="card">
          <ObjectTable
            objectSet={objectSet}
            interaction={{
              visibleFields: ["filename", "size_bytes", "added_at"],
              contextMenu: (row): ContextMenuItem[] => [
                {
                  label: "Remove",
                  disabled: remove.isPending,
                  action: { kind: "ui", handler: () => { if (confirm(`Remove "${row.filename}"?`)) remove.mutate(row.id as string); } },
                },
              ],
            }}
            renderCell={(field, value) => {
              if (field === "size_bytes") return <span className="mono" style={{ color: "var(--text-muted)" }}>{formatBytes(String(value ?? ""))}</span>;
              if (field === "added_at") return <span className="mono" style={{ color: "var(--text-muted)" }}>{value ? String(value).slice(0, 19).replace("T", " ") : "—"}</span>;
              if (field === "filename") return <span style={{ fontWeight: 500 }}>{String(value ?? "")}</span>;
              return null;
            }}
          />
        </div>
      )}
    </div>
  );
}
