import React from "react";
import { Navbar } from "@forge-suite/ts";
import { DashboardPage } from "./pages/DashboardPage.js";

export function App() {
  return (
    <div>
      <Navbar
        title="Student Analytics"
        items={[{ label: "Dashboard", active: true }]}
      />
      <main style={{ padding: "1rem" }}>
        <DashboardPage />
      </main>
    </div>
  );
}
