from __future__ import annotations

from app.logging_config import get_logger

# The JSON formatter and the root-logger setup are the host's since
# segment 21A (A3); their cases are in `cordware/tests/test_logging.py`.


def test_get_logger_returns_named_logger() -> None:
    assert get_logger("app.foo").name == "app.foo"
