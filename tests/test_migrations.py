from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _config(database_url: str) -> Config:
    root = Path(__file__).parents[1]
    config = Config(root / "alembic.ini")
    config.attributes["database_url"] = database_url
    return config


def test_initial_migration_upgrades_and_downgrades_sqlite(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration-test.db'}"
    config = _config(database_url)

    command.upgrade(config, "head")
    command.check(config)

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "investigation_feedback",
        "investigations",
        "remediation_actions",
        "remediation_audit_events",
    }
    assert {
        index["name"] for index in inspector.get_indexes("investigations")
    } >= {"ix_investigations_tenant_id", "ix_investigations_created_at"}

    command.downgrade(config, "base")

    remaining = inspect(create_engine(database_url)).get_table_names()
    assert remaining == ["alembic_version"]
