# Cordware Utilities

**Cordware Utilities** (package `utilityapps/`, mounted at `/utilities`):
small, general-purpose institutional tools that belong to neither Review
Robin nor Residential Apps. The package mounts and answers its health probe
and an index; the Email Address Checker, its first tool, is being built
(segment U1). Production does not carry it yet: Cordware's import rules
exclude `utilityapps/` until the author enables it.

**Graph, 2026-10-30** (Cordware's private progress report): with a user's
delegated token, a lookup by UPN works and a lookup by mail needs
`$filter=mail eq '…'`; calls from application code are not yet proved.
This is the checker spec's Phase 0, in part.

| Path | What it is |
|---|---|
| `main.py`, `routes_*.py`, `web.py`, `templates/` | The application: factory, routes, mount-aware URLs and templates |
| `email_check/` | The Email Address Checker: `csvio.py` (CSV in and out), `check.py` (lookup and classification), `routes.py` (the pages) |
| `tests/` | Utilities' tests; they build the host |
| `spec/utilities.md` | The application's contract: mount, health, index, import boundaries |
| `docs/email_address_checker_functional_spec_v0.1.md` | Email Address Checker, functional spec v0.1 (proposed, 2026-10-30): CSV in, CSV out, each address checked against the directory for its primary email and duplicated accounts; read-only, super-admin only |
| `guide/U1_browser_checks.md` | Segment U1's browser walkthrough: the index and a check end to end against the fake directory, with the PowerShell block that runs it; deleted when U1 closes |
| `guide/segment_U1_email_checker.md` | Segment U1 plan: the package mounted at `/utilities`, then the checker on a fake directory, with the shared Graph helper in `cordware/` |
