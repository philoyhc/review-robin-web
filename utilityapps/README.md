# Cordware Utilities

A proposed Cordware cluster, **Cordware Utilities** (package `utilityapps/`,
mounted at `/utilities`), for small, general-purpose institutional tools that
belong to neither Review Robin nor Residential Apps. Nothing is built or
mounted yet: this folder holds its design documents only.

**Graph, 2026-10-30** (Cordware's private progress report): with a user's
delegated token, a lookup by UPN works and a lookup by mail needs
`$filter=mail eq '…'`; calls from application code are not yet proved.
This is the checker spec's Phase 0, in part.

| Path | What it is |
|---|---|
| `docs/email_address_checker_functional_spec_v0.1.md` | Email Address Checker, functional spec v0.1 (proposed, 2026-10-30): CSV in, CSV out, each address checked against the directory for its primary email and duplicated accounts; read-only, super-admin only |
| `guide/segment_U1_email_checker.md` | Segment U1 plan: the package mounted at `/utilities`, then the checker on a fake directory, with the shared Graph helper in `cordware/` |
