import React from "react";
import { createRoot } from "react-dom/client";
import "/Users/mehdi/Sandbox/forge-framework/packages/forge-ts/src/forge.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { configureForge } from "@forge-framework/ts";
import { App } from "./App.js";

configureForge({ baseUrl: window.location.origin });

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
);
