"""Alembic migration-chain invariants shared by all supported databases."""

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_revision_ids_fit_alembic_default_version_column() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    oversized = {
        revision.revision: len(revision.revision)
        for revision in scripts.walk_revisions()
        if len(revision.revision) > 32
    }

    assert oversized == {}
