from forge.migrations.base import Migration, MigrationRunner, register_migration
import forge.migrations.v0_1_0_toml_schema  # noqa: F401 — registers migration on import

__all__ = ["Migration", "MigrationRunner", "register_migration"]
