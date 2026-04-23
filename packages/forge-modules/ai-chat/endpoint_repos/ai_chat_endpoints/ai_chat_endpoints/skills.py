"""Skill file management — loading, writing, dependency resolution.

Two skill locations are checked in priority order:
  1. {project_root}/.forge/skills/ai_chat/       — mutable; written by the train loop
  2. {project_root}/skills/                       — read-only defaults shipped with this module

Skill files are Markdown with YAML frontmatter (name, description, version,
depends_on, triggers). The Markdown body is freeform structured content that
the LLM reads as instructions to itself.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ── Package-default skills dir ────────────────────────────────────────────────
# The skills/ directory sits at the root of the ai-chat module project.
# We locate it relative to this file: endpoint_repos/ai_chat_endpoints/ai_chat_endpoints/
# → ../../.. → module root → skills/
_MODULE_ROOT: Path = Path(__file__).parent.parent.parent.parent
PACKAGE_SKILLS_DIR: Path = _MODULE_ROOT / "skills"


def _project_skills_dir() -> Path | None:
    """Return .forge/skills/ai_chat/ inside the current Forge project, or None."""
    try:
        from forge.config import find_project_root
        root = find_project_root()
        d = root / ".forge" / "skills" / "ai_chat"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        return None


# ── Frontmatter parsing ───────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


def _write_frontmatter(meta: dict, body: str) -> str:
    fm = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{body}\n"


# ── Listing ───────────────────────────────────────────────────────────────────

def list_all_skills() -> list[dict]:
    """Return metadata dicts for all available skills. Project overrides package defaults."""
    seen: set[str] = set()
    skills: list[dict] = []

    proj_dir = _project_skills_dir()
    if proj_dir:
        for path in sorted(proj_dir.glob("*.md")):
            meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            skill_id = meta.get("name") or path.stem
            if skill_id in seen:
                continue
            seen.add(skill_id)
            skills.append({**meta, "name": skill_id, "source": "project", "file_path": str(path)})

    if PACKAGE_SKILLS_DIR.exists():
        for path in sorted(PACKAGE_SKILLS_DIR.glob("*.md")):
            meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            skill_id = meta.get("name") or path.stem
            if skill_id in seen:
                continue
            seen.add(skill_id)
            skills.append({**meta, "name": skill_id, "source": "package", "file_path": str(path)})

    return skills


# ── Single skill access ───────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


def load_skill(skill_name: str) -> tuple[dict, str] | None:
    """Load a skill by name. Returns (meta, body) or None."""
    norm = _normalize(skill_name)

    proj_dir = _project_skills_dir()
    if proj_dir:
        for path in proj_dir.glob("*.md"):
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if _normalize(meta.get("name", path.stem)) == norm:
                return meta, body

    if PACKAGE_SKILLS_DIR.exists():
        for path in PACKAGE_SKILLS_DIR.glob("*.md"):
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if _normalize(meta.get("name", path.stem)) == norm:
                return meta, body

    return None


def load_skill_tree(skill_name: str, _visited: set[str] | None = None) -> dict[str, tuple[dict, str]]:
    """Recursively load a skill and all its declared dependencies."""
    visited = _visited if _visited is not None else set()
    norm = _normalize(skill_name)
    if norm in visited:
        return {}
    visited.add(norm)

    skill = load_skill(skill_name)
    if skill is None:
        return {}

    meta, body = skill
    result: dict[str, tuple[dict, str]] = {meta.get("name", skill_name): (meta, body)}
    for dep in meta.get("depends_on") or []:
        result.update(load_skill_tree(dep, visited))
    return result


# ── Trigger matching ──────────────────────────────────────────────────────────

def match_skills_to_prompt(prompt: str) -> list[str]:
    prompt_lower = prompt.lower()
    matched: list[str] = []
    for skill_meta in list_all_skills():
        for trigger in skill_meta.get("triggers") or []:
            if trigger.lower() in prompt_lower:
                matched.append(skill_meta["name"])
                break
    return matched


def build_skill_context(skill_names: list[str]) -> str:
    if not skill_names:
        return ""
    all_loaded: dict[str, tuple[dict, str]] = {}
    for name in skill_names:
        all_loaded.update(load_skill_tree(name))

    sections: list[str] = []
    for name, (meta, body) in all_loaded.items():
        header = f"## Skill: {meta.get('name', name)}"
        if meta.get("description"):
            header += f"\n*{meta['description']}*"
        sections.append(f"{header}\n\n{body}")
    return "\n\n---\n\n".join(sections)


# ── Writing ───────────────────────────────────────────────────────────────────

def _skill_path_in_project(skill_name: str, proj_dir: Path) -> Path | None:
    norm = _normalize(skill_name)
    for path in proj_dir.glob("*.md"):
        if _normalize(path.stem) == norm:
            return path
    return None


def write_skill(skill_name: str, meta: dict, body: str) -> Path:
    """Write or update a skill file in the project-local skills directory.

    Archives the previous version before overwriting and increments version number.
    """
    proj_dir = _project_skills_dir()
    if proj_dir is None:
        raise RuntimeError(
            "Cannot find the Forge project root — skill files cannot be written."
        )

    existing = load_skill(skill_name)
    if existing:
        old_meta, _ = existing
        old_version = old_meta.get("version", 0)
        new_version = old_version + 1
        old_path = _skill_path_in_project(skill_name, proj_dir)
        if old_path and old_path.exists():
            archive_dir = proj_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            shutil.copy2(old_path, archive_dir / f"{old_path.stem}.v{old_version}.md")
    else:
        new_version = 1

    full_meta = {
        "name": skill_name,
        "description": meta.get("description", ""),
        "version": new_version,
        "depends_on": meta.get("depends_on") or [],
        "triggers": meta.get("triggers") or [],
        **{k: v for k, v in meta.items() if k not in ("name", "description", "version", "depends_on", "triggers")},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    path = proj_dir / (_normalize(skill_name) + ".md")
    path.write_text(_write_frontmatter(full_meta, body), encoding="utf-8")
    return path


# ── Index data builder (used by the pipeline) ─────────────────────────────────

def build_index_rows() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for skill_meta in list_all_skills():
        rows.append({
            "id":              _normalize(skill_meta.get("name", "unknown")),
            "name":            skill_meta.get("name", ""),
            "description":     skill_meta.get("description", "") or "",
            "version":         int(skill_meta.get("version", 1)),
            "depends_on":      json.dumps(skill_meta.get("depends_on") or []),
            "triggers":        json.dumps(skill_meta.get("triggers") or []),
            "file_path":       skill_meta.get("file_path", ""),
            "source":          skill_meta.get("source", "package"),
            "last_indexed_at": now,
        })
    return rows
