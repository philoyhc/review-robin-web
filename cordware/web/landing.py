"""The host's landing page at `/` (segment 21D; v0.8 §1).

It lists the mounted applications, not the ones a viewer may use: each
application gates its own routes, so the page checks no identity. With
exactly one application mounted there is nothing to choose between, and
`/` redirects to it (author, 2026-10-21). An application mounted at `/`
owns `/`, and the host adds nothing there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@dataclass(frozen=True)
class LandingLink:
    """One mounted application as the landing page shows it."""

    title: str
    path: str

    @property
    def href(self) -> str:
        """The application's root, with the slash its own `/` route needs."""
        return self.path if self.path.endswith("/") else f"{self.path}/"


def add_landing_page(host: FastAPI, links: Sequence[LandingLink]) -> None:
    """Register `/` on ``host`` unless an application is mounted there.

    Call it before mounting, so the host's `/` answers ahead of a mount."""
    if any(link.path == "/" for link in links):
        return

    @host.get("/", include_in_schema=False, name="cordware_landing")
    def landing(request: Request) -> Response:
        root = request.scope.get("root_path", "")
        if len(links) == 1:
            return RedirectResponse(f"{root}{links[0].href}", status_code=302)
        return _templates.TemplateResponse(
            request,
            "landing.html",
            {"links": [(link.title, f"{root}{link.href}") for link in links]},
        )
