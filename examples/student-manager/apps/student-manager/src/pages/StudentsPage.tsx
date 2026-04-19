import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ObjectTable,
  ButtonGroup,
  Modal,
  Form,
  Selector,
  MetricTile,
  bindState,
  fetchObjectSet,
  callEndpoint,
  type ForgeObjectSet,
} from "@forge-framework/ts";

const CREATE_STUDENT_ID  = "53d12e07-c589-44cf-98c2-13a7a63c2978";
const COMPUTE_METRICS_ID = "6b379c5c-4c48-4ad0-b8f4-9fa5a7bbffdd";
const CREATE_GRADE_ID    = "ffff3c2b-a56f-466e-9f63-5d557ee2113c";
const EDIT_STUDENT_ID    = "324f7bb6-89fa-412b-a10d-32aa26307863";
const DELETE_STUDENT_ID  = "dbed6a88-cbdc-46b7-8c4f-e1ebb305d06b";
const EDIT_GRADE_ID      = "ecc3bdf3-5e4a-4b5b-8a94-f8049960e531";
const DELETE_GRADE_ID    = "921ef15c-98dd-4dbe-a36a-b437971757d4";

type StudentRow = {
  id: string;
  name: string;
  email: string;
  major: string;
  enrolled_at: string;
  status: string;
};
type GradeRow = {
  id: string;
  student_id: string;
  course: string;
  semester: string;
  grade: string;
  credits: number;
};

const TIMEFRAME_OPTIONS = [
  { value: "all", label: "All Time" },
  { value: "2024-fall", label: "Fall 2024" },
  { value: "2024-spring", label: "Spring 2024" },
  { value: "2023-fall", label: "Fall 2023" },
  { value: "2023-spring", label: "Spring 2023" },
];

type ActiveModal =
  | "create"
  | "edit"
  | "grade"
  | "grades"
  | "confirmDelete"
  | "editGrade"
  | "confirmDeleteGrade"
  | null;

export function StudentsPage() {
  const [modal, setModal] = useState<ActiveModal>(null);
  const [selected, setSelected] = useState<StudentRow | null>(null);
  const [selectedGrade, setSelectedGrade] = useState<GradeRow | null>(null);
  const [timeframe, setTimeframe] = useState("all");
  const [deleting, setDeleting] = useState(false);
  const [deletingGrade, setDeletingGrade] = useState(false);

  const { data, refetch } = useQuery({
    queryKey: ["students"],
    queryFn: () => fetchObjectSet<StudentRow>("Student"),
  });

  const { data: gradeData, refetch: refetchGrades } = useQuery({
    queryKey: ["grades"],
    queryFn: () => fetchObjectSet<GradeRow>("Grade"),
    enabled: modal === "grades" || modal === "editGrade" || modal === "confirmDeleteGrade",
  });

  const objectSet: ForgeObjectSet<StudentRow> | undefined = data
    ? {
        rows: data.rows,
        schema: data.schema as any,
        datasetId: "Student",
        mode: "snapshot",
        total: data.total,
      }
    : undefined;

  const studentGrades: GradeRow[] = gradeData
    ? gradeData.rows.filter((g) => g.student_id === selected?.id)
    : [];

  const gradeObjectSet: ForgeObjectSet<GradeRow> | undefined = gradeData
    ? {
        rows: studentGrades,
        schema: gradeData.schema as any,
        datasetId: "Grade",
        mode: "stream",
        total: studentGrades.length,
      }
    : undefined;

  const handleDelete = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      await callEndpoint(DELETE_STUDENT_ID, { id: selected.id });
      setModal(null);
      setSelected(null);
      refetch();
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteGrade = async () => {
    if (!selectedGrade || !selected) return;
    setDeletingGrade(true);
    try {
      await callEndpoint(DELETE_GRADE_ID, { id: selectedGrade.id, student_id: selected.id });
      setModal("grades");
      setSelectedGrade(null);
      refetchGrades();
    } finally {
      setDeletingGrade(false);
    }
  };

  if (!objectSet)
    return (
      <div style={{ padding: 32, color: "#9898b0" }}>Loading students…</div>
    );

  return (
    <>
      <div className='metrics-row'>
        <MetricTile
          label='Total Students'
          objectSet={objectSet}
          aggregation='count'
        />
        <MetricTile
          label='Active'
          value={objectSet.rows.filter((r) => r.status === "active").length}
        />
        <MetricTile
          label='Graduated'
          value={objectSet.rows.filter((r) => r.status === "graduated").length}
        />
      </div>

      <div className='controls-row'>
        <Selector
          label='GPA Timeframe'
          value={timeframe}
          options={TIMEFRAME_OPTIONS}
          onChange={setTimeframe}
        />
        <ButtonGroup
          buttons={[
            {
              label: "New Student",
              variant: "primary",
              action: {
                kind: "ui",
                handler: () => {
                  setSelected(null);
                  setModal("create");
                },
              },
            },
          ]}
        />
      </div>

      <ObjectTable
        objectSet={objectSet}
        computedColumns={[
          {
            endpointId: COMPUTE_METRICS_ID,
            params: { timeframe: bindState("timeframe") },
          },
        ]}
        localState={{ timeframe }}
        interaction={{
          selectable: "single",
          visibleFields: [
            "id",
            "name",
            "email",
            "major",
            "status",
            "enrolled_at",
          ],
          density: "normal",
          onClick: {
            kind: "ui",
            handler: (item) => setSelected(item as StudentRow),
          },
          contextMenu: [
            {
              label: "View Grades",
              action: {
                kind: "ui",
                handler: (item) => {
                  setSelected(item as StudentRow);
                  setModal("grades");
                },
              },
            },
            {
              label: "Edit Student",
              action: {
                kind: "ui",
                handler: (item) => {
                  setSelected(item as StudentRow);
                  setModal("edit");
                },
              },
            },
            {
              label: "Add Grade",
              action: {
                kind: "ui",
                handler: (item) => {
                  setSelected(item as StudentRow);
                  setModal("grade");
                },
              },
            },
            {
              label: "Delete Student",
              action: {
                kind: "ui",
                handler: (item) => {
                  setSelected(item as StudentRow);
                  setModal("confirmDelete");
                },
              },
            },
          ],
        }}
      />

      <p style={{ fontSize: 12, color: "#5a5a72", marginTop: 8 }}>
        Right-click any row for actions
      </p>

      {/* ── Create student ── */}
      <Modal
        open={modal === "create"}
        onClose={() => setModal(null)}
        title='New Student'
        size='md'
      >
        <Form
          endpointId={CREATE_STUDENT_ID}
          onSuccess={() => {
            setModal(null);
            refetch();
          }}
          submitLabel='Create Student'
        />
      </Modal>

      {/* ── Edit student — form pre-filled with current values ── */}
      <Modal
        open={modal === "edit"}
        onClose={() => setModal(null)}
        title={selected ? `Edit — ${selected.name}` : "Edit Student"}
        size='md'
      >
        <Form
          endpointId={EDIT_STUDENT_ID}
          prefill={selected ?? {}}
          onSuccess={() => {
            setModal(null);
            refetch();
          }}
          submitLabel='Save Changes'
        />
      </Modal>

      {/* ── Add grade ── */}
      <Modal
        open={modal === "grade"}
        onClose={() => setModal(null)}
        title={selected ? `Add Grade — ${selected.name}` : "Add Grade"}
        size='md'
      >
        <Form
          endpointId={CREATE_GRADE_ID}
          prefill={selected ? { student_id: selected.id } : {}}
          onSuccess={() => setModal(null)}
          submitLabel='Save Grade'
        />
      </Modal>

      {/* ── View grades ── */}
      <Modal
        open={modal === "grades"}
        onClose={() => setModal(null)}
        title={selected ? `Grades — ${selected.name}` : "Grades"}
        size='lg'
      >
        {gradeObjectSet && gradeObjectSet.rows.length > 0 ? (
          <ObjectTable
            objectSet={gradeObjectSet}
            interaction={{
              visibleFields: ["course", "semester", "grade", "credits"],
              density: "compact",
              contextMenu: [
                {
                  label: "Edit Grade",
                  action: {
                    kind: "ui",
                    handler: (item) => {
                      setSelectedGrade(item as GradeRow);
                      setModal("editGrade");
                    },
                  },
                },
                {
                  label: "Delete Grade",
                  action: {
                    kind: "ui",
                    handler: (item) => {
                      setSelectedGrade(item as GradeRow);
                      setModal("confirmDeleteGrade");
                    },
                  },
                },
              ],
            }}
          />
        ) : (
          <p
            style={{
              color: "#9898b0",
              fontSize: 14,
              textAlign: "center",
              padding: "24px 0",
            }}
          >
            {gradeData ? "No grades recorded for this student." : "Loading…"}
          </p>
        )}
      </Modal>

      {/* ── Edit grade ── */}
      <Modal
        open={modal === "editGrade"}
        onClose={() => setModal("grades")}
        title={selectedGrade ? `Edit — ${selectedGrade.course}` : "Edit Grade"}
        size='md'
      >
        <Form
          endpointId={EDIT_GRADE_ID}
          prefill={selectedGrade ?? {}}
          onSuccess={() => {
            setModal("grades");
            refetchGrades();
          }}
          submitLabel='Save Changes'
        />
      </Modal>

      {/* ── Confirm delete grade ── */}
      <Modal
        open={modal === "confirmDeleteGrade"}
        onClose={() => setModal("grades")}
        title='Delete Grade'
        size='sm'
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <p style={{ margin: 0, fontSize: 14, color: "#e0e0e8" }}>
            Delete <strong>{selectedGrade?.course}</strong> ({selectedGrade?.semester})? This cannot be undone.
          </p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <ButtonGroup
              buttons={[
                {
                  label: "Cancel",
                  variant: "secondary",
                  action: { kind: "ui", handler: () => setModal("grades") },
                },
              ]}
            />
            <ButtonGroup
              buttons={[
                {
                  label: deletingGrade ? "Deleting…" : "Delete",
                  variant: "danger",
                  disabled: deletingGrade,
                  action: { kind: "ui", handler: handleDeleteGrade },
                },
              ]}
            />
          </div>
        </div>
      </Modal>

      {/* ── Confirm delete ── */}
      <Modal
        open={modal === "confirmDelete"}
        onClose={() => setModal(null)}
        title='Delete Student'
        size='sm'
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <p style={{ margin: 0, fontSize: 14, color: "#e0e0e8" }}>
            Permanently delete <strong>{selected?.name}</strong>? This cannot be
            undone.
          </p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <ButtonGroup
              buttons={[
                {
                  label: "Cancel",
                  variant: "secondary",
                  action: { kind: "ui", handler: () => setModal(null) },
                },
              ]}
            />
            <ButtonGroup
              buttons={[
                {
                  label: deleting ? "Deleting…" : "Delete",
                  variant: "danger",
                  disabled: deleting,
                  action: { kind: "ui", handler: handleDelete },
                },
              ]}
            />
          </div>
        </div>
      </Modal>
    </>
  );
}
