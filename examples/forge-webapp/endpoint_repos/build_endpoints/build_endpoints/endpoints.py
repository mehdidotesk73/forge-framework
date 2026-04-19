"""
Control Layer — build_endpoints
Shells out to the forge CLI and streams stdout/stderr as SSE events.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from forge.control import streaming_endpoint, StreamEvent

from models.models import ForgeProject

RUN_PIPELINE_ID       = "cccccccc-0005-0000-0000-000000000000"
RUN_MODEL_BUILD_ID    = "cccccccc-0006-0000-0000-000000000000"
RUN_ENDPOINT_BUILD_ID = "cccccccc-0007-0000-0000-000000000000"


def _get_root(project_id: str):
    proj = ForgeProject.get(project_id)
    return Path(proj.root_path) if proj else None


def _stream_command(cmd: list[str], cwd: Path):
    """Run a subprocess and yield StreamEvents for each output line."""
    yield StreamEvent(data=f"$ {' '.join(cmd)}", event="status")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        import select, sys
        stdout_done = False
        stderr_done = False
        while not (stdout_done and stderr_done):
            reads = []
            if not stdout_done:
                reads.append(proc.stdout)
            if not stderr_done:
                reads.append(proc.stderr)
            readable, _, _ = select.select(reads, [], [], 0.1)
            for stream in readable:
                line = stream.readline()
                if not line:
                    if stream is proc.stdout:
                        stdout_done = True
                    else:
                        stderr_done = True
                else:
                    event = "stdout" if stream is proc.stdout else "stderr"
                    yield StreamEvent(data=line.rstrip(), event=event)
        proc.wait()
        if proc.returncode == 0:
            yield StreamEvent(data=f"Exited with code {proc.returncode}", event="status")
        else:
            yield StreamEvent(data=f"Process failed (exit {proc.returncode})", event="error")
    except Exception as exc:
        yield StreamEvent(data=str(exc), event="error")


@streaming_endpoint(
    name="run_pipeline",
    endpoint_id=RUN_PIPELINE_ID,
    description="Run a named pipeline in the active project and stream its output",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "pipeline_name", "type": "string", "required": True},
    ],
)
def run_pipeline(project_id: str, pipeline_name: str):
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    yield from _stream_command(["forge", "pipeline", "run", pipeline_name], root)


@streaming_endpoint(
    name="run_model_build",
    endpoint_id=RUN_MODEL_BUILD_ID,
    description="Run forge model build and stream detailed schema + data summary per model",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def run_model_build(project_id: str):
    import sys, json, math
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    try:
        from forge.config import load_config
        from forge.storage.engine import StorageEngine
        from forge.model.builder import ModelBuilder

        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        config, _ = load_config(root)
        if not config.models:
            yield StreamEvent(data="No models declared in forge.toml", event="status")
            return

        yield StreamEvent(data=f"Building {len(config.models)} model(s) in {root.name}…", event="status")

        with StorageEngine(root / ".forge") as engine:
            builder = ModelBuilder(config, root, engine)
            for model_cfg in config.models:
                yield StreamEvent(data=f"▸ {model_cfg.class_name}", event="status")
                try:
                    result = builder.build_one(model_cfg)

                    artifact = json.loads(Path(result["artifact"]).read_text())
                    fields  = artifact.get("fields", {})
                    pk      = artifact.get("primary_key") or "—"
                    mode    = artifact.get("mode", "—")
                    snap_id = artifact.get("snapshot_dataset_id") or "—"
                    back_id = artifact.get("backing_dataset_id", "—")

                    yield StreamEvent(data=f"  mode={mode}  pk={pk}  backing={back_id[:8]}…  snapshot={snap_id[:8] if snap_id != '—' else '—'}…", event="stdout")

                    # ── Schema table ──────────────────────────────────────────
                    col_w = max((len(n) for n in fields), default=5)
                    sep_w = col_w + 40
                    yield StreamEvent(data="", event="stdout")
                    yield StreamEvent(data=f"  ┌─ Schema {'─' * (sep_w - 9)}┐", event="stdout")
                    hdr = f"  │  {'Field':<{col_w}}  {'Type':<10}  {'PK':<3}  {'Nullable':<8}  Display"
                    yield StreamEvent(data=hdr, event="stdout")
                    yield StreamEvent(data=f"  │  {'─' * (sep_w - 4)}", event="stdout")
                    for fname, fmeta in fields.items():
                        is_pk    = "✓" if fmeta.get("primary_key") else ""
                        nullable = "✓" if fmeta.get("nullable") else ""
                        ftype    = fmeta.get("type", "")
                        display  = fmeta.get("display", "")
                        yield StreamEvent(
                            data=f"  │  {fname:<{col_w}}  {ftype:<10}  {is_pk:<3}  {nullable:<8}  {display}",
                            event="stdout"
                        )
                    yield StreamEvent(data=f"  └{'─' * (sep_w + 1)}┘", event="stdout")

                    # ── Data summary ──────────────────────────────────────────
                    dataset_id = artifact.get("snapshot_dataset_id") or artifact.get("backing_dataset_id")
                    df = engine.read_dataset(dataset_id)

                    desc_all = df.describe(include="all")
                    name_w = max((len(c) for c in df.columns), default=6)
                    n_rows = len(df)
                    data_sep_w = name_w + 60
                    yield StreamEvent(data="", event="stdout")
                    yield StreamEvent(data=f"  ┌─ Data  {n_rows:,} rows × {len(df.columns)} cols {'─' * max(0, data_sep_w - 22 - len(str(n_rows)))}┐", event="stdout")
                    yield StreamEvent(
                        data=f"  │  {'Column':<{name_w}}  {'dtype':<14}  {'nulls':<6}  {'unique':<7}  Range / Top value",
                        event="stdout"
                    )
                    yield StreamEvent(data=f"  │  {'─' * (data_sep_w - 4)}", event="stdout")

                    def _fmt_num(v) -> str:
                        if v is None:
                            return "—"
                        if isinstance(v, float):
                            return f"{v:,.4g}"
                        return str(v)

                    for col in df.columns:
                        dtype    = str(df[col].dtype)
                        nulls    = int(df[col].isna().sum())
                        n_unique = int(df[col].nunique())
                        s = desc_all[col] if col in desc_all.columns else {}

                        def _v(key, _s=s):
                            try:
                                v = _s[key] if hasattr(_s, "__getitem__") else None
                                return v if (v is not None and not (isinstance(v, float) and math.isnan(v))) else None
                            except Exception:
                                return None

                        mn   = _v("min");  mx   = _v("max")
                        top  = _v("top");  freq = _v("freq")
                        mean = _v("mean")

                        if mn is not None:
                            range_str = f"min={_fmt_num(mn)}  max={_fmt_num(mx)}"
                            if mean is not None:
                                range_str += f"  mean={_fmt_num(mean)}"
                        elif top is not None:
                            pct = f"{int(freq) / n_rows * 100:.0f}%" if n_rows else "?"
                            range_str = f"top={str(top)[:30]!r} ({freq}x, {pct})"
                        else:
                            range_str = ""

                        yield StreamEvent(
                            data=f"  │  {col:<{name_w}}  {dtype:<14}  {nulls:<6}  {n_unique:<7}  {range_str}",
                            event="stdout"
                        )

                    yield StreamEvent(data=f"  └{'─' * (data_sep_w + 1)}┘", event="stdout")
                    yield StreamEvent(data="", event="stdout")
                    yield StreamEvent(data=f"  artifacts → {result['artifact']}", event="stdout")
                    yield StreamEvent(data=f"  py sdk   → {result['python_sdk']}", event="stdout")
                    yield StreamEvent(data=f"  ts sdk   → {result['typescript_sdk']}", event="stdout")

                except Exception as exc:
                    yield StreamEvent(data=f"  ✗ {model_cfg.class_name}: {exc}", event="error")

        yield StreamEvent(data="Done.", event="status")
    except Exception as exc:
        yield StreamEvent(data=str(exc), event="error")


@streaming_endpoint(
    name="run_endpoint_build",
    endpoint_id=RUN_ENDPOINT_BUILD_ID,
    description="Run forge endpoint build and stream output",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def run_endpoint_build(project_id: str):
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    yield from _stream_command(["forge", "endpoint", "build"], root)
