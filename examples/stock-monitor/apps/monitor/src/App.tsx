import React from "react";
import { Navbar } from "@forge-framework/ts";
import { MonitorPage } from "./pages/MonitorPage.js";

export function App() {
  return (
    <div>
      <Navbar title="Stock Price Monitor" items={[{ label: "Monitor", active: true }]} />
      <main style={{ padding: "1rem" }}>
        <MonitorPage />
      </main>
    </div>
  );
}
