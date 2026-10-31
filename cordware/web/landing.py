"""The host's landing page at `/` (segment 21D; v0.8 §1).

It lists the mounted applications, not the ones a viewer may use: each
application gates its own routes, so the page requires no identity. It
renders whatever is mounted, one application included: the redirect a
lone application once took (author, 2026-10-21) is gone (author,
2026-10-31), since it hid the sign-in details on a deployment mounting
only one. An application mounted at `/` owns `/`, and the host adds
nothing there.

For diagnosis it shows who the request is signed in as, if anyone: the
address the applications match on, the UPN and the mail beside it
(author, 2026-10-26 and 2026-10-31). The raw claims Easy Auth passed
are a super-admin's alone, since they carry session internals; never
for the fake identity. The details are the viewer's own sign-in, so the
page is never cached.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from cordware.identity import current_identity, extract_claims

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@dataclass(frozen=True)
class LandingLink:
    """One mounted application as the landing page shows it."""

    title: str
    path: str
    icon: str = ""

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
        identity = current_identity(request)
        show_claims = identity is not None and not identity.is_fake and identity.is_super_admin
        response = _templates.TemplateResponse(
            request,
            "landing.html",
            {
                "links": [(link.title, f"{root}{link.href}", link.icon) for link in links],
                "identity": identity,
                "claims": extract_claims(request) if show_claims else [],
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response
