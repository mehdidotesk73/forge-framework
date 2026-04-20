"""Migration: forge.toml schema rename (0.1.0)."""
from __future__ import annotations

import re
from pathlib import Path

from forge.migrations.base import register_migration


@register_migration(
    "0.0.0",
    "0.1.0",
    "Rename forge.toml fields: pipeline name→display_name, model class/name→class_name, endpoint_repo name+path→module",
)
def migrate_toml_schema(project_root: Path) -> None:
    toml_path = project_root / "forge.toml"
    if not toml_path.exists():
        return

    text = toml_path.read_text()
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_pipeline = False
    in_model = False
    in_endpoint_repo = False
    pending_class: str | None = None  # holds class_name value while scanning model block

    def current_section(line: str) -> str | None:
        stripped = line.strip()
        if stripped == "[[pipelines]]":
            return "pipeline"
        if stripped == "[[models]]":
            return "model"
        if stripped == "[[endpoint_repos]]":
            return "endpoint_repo"
        if stripped.startswith("[[") or stripped.startswith("["):
            return "other"
        return None

    i = 0
    while i < len(lines):
        line = lines[i]
        section = current_section(line)

        if section == "pipeline":
            in_pipeline, in_model, in_endpoint_repo = True, False, False
            out.append(line)
            i += 1
            continue

        if section == "model":
            in_pipeline, in_model, in_endpoint_repo = False, True, False
            pending_class = None
            out.append(line)
            i += 1
            continue

        if section == "endpoint_repo":
            in_pipeline, in_model, in_endpoint_repo = False, False, True
            out.append(line)
            i += 1
            continue

        if section == "other":
            in_pipeline, in_model, in_endpoint_repo = False, False, False
            out.append(line)
            i += 1
            continue

        # ── pipeline block: rename `name` → `display_name` ───────────────────
        if in_pipeline:
            m = re.match(r'^(name\s*=\s*)(.+)$', line.rstrip('\n'))
            if m:
                out.append(f"display_name = {m.group(2)}\n")
                i += 1
                continue

        # ── model block: collapse name+class → class_name ────────────────────
        if in_model:
            # `class = "X"` → `class_name = "X"` (and drop `name = "X"`)
            m_class = re.match(r'^class\s*=\s*(.+)$', line.rstrip('\n'))
            if m_class:
                # emit class_name only if we haven't already from a `name =` line
                if pending_class is None:
                    out.append(f"class_name = {m_class.group(1)}\n")
                # else: class_name was already emitted when we saw `name =`; skip
                i += 1
                continue

            m_name = re.match(r'^name\s*=\s*(.+)$', line.rstrip('\n'))
            if m_name:
                # Tentatively emit class_name; it may be overridden by a `class =` line
                pending_class = m_name.group(1)
                out.append(f"class_name = {m_name.group(1)}\n")
                i += 1
                continue

        # ── endpoint_repo block: build module from name+path ─────────────────
        if in_endpoint_repo:
            m_path = re.match(r'^path\s*=\s*["\']?([^"\']+)["\']?', line.rstrip('\n'))
            if m_path:
                # Convert "./endpoint_repos/foo" → "endpoint_repos.foo"
                path_val = m_path.group(1).strip().lstrip("./").rstrip("/")
                module_val = path_val.replace("/", ".")
                out.append(f'module = "{module_val}"\n')
                i += 1
                continue

            m_name = re.match(r'^name\s*=\s*(.+)$', line.rstrip('\n'))
            if m_name:
                # Drop the `name` field; module will come from `path` (or synthesise below)
                # But if there is no `path` field in this block we need to emit module from name.
                # Peek ahead to see if path follows in the same block.
                j = i + 1
                has_path = False
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if next_stripped.startswith("[[") or next_stripped.startswith("["):
                        break
                    if re.match(r'^path\s*=', next_stripped):
                        has_path = True
                        break
                    j += 1
                if not has_path:
                    # synthesise module from name value
                    name_val = m_name.group(1).strip().strip('"\'')
                    out.append(f'module = "endpoint_repos.{name_val}"\n')
                # else: drop; module will be emitted when we hit path =
                i += 1
                continue

        out.append(line)
        i += 1

    toml_path.write_text("".join(out))
