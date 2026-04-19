"""CORE build operations — stream forge CLI commands as events."""
from __future__ import annotations

import subprocess
from pathlib import Path


def stream_command(cmd: list[str], cwd: Path):
    """Run a subprocess and yield (event, data) tuples for each output line."""
    import select

    yield ("status", f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
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
                    yield (event, line.rstrip())
        proc.wait()
        if proc.returncode == 0:
            yield ("status", f"Exited with code {proc.returncode}")
        else:
            yield ("error", f"Process failed (exit {proc.returncode})")
    except Exception as exc:
        yield ("error", str(exc))


def stream_pipeline_run(root: Path, pipeline_name: str):
    """Yield (event, data) tuples for running a named pipeline."""
    yield from stream_command(["forge", "pipeline", "run", pipeline_name], root)


def stream_model_build(root: Path):
    """Run forge model build with rich per-model output; yield (event, data) tuples."""
    import json
    import math
    import sys

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    try:
        from forge.config import load_config
        from forge.storage.engine import StorageEngine
        from forge.model.builder import ModelBuilder

        config, _ = load_config(root)
        if not config.models:
            yield ("status", "No models declared in forge.toml")
            return

        yield ("status", f"Building {len(config.models)} model(s) in {root.name}…")

        with StorageEngine(root / ".forge") as engine:
            builder = ModelBuilder(config, root, engine)
            for model_cfg in config.models:
                yield ("status", f"▸ {model_cfg.class_name}")
                try:
                    result = builder.build_one(model_cfg)

                    artifact = json.loads(Path(result["artifact"]).read_text())
                    fields = artifact.get("fields", {})
                    pk = artifact.get("primary_key") or "—"
                    mode = artifact.get("mode", "—")
                    snap_id = artifact.get("snapshot_dataset_id") or "—"
                    back_id = artifact.get("backing_dataset_id", "—")

                    yield ("stdout", f"  mode={mode}  pk={pk}  backing={back_id[:8]}…  snapshot={snap_id[:8] if snap_id != '—' else '—'}…")

                    col_w = max((len(n) for n in fields), default=5)
                    sep_w = col_w + 40
                    yield ("stdout", "")
                    yield ("stdout", f"  ┌─ Schema {'─' * (sep_w - 9)}┐")
                    yield ("stdout", f"  │  {'Field':<{col_w}}  {'Type':<10}  {'PK':<3}  {'Nullable':<8}  Display")
                    yield ("stdout", f"  │  {'─' * (sep_w - 4)}")
                    for fname, fmeta in fields.items():
                        is_pk = "✓" if fmeta.get("primary_key") else ""
                        nullable = "✓" if fmeta.get("nullable") else ""
                        ftype = fmeta.get("type", "")
                        display = fmeta.get("display", "")
                        yield ("stdout", f"  │  {fname:<{col_w}}  {ftype:<10}  {is_pk:<3}  {nullable:<8}  {display}")
                    yield ("stdout", f"  └{'─' * (sep_w + 1)}┘")

                    dataset_id = artifact.get("snapshot_dataset_id") or artifact.get("backing_dataset_id")
                    df = engine.read_dataset(dataset_id)

                    desc_all = df.describe(include="all")
                    name_w = max((len(c) for c in df.columns), default=6)
                    n_rows = len(df)
                    data_sep_w = name_w + 60
                    yield ("stdout", "")
                    yield ("stdout", f"  ┌─ Data  {n_rows:,} rows × {len(df.columns)} cols {'─' * max(0, data_sep_w - 22 - len(str(n_rows)))}┐")
                    yield ("stdout", f"  │  {'Column':<{name_w}}  {'dtype':<14}  {'nulls':<6}  {'unique':<7}  Range / Top value")
                    yield ("stdout", f"  │  {'─' * (data_sep_w - 4)}")

                    def _fmt_num(v) -> str:
                        if v is None:
                            return "—"
                        if isinstance(v, float):
                            return f"{v:,.4g}"
                        return str(v)

                    for col in df.columns:
                        dtype = str(df[col].dtype)
                        nulls = int(df[col].isna().sum())
                        n_unique = int(df[col].nunique())
                        s = desc_all[col] if col in desc_all.columns else {}

                        def _v(key, _s=s):
                            try:
                                v = _s[key] if hasattr(_s, "__getitem__") else None
                                return v if (v is not None and not (isinstance(v, float) and math.isnan(v))) else None
                            except Exception:
                                return None

                        mn = _v("min")
                        mx = _v("max")
                        top = _v("top")
                        freq = _v("freq")
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

                        yield ("stdout", f"  │  {col:<{name_w}}  {dtype:<14}  {nulls:<6}  {n_unique:<7}  {range_str}")

                    yield ("stdout", f"  └{'─' * (data_sep_w + 1)}┘")
                    yield ("stdout", "")
                    yield ("stdout", f"  artifacts → {result['artifact']}")
                    yield ("stdout", f"  py sdk   → {result['python_sdk']}")
                    yield ("stdout", f"  ts sdk   → {result['typescript_sdk']}")

                except Exception as exc:
                    yield ("error", f"  ✗ {model_cfg.class_name}: {exc}")

        yield ("status", "Done.")
    except Exception as exc:
        yield ("error", str(exc))


def stream_endpoint_build(root: Path):
    """Yield (event, data) tuples for running forge endpoint build."""
    yield from stream_command(["forge", "endpoint", "build"], root)
