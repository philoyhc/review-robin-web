"""Support Logs' sample data, for the placeholder screens of segment 1D
item 1 (`residentialapps/guide/segment_1D_support_logs.md`). Deleted in one
place by items 2–5.

Support Logs may not import Residential Operations
(`residentialapps/spec/architecture.md`, "Import boundaries"), so the
staff below are copied from the Staff roster's mock,
`residentialapps/docs/sample_data/staff_roster.csv`; a test holds the copy
to the file. Students and support content, as later rungs add them, are
invented and bland: nothing here may read as a real case."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

UNIT_NAME = "Example College"

# Support Logs' authorization types (functional spec §3.5; roles rules 1
# and 8), in the Access page's order. The super-admin holds administration
# from the platform, not as a grant (§3.4).
FRONTLINE = "Frontline"
SENIOR = "Senior identifiable"
RECIPIENT = "Safety-flag recipient"
CONSULTATION = "Consultation check"
VIEW_AGGREGATE = "Other Staff view: aggregate"
VIEW_IDENTIFIABLE = "Other Staff view: identifiable"
SYS_ADMIN = "Sys admin"
SUPER_ADMIN = "Super-admin"
VIEW = (VIEW_AGGREGATE, VIEW_IDENTIFIABLE)
ADMINISTRATION = (SYS_ADMIN, SUPER_ADMIN)


@dataclass(frozen=True)
class Viewer:
    name: str
    appointment: str  # from the Staff roster's mock; empty for the super-admin
    grants: frozenset[str]


# One sample viewer per authorization type; a frontline recipient (Priya
# Raman, whose dashboard lists every active flag); someone reaching two
# pages off the frontline (Nadia Hassan, whose Home lists them); the
# super-admin; and a rostered RF with no grant (the 403 page): access is a
# deliberate grant, never an appointment (§3.5).
VIEWERS = (
    Viewer("Daniel Koh", "RF", frozenset({FRONTLINE})),
    Viewer("Priya Raman", "RSLM", frozenset({FRONTLINE, RECIPIENT})),
    Viewer("Sam Lee", "Master", frozenset({SENIOR, RECIPIENT})),
    Viewer("Hui Min Goh", "Exec", frozenset({RECIPIENT})),
    Viewer("Marcus Tan", "RSLM", frozenset({CONSULTATION})),
    Viewer("Kenneth Lau", "RF", frozenset({VIEW_AGGREGATE})),
    Viewer("Siti Rahman", "RF", frozenset({VIEW_IDENTIFIABLE})),
    Viewer("Nadia Hassan", "RSLM", frozenset({CONSULTATION, VIEW_IDENTIFIABLE})),
    Viewer("Rachel Yeo", "Admin", frozenset({SYS_ADMIN})),
    Viewer("Platform super-admin", "", frozenset({SUPER_ADMIN})),
    Viewer("Wei Jie Ong", "RF", frozenset()),
)
DEFAULT = VIEWERS[0]


def viewer(name: str | None) -> Viewer:
    """The sample viewer a page is drawn for (`?as=`); the default for an
    unknown or absent name."""
    return next((v for v in VIEWERS if v.name == name), DEFAULT)


def as_query(v: Viewer) -> str:
    """The `?as=` every link carries, empty for the default viewer."""
    return "" if v == DEFAULT else f"?as={quote(v.name)}"


def holds(v: Viewer, *grants: str) -> bool:
    return bool(v.grants & set(grants))


def what(v: Viewer) -> str:
    """The viewer's access, as the sample card lists it."""
    if not v.grants:
        return f"{v.appointment}, no Support Logs access"
    held = ", ".join(g for g in (FRONTLINE, SENIOR, RECIPIENT, CONSULTATION, *VIEW, *ADMINISTRATION) if g in v.grants)
    return f"{v.appointment}: {held}" if v.appointment else held
