import React from "react";
import { Navbar } from "@forge-framework/ts";
import { PriceChart } from "./pages/PriceChart.js";

export function App() {
  return (
    <div style={{ background: "#0f1117", minHeight: "100vh", color: "#e2e8f0" }}>
      <Navbar title="₿ BTC Chart" />
      <main style={{ padding: "24px" }}>
        <PriceChart />
      </main>
    </div>
  );
}
