"""``app.db.schema_head.SCHEMA_HEAD`` is the migration chain's head
(segment 22G Item 1): a new migration updates the constant with it."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.schema_head import SCHEMA_HEAD

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_schema_head_is_the_chain_head() -> None:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == [SCHEMA_HEAD], (
        f"app/db/schema_head.py says {SCHEMA_HEAD!r}; the chain's head is {heads}. "
        "Set SCHEMA_HEAD to the new migration's revision."
    )
