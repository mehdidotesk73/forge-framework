// Standalone dev entry — mounts a full working demo app.
// Not included in the library build.
import React from "react";
import ReactDOM from "react-dom/client";
import { configureForge } from "@forge-suite/ts";
import { AiChat } from "./widgets/AiChat.js";
import "@forge-suite/ts/forge.css";

configureForge({ baseUrl: "http://localhost:8000" });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <AiChat />
    </div>
  </React.StrictMode>,
);
