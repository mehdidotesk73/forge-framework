# forge-framework (Python package)

This is the Forge Python package. It provides the CLI, storage engine, pipeline runner, model builder, endpoint builder, scheduler, and dev server.

## What you need to know

Install:
```bash
pip install forge-framework
```

## CLI Reference

```bash
forge init <project-name>           # create a new project

forge dataset load <file> --name <n> # load CSV/Parquet as a named dataset
forge dataset list                   # list all datasets
forge dataset inspect <id-or-name>   # inspect schema and preview rows

forge pipeline run <name>            # run a registered pipeline
forge pipeline dag                   # display the pipeline dependency DAG
forge pipeline history <name>        # show run history

forge model build                    # generate schema artifacts + Python/TS SDKs
forge model reinitialize <Type>      # drop and recreate a snapshot dataset

forge endpoint build                 # build all endpoint repos
forge endpoint build --repo <name>   # build a single endpoint repo

forge dev serve                      # start the dev server (port 8000)
forge dev serve --app <name>         # serve a specific app
forge dev serve --port 9000          # custom port

forge upgrade                        # run migrations + regenerate artifacts
forge upgrade --dry-run              # preview what would happen
forge version                        # print Python + TypeScript versions
```

## Layer-specific guides

### Pipeline developer

You write Python functions decorated with `@pipeline`. You see dataset UUIDs and schemas. You have zero knowledge of object types, endpoints, or UI.

```python
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

@pipeline(
    inputs={"raw": ForgeInput("your-input-uuid")},
    outputs={"clean": ForgeOutput("your-output-uuid")},
    schedule="0 6 * * *",  # optional
)
def run(inputs, outputs):
    df = inputs.raw.df()          # returns pandas DataFrame
    # or: rel = inputs.raw.relation()  # returns DuckDB relation
    outputs.clean.write(df)
```

Run: `forge pipeline run <name>`

### Model developer

You write class definitions decorated with `@forge_model`. You run `forge model build`. You do not write pipeline logic, endpoint logic, or UI code.

```python
from forge.model import forge_model, field_def

@forge_model(mode="snapshot", backing_dataset="uuid-here")
class MyObject:
    id: str = field_def(primary_key=True)
    name: str = field_def(display="Name")
```

`forge model build` generates:
- `.forge/artifacts/MyObject.schema.json`
- `.forge/generated/python/myobject.py`
- `.forge/generated/typescript/MyObject.ts`

### API developer

You write functions decorated with `@action_endpoint` or `@computed_column_endpoint`. You import from the generated Python SDK. You do not write UI code.

```python
from forge.control import action_endpoint

@action_endpoint(name="do_thing", params=[{"name": "x", "type": "string"}])
def do_thing(x: str) -> dict:
    return {"result": x.upper()}
```

Run: `forge endpoint build`

## Storage

All datasets are stored as Parquet files in `.forge/data/`. The DuckDB catalog at `.forge/forge.duckdb` tracks metadata and run history. Datasets are immutable once written — each pipeline run produces a new versioned file. Snapshot datasets are the sole exception and are mutated in place.

## Dev server

`forge dev serve` starts a FastAPI server on port 8000:
- `GET /api/datasets` — list datasets
- `GET /api/objects/<Type>` — read object set
- `POST /endpoints/<uuid>` — call an endpoint
- `GET /api/schemas/<Name>` — get schema artifact
- `GET /api/endpoints` — get call form descriptor registry
- `POST /api/pipelines/<name>/run` — trigger a pipeline
