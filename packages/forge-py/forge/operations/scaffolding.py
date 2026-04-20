"""CORE scaffolding operations — create pipelines, models, endpoints, and apps."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from forge.operations.projects import read_toml, resolve_suite_root


# ── Pipeline ───────────────────────────────────────────────────────────────────

_PIPELINE_TEMPLATE = '''\
"""
Pipeline Layer — {name}
"""
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

INPUT_DATASET_ID  = "{input_uuid}"
OUTPUT_DATASET_ID = "{output_uuid}"


@pipeline(
    inputs={{
        "source": ForgeInput(INPUT_DATASET_ID),
    }},
    outputs={{
        "result": ForgeOutput(OUTPUT_DATASET_ID),
    }},
)
def run(inputs, outputs):
    df = inputs.source.df()
    # Transform df here
    outputs.result.write(df)
'''


def create_pipeline(root: Path, pipeline_name: str) -> dict:
    name = re.sub(r"[^a-z0-9_]", "_", pipeline_name.lower()).strip("_")
    if not name:
        return {"error": "Invalid pipeline name"}

    pipelines_dir = root / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    init = pipelines_dir / "__init__.py"
    if not init.exists():
        init.write_text("")

    pipeline_file = pipelines_dir / f"{name}.py"
    if pipeline_file.exists():
        return {"error": f"pipelines/{name}.py already exists"}

    pipeline_file.write_text(_PIPELINE_TEMPLATE.format(
        name=name,
        input_uuid=str(uuid.uuid4()),
        output_uuid=str(uuid.uuid4()),
    ))

    _patch_toml_pipelines(root, name)
    return {"file": str(pipeline_file), "name": name}


def _patch_toml_pipelines(root: Path, name: str) -> None:
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return
    cfg = read_toml(toml_path)
    if any(p.get("display_name") == name or p.get("name") == name for p in cfg.get("pipelines", [])):
        return
    toml_path.write_text(
        toml_path.read_text()
        + f'\n[[pipelines]]\ndisplay_name = "{name}"\nmodule = "pipelines.{name}"\nfunction = "run"\n'
    )


# ── Model ──────────────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "integer": "int",
    "float": "float",
    "boolean": "bool",
    "datetime": "str",
    "string": "str",
}

_MODEL_TEMPLATE = '''\
# -*- coding: utf-8 -*-
"""
Model Layer — {class_name} ({mode})
Backed by dataset {dataset_id}.
"""
from forge.model import forge_model, field_def, {base_class}

DATASET_ID = "{dataset_id}"


@forge_model(mode="{mode}", backing_dataset=DATASET_ID)
class {class_name}({base_class}):
{fields}
'''


def create_model(root: Path, dataset_id: str, model_name: str, mode: str = "snapshot") -> dict:
    from forge.storage.engine import StorageEngine

    if mode not in ("snapshot", "immutable"):
        return {"error": "mode must be 'snapshot' or 'immutable'"}

    class_name = re.sub(r"^[^A-Za-z]+", "", model_name.strip())
    class_name = re.sub(r"[^A-Za-z0-9_]", "_", class_name)
    if not class_name:
        return {"error": "model_name must contain at least one letter"}

    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    snake_name = re.sub(r"[^a-z0-9_]", "_", snake_name).strip("_")

    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    init = models_dir / "__init__.py"
    if not init.exists():
        init.write_text("")

    model_file = models_dir / f"{snake_name}.py"
    if model_file.exists():
        return {"error": f"models/{snake_name}.py already exists"}

    with StorageEngine(root / ".forge") as engine:
        meta = engine.get_dataset(dataset_id)
        if meta is None:
            return {"error": f"Dataset {dataset_id} not found in project storage"}
        schema_fields = meta.schema.get("fields", {})

    if not schema_fields:
        return {"error": "Dataset has no schema fields — run the pipeline at least once first"}

    col_names = list(schema_fields.keys())
    pk_candidates = [c for c in col_names if c.lower() == "id"] \
        or [c for c in col_names if c.lower() == "pk"]
    primary_key = pk_candidates[0] if pk_candidates else col_names[0]

    field_lines = []
    for col, info in schema_fields.items():
        py_type = _TYPE_MAP.get(info.get("type", "string"), "str")
        display = col.replace("_", " ").title()
        hints = []
        if col == primary_key:
            hints.append("primary_key=True")
        hints.append(f'display="{display}"')
        if info.get("type") == "datetime":
            hints.append('display_hint="date"')
        field_lines.append(f"    {col}: {py_type} = field_def({', '.join(hints)})")

    base_class = "ForgeSnapshotModel" if mode == "snapshot" else "ForgeStreamModel"
    model_file.write_text(_MODEL_TEMPLATE.format(
        class_name=class_name,
        dataset_id=dataset_id,
        fields="\n".join(field_lines),
        mode=mode,
        base_class=base_class,
    ))

    _patch_toml_models(root, class_name, snake_name, mode)
    return {"file": str(model_file), "name": class_name}


def _patch_toml_models(root: Path, class_name: str, snake_name: str, mode: str) -> None:
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return
    cfg = read_toml(toml_path)
    if any(m.get("class_name") == class_name or m.get("name") == class_name for m in cfg.get("models", [])):
        return
    toml_path.write_text(
        toml_path.read_text()
        + f'\n[[models]]\nclass_name = "{class_name}"\n'
          f'module = "models.{snake_name}"\nmode = "{mode}"\n'
    )


# ── Endpoint ───────────────────────────────────────────────────────────────────

_ENDPOINT_REPO_SETUP = 'from setuptools import setup, find_packages\nsetup(name="{repo_name}", packages=find_packages())\n'

_ENDPOINT_FILE_NEW: dict[str, str] = {
    "action": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import action_endpoint

{CONST_NAME}_ID = "{endpoint_uuid}"


@action_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str) -> dict:
    return {{"result": input}}
''',
    "streaming": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import streaming_endpoint, StreamEvent

{CONST_NAME}_ID = "{endpoint_uuid}"


@streaming_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str):
    yield StreamEvent(data="done", event="done")
''',
    "computed_attribute": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import computed_attribute_endpoint

{CONST_NAME}_ID = "{endpoint_uuid}"


@computed_attribute_endpoint(
    object_type="MyModel",
    columns=["my_column"],
    endpoint_id={CONST_NAME}_ID,
    name="{endpoint_name}",
    description="TODO: describe what this computed column does",
)
def {endpoint_name}(objects, **kwargs) -> dict:
    return {{obj.id: {{"my_column": None}} for obj in objects}}
''',
}

_ENDPOINT_SNIPPET: dict[str, str] = {
    "action": '''

from forge.control import action_endpoint  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@action_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str) -> dict:
    return {{"result": input}}
''',
    "streaming": '''

from forge.control import streaming_endpoint, StreamEvent  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@streaming_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str):
    yield StreamEvent(data="done", event="done")
''',
    "computed_attribute": '''

from forge.control import computed_attribute_endpoint  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@computed_attribute_endpoint(
    object_type="MyModel",
    columns=["my_column"],
    endpoint_id={CONST_NAME}_ID,
    name="{endpoint_name}",
    description="TODO: describe what this computed column does",
)
def {endpoint_name}(objects, **kwargs) -> dict:
    return {{obj.id: {{"my_column": None}} for obj in objects}}
''',
}


def create_endpoint(
    root: Path,
    endpoint_name: str,
    repo_name: str,
    kind: str = "action",
) -> dict:
    if kind not in ("action", "streaming", "computed_attribute"):
        return {"error": "kind must be 'action', 'streaming', or 'computed_attribute'"}

    name = re.sub(r"[^a-z0-9_]", "_", endpoint_name.lower()).strip("_")
    if not name:
        return {"error": "Invalid endpoint name"}

    repo = re.sub(r"[^a-z0-9_]", "_", repo_name.lower()).strip("_")
    if not repo:
        return {"error": "Invalid repo name"}

    const_name = name.upper()
    endpoint_uuid = str(uuid.uuid4())
    toml_path = root / "forge.toml"
    cfg = read_toml(toml_path) if toml_path.exists() else {}

    repo_module = f"endpoint_repos.{repo}"
    existing_repo = next(
        (r for r in cfg.get("endpoint_repos", [])
         if r.get("module") == repo_module or r.get("name") == repo),
        None,
    )
    repo_root = root / "endpoint_repos" / repo
    # New repos use flat structure: endpoint_repos/{repo}/endpoints.py
    # Old repos may have nested structure: endpoint_repos/{repo}/{repo}/endpoints.py
    old_endpoints_file = repo_root / repo / "endpoints.py"
    new_endpoints_file = repo_root / "endpoints.py"
    endpoints_file = old_endpoints_file if old_endpoints_file.exists() else new_endpoints_file

    if existing_repo is None:
        repo_root.mkdir(parents=True, exist_ok=True)
        (repo_root / "__init__.py").write_text("")
        new_endpoints_file.write_text(
            _ENDPOINT_FILE_NEW[kind].format(
                repo_name=repo,
                CONST_NAME=const_name,
                endpoint_uuid=endpoint_uuid,
                endpoint_name=name,
            )
        )
        if toml_path.exists():
            toml_path.write_text(
                toml_path.read_text()
                + f'\n[[endpoint_repos]]\nmodule = "{repo_module}"\n'
            )
    else:
        if not endpoints_file.parent.exists():
            endpoints_file.parent.mkdir(parents=True, exist_ok=True)
        existing = endpoints_file.read_text() if endpoints_file.exists() else ""
        if f"def {name}(" in existing:
            return {"error": f"Function '{name}' already exists in {repo}/endpoints.py"}
        endpoints_file.write_text(
            existing + _ENDPOINT_SNIPPET[kind].format(
                CONST_NAME=const_name,
                endpoint_uuid=endpoint_uuid,
                endpoint_name=name,
            )
        )

    return {"file": str(endpoints_file), "name": name, "repo": repo, "kind": kind}


# ── App ────────────────────────────────────────────────────────────────────────

_APP_COMMAND = '''\
#!/usr/bin/env bash
# {app_name} — start the dev server and open the app in a browser.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
APP_DIR="$PROJECT_ROOT/apps/{app_name}"
PORT={port}

if [ ! -d "$APP_DIR/node_modules" ]; then
  echo "→ Installing npm dependencies (first run)..."
  npm install --prefix "$APP_DIR" --silent
fi

echo "→ Starting {app_name} dev server on :$PORT..."
npm --prefix "$APP_DIR" run dev &
DEV_PID=$!

echo "→ Waiting for server to be ready..."
for _ in $(seq 1 60); do
  if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "✓ {app_name} running at http://localhost:$PORT"
if command -v open &>/dev/null; then open "http://localhost:$PORT"
elif command -v xdg-open &>/dev/null; then xdg-open "http://localhost:$PORT"
fi

echo "Press Ctrl+C to stop."
cleanup() {{ kill "$DEV_PID" 2>/dev/null || true; }}
trap cleanup EXIT INT TERM
wait "$DEV_PID"
'''

_APP_PACKAGE_JSON = '''\
{{
  "name": "{app_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "@forge-suite/ts": "*",
    "@tanstack/react-query": "^5.40.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.3.1"
  }}
}}
'''

# vite.config.ts reads FORGE_SUITE_ROOT from ~/.forge/env at build/dev time.
# Falls back to a relative path from the project's .forge/suite_root file.
_APP_VITE_CONFIG = '''\
import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";
import {{ readFileSync, existsSync }} from "fs";
import {{ resolve }} from "path";

function forgeTsSrc(): string {{
  // 1. Read FORGE_SUITE_ROOT from ~/.forge/env
  const envFile = resolve(process.env.HOME || "~", ".forge", "env");
  if (existsSync(envFile)) {{
    const line = readFileSync(envFile, "utf8")
      .split("\\n")
      .find((l) => l.startsWith("FORGE_SUITE_ROOT="));
    if (line) {{
      const suiteRoot = line.split("=")[1].trim();
      return resolve(suiteRoot, "forge-framework", "packages", "forge-ts", "src", "index.ts");
    }}
  }}
  // 2. Read from .forge/suite_root written at project mount time
  const suiteRootFile = resolve(__dirname, ".forge", "suite_root");
  if (existsSync(suiteRootFile)) {{
    const suiteRoot = readFileSync(suiteRootFile, "utf8").trim();
    return resolve(suiteRoot, "forge-framework", "packages", "forge-ts", "src", "index.ts");
  }}
  throw new Error(
    "FORGE_SUITE_ROOT not found. Run setup.command or mount this project in forge-suite."
  );
}}

export default defineConfig({{
  plugins: [react()],
  resolve: {{
    alias: {{
      "@forge-suite/ts/forge.css": forgeTsSrc().replace("index.ts", "forge.css"),
      "@forge-suite/ts/runtime": forgeTsSrc().replace("index.ts", "runtime/index.ts"),
      "@forge-suite/ts": forgeTsSrc(),
    }},
  }},
  server: {{
    proxy: {{
      "/api": `http://localhost:${{process.env.VITE_API_PORT || "8000"}}`,
      "/endpoints": `http://localhost:${{process.env.VITE_API_PORT || "8000"}}`,
    }},
  }},
}});
'''

_APP_TSCONFIG = '''\
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
'''

_APP_INDEX_HTML = '''\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{app_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''

_APP_MAIN_TSX = '''\
import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@forge-suite/ts/forge.css";
import "./index.css";
import { App } from "./App.js";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
'''

_APP_INDEX_CSS = '''\
/* Project-specific styles — forge.css is imported in main.tsx */

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

#root { min-height: 100vh; }
'''

_APP_APP_TSX = '''\
import React, {{ useState }} from "react";
import {{ Container }} from "@forge-suite/ts";
import {{ Sidebar }} from "./components/Sidebar.js";
import {{ Landing }} from "./pages/landing.js";

export type Page = "landing";

export function App() {{
  const [page, setPage] = useState<Page>("landing");

  return (
    <Container direction='row' style={{{{ minHeight: "100vh" }}}}>
      <Sidebar activePage={{page}} onNavigate={{setPage}} />
      <Container direction='column' size={{1}} padding={{24}}>
        {{page === "landing" && <Landing />}}
      </Container>
    </Container>
  );
}}
'''

_APP_SIDEBAR_TSX = '''\
import React from "react";
import {{ Container, Navbar }} from "@forge-suite/ts";
import type {{ Page }} from "../App.js";

const NAV_ITEMS = [
  {{ id: "landing", label: "Home", icon: "◈" }},
] as const;

interface Props {{
  activePage: Page;
  onNavigate: (p: Page) => void;
}}

export function Sidebar({{ activePage, onNavigate }}: Props) {{
  return (
    <Container
      direction='column'
      size='220px'
      separator
      style={{{{
        minHeight: "100vh",
        background: "var(--bg-panel)",
        borderRight: "1px solid var(--border)",
      }}}}
    >
      <Container direction='row' gap={{8}} padding='18px 16px 14px'>
        <span style={{{{ fontWeight: 700, fontSize: 15 }}}}>{app_name}</span>
      </Container>
      <Navbar
        orientation='vertical'
        items={{NAV_ITEMS.map((item) => ({{
          id: item.id,
          label: item.label,
          icon: item.icon,
          active: activePage === item.id,
          onClick: () => onNavigate(item.id as Page),
        }}))}}
        style={{{{ padding: "4px 0" }}}}
      />
    </Container>
  );
}}
'''

_APP_LANDING_TSX = '''\
import React from "react";
import {{ Container }} from "@forge-suite/ts";

export function Landing() {{
  return (
    <Container direction='row' padding={{24}} alignItems='center'>
      <p>Hello World!</p>
    </Container>
  );
}}
'''


def create_app(
    root: Path,
    app_name: str,
    port: str = "5177",
    suite_root: Path | None = None,
) -> dict:
    name = re.sub(r"[^a-z0-9\-_]", "-", app_name.lower()).strip("-_")
    if not name:
        return {"error": "Invalid app name"}

    app_dir = root / "apps" / name
    if app_dir.exists():
        return {"error": f"apps/{name} already exists"}

    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "src").mkdir(exist_ok=True)
    (app_dir / "src" / "pages").mkdir(exist_ok=True)
    (app_dir / "src" / "components").mkdir(exist_ok=True)

    (app_dir / "package.json").write_text(_APP_PACKAGE_JSON.format(app_name=name), encoding="utf-8")
    (app_dir / "vite.config.ts").write_text(_APP_VITE_CONFIG.format(), encoding="utf-8")
    (app_dir / "index.html").write_text(_APP_INDEX_HTML.format(app_name=name), encoding="utf-8")
    (app_dir / "tsconfig.json").write_text(_APP_TSCONFIG, encoding="utf-8")
    (app_dir / "src" / "main.tsx").write_text(_APP_MAIN_TSX, encoding="utf-8")
    (app_dir / "src" / "index.css").write_text(_APP_INDEX_CSS, encoding="utf-8")
    (app_dir / "src" / "App.tsx").write_text(_APP_APP_TSX.format(), encoding="utf-8")
    (app_dir / "src" / "components" / "Sidebar.tsx").write_text(_APP_SIDEBAR_TSX.format(app_name=name), encoding="utf-8")
    (app_dir / "src" / "pages" / "landing.tsx").write_text(_APP_LANDING_TSX.format(app_name=name), encoding="utf-8")

    if sys.platform != "win32":
        command_file = root / f"{name}.command"
        command_file.write_text(_APP_COMMAND.format(app_name=name, port=port))
        command_file.chmod(0o755)

    # Write .forge/suite_root so vite.config.ts can resolve forge-ts at IDE/build time
    if suite_root is None:
        suite_root = resolve_suite_root()
    if suite_root is not None:
        suite_root_file = app_dir / ".forge" / "suite_root"
        suite_root_file.parent.mkdir(parents=True, exist_ok=True)
        suite_root_file.write_text(str(suite_root), encoding="utf-8")

    _patch_toml_apps(root, name)

    npm = shutil.which("npm")
    npm_ok = False
    if npm:
        result = subprocess.run([npm, "install"], cwd=str(app_dir), capture_output=True)
        npm_ok = result.returncode == 0

    # Symlink @forge-suite/ts into node_modules so IDE and tsc can resolve types.
    # Symlinks require Developer Mode or admin on Windows; skip gracefully if unavailable.
    if suite_root is not None:
        forge_ts_src = Path(suite_root) / "forge-framework" / "packages" / "forge-ts"
        if forge_ts_src.exists():
            scope_dir = app_dir / "node_modules" / "@forge-suite"
            scope_dir.mkdir(parents=True, exist_ok=True)
            ts_link = scope_dir / "ts"
            if not ts_link.exists():
                try:
                    ts_link.symlink_to(forge_ts_src.resolve())
                except OSError:
                    pass

    return {"path": str(app_dir), "name": name, "npm_installed": npm_ok}


def _patch_toml_apps(root: Path, name: str) -> None:
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return
    cfg = read_toml(toml_path)
    if any(a.get("name") == name for a in cfg.get("apps", [])):
        return
    toml_path.write_text(
        toml_path.read_text()
        + f'\n[[apps]]\nname = "{name}"\npath = "./apps/{name}"\n'
    )
