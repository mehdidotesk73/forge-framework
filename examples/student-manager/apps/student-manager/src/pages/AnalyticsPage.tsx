import React, { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Chart, MetricTile, ObjectTable, type ForgeObjectSet , fetchObjectSet } from "@forge-suite/ts";


type StudentRow = { id: string; name: string; major: string; status: string; enrolled_at: string; };
type GradeRow   = { id: string; student_id: string; course: string; semester: string; grade: string; credits: number; };

export function AnalyticsPage() {
  const { data: studentData } = useQuery({ queryKey: ["students"], queryFn: () => fetchObjectSet<StudentRow>("Student") });
  const { data: gradeData }   = useQuery({ queryKey: ["grades"],   queryFn: () => fetchObjectSet<GradeRow>("Grade") });

  const studentSet: ForgeObjectSet<StudentRow> | undefined = studentData
    ? { rows: studentData.rows, schema: studentData.schema as any, datasetId: "Student", mode: "snapshot" }
    : undefined;

  const gradeChartSet = useMemo(() => {
    if (!gradeData) return null;
    const counts: Record<string, number> = {};
    for (const g of gradeData.rows) counts[g.grade] = (counts[g.grade] ?? 0) + 1;
    const rows = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)).map(([grade, count]) => ({ grade, count }));
    return { rows, schema: { name: "GradeDist", mode: "stream" as const, fields: { grade: { type: "string" as const }, count: { type: "integer" as const } } }, datasetId: "gd", mode: "stream" as const };
  }, [gradeData]);

  const majorChartSet = useMemo(() => {
    if (!studentData) return null;
    const counts: Record<string, number> = {};
    for (const s of studentData.rows) counts[s.major] = (counts[s.major] ?? 0) + 1;
    const rows = Object.entries(counts).map(([major, count]) => ({ major, count }));
    return { rows, schema: { name: "MajorDist", mode: "stream" as const, fields: { major: { type: "string" as const }, count: { type: "integer" as const } } }, datasetId: "md", mode: "stream" as const };
  }, [studentData]);

  return (
    <>
      <div className="metrics-row">
        {studentSet && <MetricTile label="Total Students" objectSet={studentSet} aggregation="count" />}
        {studentSet && <MetricTile label="Active" value={studentSet.rows.filter(r => r.status === "active").length} />}
        {gradeData  && <MetricTile label="Total Grades" value={gradeData.total} />}
      </div>

      <div className="charts-grid">
        <div>
          <h3>Grade Distribution</h3>
          {gradeChartSet && (
            <Chart objectSet={gradeChartSet} chartType="bar" xField="grade"
              series={[{ field: "count", label: "# Grades", color: "#6366f1" }]} height={260} />
          )}
        </div>
        <div>
          <h3>Students by Major</h3>
          {majorChartSet && (
            <Chart objectSet={majorChartSet} chartType="bar" xField="major"
              series={[{ field: "count", label: "Students", color: "#10b981" }]} height={260} />
          )}
        </div>
      </div>

      {studentSet && (
        <div className="section">
          <h3>Student Roster</h3>
          <ObjectTable objectSet={studentSet} interaction={{ visibleFields: ["name", "major", "status", "enrolled_at"], density: "compact" }} />
        </div>
      )}
    </>
  );
}
