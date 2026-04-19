import React, { useState } from "react";
import { Navbar } from "@forge-suite/ts";
import { StudentsPage } from "./pages/StudentsPage.js";
import { AnalyticsPage } from "./pages/AnalyticsPage.js";

type Tab = "students" | "analytics";

export function App() {
  const [tab, setTab] = useState<Tab>("students");

  return (
    <div className="forge-root">
      <Navbar
        title="Student Manager"
        items={[
          { label: "Students", active: tab === "students", onClick: () => setTab("students") },
          { label: "Analytics", active: tab === "analytics", onClick: () => setTab("analytics") },
        ]}
      />
      <main className="page">
        {tab === "students" && <StudentsPage />}
        {tab === "analytics" && <AnalyticsPage />}
      </main>
    </div>
  );
}
