"""The Telegram egress probe's page (`utilityapps/spec/utilities.md`
"Telegram egress probe"; the handover is
`utilityapps/docs/cordware_telegram_egress_probe_handover_v0.1.md`).

``GET`` explains and offers **Run probe**; it sends nothing. ``POST …/run``
makes one request to Telegram and shows the classified result, nothing
kept. Super-admin only, every response `no-store`. Runs start at least
``MIN_INTERVAL`` seconds apart across the process, and one runs at a time.
There is no feature flag: Utilities reads no setting, the super-admin gate
is the access control, and the page goes when Telegram Test replaces it.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from utilityapps.access import require_super_admin
from utilityapps.diagnostics import telegram_egress
from utilityapps.web import templates

log = logging.getLogger(__name__)

MIN_INTERVAL = 30.0
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
_SGT = timezone(timedelta(hours=8), "SGT")


class _Gate:
    """One probe at a time, and none starting within ``MIN_INTERVAL`` of the
    last start."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: float | None = None
        self._busy = False

    def wait_left(self, now: float) -> int:
        """Seconds to wait (0: claimed, run now, then ``release()``)."""
        with self._lock:
            if self._busy:
                return round(MIN_INTERVAL)
            if self._last is not None and now - self._last < MIN_INTERVAL:
                return max(1, round(MIN_INTERVAL - (now - self._last)))
            self._last, self._busy = now, True
            return 0

    def release(self) -> None:
        with self._lock:
            self._busy = False


gate = _Gate()
probe = telegram_egress.run  # replaced in tests, which never reach Telegram

router = APIRouter(prefix="/diagnostics", dependencies=[Depends(require_super_admin)])


def _page(request: Request, context: dict[str, object], status: int = 200) -> Response:
    return templates.TemplateResponse(
        request,
        "diagnostics/telegram_egress.html",
        {"host": telegram_egress.HOST, "interval": round(MIN_INTERVAL), **context},
        status_code=status,
        headers=_NO_STORE,
    )


@router.get("/telegram-egress", name="utilities_telegram_egress")
def explain(request: Request) -> Response:
    return _page(request, {})


@router.post("/telegram-egress/run")
async def run(request: Request) -> Response:
    left = gate.wait_left(time.monotonic())
    if left:
        return _page(request, {"wait": left}, status=429)
    correlation = uuid.uuid4().hex[:12]
    at = datetime.now(UTC)
    try:
        result = await run_in_threadpool(probe)
    finally:
        gate.release()
    log.info(
        "telegram egress probe outcome=%s status=%s elapsed_ms=%d error=%s correlation=%s",
        result.outcome.value,
        result.http_status,
        result.elapsed_ms,
        result.error_type or "-",
        correlation,
    )
    return _page(
        request,
        {
            "result": result,
            "correlation": correlation,
            "at_utc": at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "at_sgt": at.astimezone(_SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
        },
    )
