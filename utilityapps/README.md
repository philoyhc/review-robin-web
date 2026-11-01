# Cordware Utilities

**Cordware Utilities** (package `utilityapps/`, mounted at `/utilities`):
small, general-purpose institutional tools that belong to neither Review
Robin nor Residential Apps. Its first tool, the Email Address Checker, is
built (segment U1, closed 2026-10-30). Production carries its runtime code
from 2026-10-30: Cordware's import rules split `utilityapps/` and import
everything but its prose and tests. The import of 2026-10-31 brought the
favicon below. `/utilities/health` is excluded from
sign-in. Its first release is Cordware's interim one (2026-10-31): the host
and Utilities alone, deployed without migrations, with Review Robin off until
the full release deploy can migrate its database. The real-tenant smoke test
ran at that release and passed (Cordware's private records): a mail
address, a sign-in name and an unknown address came back `OK`,
`USE_PRIMARY` and `NOT_FOUND`, and a past class list of student addresses
classified the same way.

**Identity** (author, 2026-10-30): the name **Cordware Utilities**, mounted at
`/utilities`. Its accent is **amber `#b45309`**; white on it is about 5:1.
It is distinct from Cordware's black, Review Robin's blue, Residential
Operations' fuchsia and Support Logs' teal. The favicon is a white wrench on
a 32×32 amber rounded square, `rx` 7: Lucide's "wrench", mirrored, filled and
scaled 1.75, its head at top-left and its handle running off the bottom-right
like RRW's robin (author, 2026-11-01; the 2026-10-30 outline wrench before
it), inline in `templates/utilities/base.html`.

Rejected:
- Cordware's black cord, which would have made the tab identical to the
  landing page's (2026-10-30; the host's icon has since become a knot).
- The cord on a colored tile, which is unreadable at 16 px.

Amber can read as "warning", so alerts use the status token `--warn`, never
the accent.

**Graph, 2026-10-30 and 2026-10-31** (Cordware's private progress report):
with a user's delegated token, a lookup by UPN works and a lookup by mail
needs `$filter=mail eq '…'`. From 2026-10-31 the checker's combined query
runs from application code in production, for staff and student accounts.
This is the checker spec's Phase 0, done but for two cases not yet
exercised: a secondary alias, and the sign-in-again message once the
token's hour is up.

| Path | What it is |
|---|---|
| `main.py`, `routes_*.py`, `web.py`, `templates/` | The application: factory, routes, mount-aware URLs and templates |
| `email_check/` | The Email Address Checker: `csvio.py` (CSV in and out), `check.py` (lookup and classification), `routes.py` (the pages) |
| `tests/` | Utilities' tests; they build the host |
| `spec/utilities.md` | The application's contract: mount, health, index, import boundaries |
| `docs/email_address_checker_functional_spec_v0.1.md` | Email Address Checker, functional spec v0.1 (proposed, 2026-10-30): CSV in, CSV out, each address checked against the directory for its primary email and duplicated accounts; read-only, super-admin only |
| `guide/U1_browser_checks.md` | Segment U1's browser walkthrough: the index and a check end to end against the fake directory, with the PowerShell block that runs it; deleted when U1 closes |
| `guide/archive/segment_U1_email_checker.md` | Segment U1, closed 2026-10-30 (`#3406`→`#3411` and the close): the package and mount, the checker on a fake directory, and the shared Graph helper in `cordware/`. **Read `Status`** for the divergences and what the reads caught |
