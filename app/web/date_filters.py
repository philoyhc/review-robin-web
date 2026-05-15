"""Context-aware date / time Jinja filters + the display-timezone
context processor (Segment 18B PR 2).

The ``format_datetime`` / ``format_date`` filters resolve their
display zone from the Jinja render context's ``display_timezone``
key, which the context processor injects from
``request.state.display_timezone``. ``get_or_create_user``
(``app/web/deps.py``) stamps that state value with the signed-in
operator's default zone; absent ⇒ ``UTC``.

Keeping the ``@pass_context`` wiring here (not in
``app/services/date_formatting.py``) leaves the service module
template-engine-agnostic — it only knows zone names.
"""

from __future__ import annotations

from datetime import date, datetime

import jinja2
from starlette.requests import Request

from app.services import date_formatting

DEFAULT_TIMEZONE = date_formatting.DEFAULT_TIMEZONE


def display_timezone_context_processor(request: Request) -> dict[str, str]:
    """Inject ``display_timezone`` into every template render."""
    return {
        "display_timezone": getattr(
            request.state, "display_timezone", DEFAULT_TIMEZONE
        )
    }


def _context_zone(context: jinja2.runtime.Context) -> str:
    return context.get("display_timezone") or DEFAULT_TIMEZONE


@jinja2.pass_context
def format_datetime_filter(
    context: jinja2.runtime.Context, value: datetime | None
) -> str:
    return date_formatting.format_datetime(value, _context_zone(context))


@jinja2.pass_context
def format_date_filter(
    context: jinja2.runtime.Context, value: date | datetime | None
) -> str:
    return date_formatting.format_date(value, _context_zone(context))
