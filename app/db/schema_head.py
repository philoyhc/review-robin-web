"""The Alembic revision this code expects the database to be at
(segment 22G Item 1), for the System Status tab.

The deploy ships no ``alembic/`` beside the code (the host keeps
migration files off the import path), so the running app cannot read
the head from its scripts. ``tests/unit/test_schema_head.py`` fails when
this differs from ``alembic heads``: a new migration updates it in the
same change.
"""

SCHEMA_HEAD = "a3d7f1c9e2b4"
