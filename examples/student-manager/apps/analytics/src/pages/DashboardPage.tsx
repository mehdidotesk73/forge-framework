/**
 * View Layer — Analytics App
 *
 * Second app in the same project. Shares the Student and Grade object sets
 * and the same endpoint layer, but composes completely different pages.
 * Widget state is not shared with the student-manager app.
 */
import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Chart,
  MetricTile,
  Container,
  ObjectTable,
  type ForgeObjectSet,
  fetchObjectSet,
} from "@forge-framework/ts";

type StudentRow = {
  id: string; name: string; major: string; status: string; enrolled_at: string;
};
type GradeRow = {
  id: string; student_id: string; course: string; semester: string;
  grade: string; credits: number;
};

const GRADE_POINTS: Record<string, number> = {
  "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
  "C+": 2.3, "C": 2.0, "F": 0.0,
};

export function DashboardPage() {
  const { data: studentData } = useQuery({
    queryKey: ["students"],
    queryFn: () => fetchObjectSet<StudentRow>("Student"),
  });
  const { data: gradeData } = useQuery({
    queryKey: ["grades"],
    queryFn: () => fetchObjectSet<GradeRow>("Grade"),
  });

  const studentSet: ForgeObjectSet<StudentRow> | undefined = studentData
    ? { rows: studentData.rows, schema: studentData.schema as any, datasetId: "Student", mode: "snapshot" }
    : undefined;

  // Compute grade distribution for chart
  const gradeDistribution = React.useMemo(() => {
    if (!gradeData) return [];
    const counts: Record<string, number> = {};
    for (const g of gradeData.rows) {
      counts[g.grade] = (counts[g.grade] ?? 0) + 1;
    }
    return Object.entries(counts).map(([grade, count]) => ({ grade, count }));
  }, [gradeData]);

  const gradeChartSet = {
    rows: gradeDistribution,
    schema: { name: "GradeDistribution", mode: "stream" as const, fields: {
      grade: { type: "string" as const },
      count: { type: "integer" as const },
    }},
    datasetId: "grade_dist",
    mode: "stream" as const,
  };

  // Major breakdown
  const majorCounts = React.useMemo(() => {
    if (!studentData) return [];
    const counts: Record<string, number> = {};
    for (const s of studentData.rows) {
      counts[s.major] = (counts[s.major] ?? 0) + 1;
    }
    return Object.entries(counts).map(([major, count]) => ({ major, count }));
  }, [studentData]);

  const majorChartSet = {
    rows: majorCounts,
    schema: { name: "MajorBreakdown", mode: "stream" as const, fields: {
      major: { type: "string" as const },
      count: { type: "integer" as const },
    }},
    datasetId: "major_dist",
    mode: "stream" as const,
  };

  return (
    <div>
      <h2>Academic Analytics Dashboard</h2>

      <Container layout="flex" direction="row" gap="1rem">
        {studentSet && (
          <>
            <MetricTile label="Total Students" objectSet={studentSet} aggregation="count" />
            <MetricTile
              label="Active"
              value={studentSet.rows.filter((r) => r.status === "active").length}
            />
          </>
        )}
        {gradeData && (
          <MetricTile label="Total Grades" value={gradeData.total} />
        )}
      </Container>

      <Container layout="grid" columns={2} gap="2rem" padding="2rem 0">
        <div>
          <h3>Grade Distribution</h3>
          <Chart
            objectSet={gradeChartSet}
            chartType="bar"
            xField="grade"
            series={[{ field: "count", label: "# Grades", color: "#6366f1" }]}
            height={250}
          />
        </div>
        <div>
          <h3>Students by Major</h3>
          <Chart
            objectSet={majorChartSet}
            chartType="bar"
            xField="major"
            series={[{ field: "count", label: "Students", color: "#10b981" }]}
            height={250}
          />
        </div>
      </Container>

      {studentSet && (
        <div>
          <h3>Student Roster</h3>
          <ObjectTable
            objectSet={studentSet}
            interaction={{
              visibleFields: ["name", "major", "status", "enrolled_at"],
              density: "compact",
            }}
          />
        </div>
      )}
    </div>
  );
}
