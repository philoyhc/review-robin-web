"""``email_overrides.*`` parse + apply."""
from __future__ import annotations

from app.db.models import ReviewSession
from app.services.email_templates import (
    OVERRIDE_KEYS,
    RESPONSES_RECEIVED_ENABLED_KEY,
)

from ._apply_shared import (
    _RX_EMAIL,
    _ParsedConfig,
    _ParseError,
    _parse_bool,
)


def _apply_email_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    match = _RX_EMAIL.match(field_path)
    if match is None:
        raise _ParseError(f"unrecognised email_overrides key {field_path!r}")
    kind, slot = match.group(1), match.group(2)
    if slot == "enabled":
        # ``responses_received.enabled`` boolean; the legacy
        # ``responses_received_enabled`` key in the JSON dict is
        # the canonical home (matches the resolver).
        plan.email_overrides[RESPONSES_RECEIVED_ENABLED_KEY] = _parse_bool(
            value, default=True
        )
        return
    legacy_key = f"{kind}_{slot}"
    if legacy_key not in OVERRIDE_KEYS:
        raise _ParseError(
            f"unknown email override slot {field_path!r}"
        )
    if value:
        plan.email_overrides[legacy_key] = value
    # Empty cell ⇒ key absent ⇒ "use default" (matches resolver).
    del data_type  # unused; cell is always string here


def _apply_email_overrides(
    review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Replace ``email_template_overrides`` JSON wholesale from
    the parsed dict. Empty cells collapsed into "key absent" by
    the parser, so the dict is the resolver-ready shape."""

    review_session.email_template_overrides = (
        dict(plan.email_overrides) if plan.email_overrides else None
    )
    return len(plan.email_overrides)
