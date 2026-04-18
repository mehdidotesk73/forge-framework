"""Version migration system for Forge framework upgrades."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from packaging.version import Version


@dataclass
class Migration:
    from_version: str
    to_version: str
    description: str
    migrate: Callable[[Path], None]


_MIGRATIONS: list[Migration] = []


def register_migration(
    from_version: str,
    to_version: str,
    description: str,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        _MIGRATIONS.append(Migration(
            from_version=from_version,
            to_version=to_version,
            description=description,
            migrate=func,
        ))
        return func
    return decorator


class MigrationRunner:
    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self._state_file = project_root / ".forge" / "migration_state.json"

    def get_current_version(self) -> str:
        if self._state_file.exists():
            data = json.loads(self._state_file.read_text())
            return data.get("forge_version", "0.0.0")
        # Fall back to forge.toml
        toml_path = self.root / "forge.toml"
        if toml_path.exists():
            import sys
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            with open(toml_path, "rb") as f:
                raw = tomllib.load(f)
            return raw.get("project", {}).get("forge_version", "0.0.0")
        return "0.0.0"

    def set_current_version(self, version: str) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"forge_version": version}))

    def get_pending_migrations(self, target_version: str) -> list[Migration]:
        current = Version(self.get_current_version())
        target = Version(target_version)
        pending = [
            m for m in _MIGRATIONS
            if Version(m.from_version) >= current and Version(m.to_version) <= target
        ]
        return sorted(pending, key=lambda m: Version(m.from_version))

    def run_migrations(self, target_version: str) -> list[str]:
        pending = self.get_pending_migrations(target_version)
        applied = []
        for migration in pending:
            migration.migrate(self.root)
            applied.append(f"{migration.from_version} → {migration.to_version}: {migration.description}")
            self.set_current_version(migration.to_version)
        if not applied:
            self.set_current_version(target_version)
        return applied
