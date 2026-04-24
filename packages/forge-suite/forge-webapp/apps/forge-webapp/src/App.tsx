import React, { useState } from "react";
import { Sidebar } from "./components/Sidebar.js";
import { OverviewPage } from "./pages/OverviewPage.js";
import { PipelinesPage } from "./pages/PipelinesPage.js";
import { ModelPage } from "./pages/ModelPage.js";
import { EndpointsPage } from "./pages/EndpointsPage.js";
import { AppsPage } from "./pages/AppsPage.js";
import { FilesPage } from "./pages/FilesPage.js";
import { DatasetsPage } from "./pages/DatasetsPage.js";
import { ModulesPage } from "./pages/ModulesPage.js";
import { ModuleLibraryPage } from "./pages/ModuleLibraryPage.js";

export type Page =
  | "overview"
  | "pipelines"
  | "model"
  | "endpoints"
  | "apps"
  | "modules"
  | "module-library"
  | "files"
  | "datasets";

export function App() {
  const [page, setPage] = useState<Page>("overview");

  return (
    <div style={{ display: "flex", minHeight: "100vh", width: "100%" }}>
      <Sidebar activePage={page} onNavigate={setPage} />
      <main style={{ flex: 1, overflow: "auto" }}>
        {page === "overview" && <OverviewPage />}
        {page === "pipelines" && <PipelinesPage />}
        {page === "model" && <ModelPage />}
        {page === "endpoints" && <EndpointsPage />}
        {page === "apps" && <AppsPage />}
        {page === "modules" && <ModulesPage />}
        {page === "module-library" && <ModuleLibraryPage />}
        {page === "files" && <FilesPage />}
        {page === "datasets" && <DatasetsPage />}
      </main>
    </div>
  );
}
