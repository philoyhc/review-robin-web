# Cordware Utilities

The Email Address Checker's contract is `utilityapps/spec/email_check.md`.

The contract of the Utilities application as the Cordware host sees it.
The host's side is `cordware/spec/host.md`; this file states only what
Utilities adds. The design it follows is
`utilityapps/docs/email_address_checker_functional_spec_v0.1.md` §1 and §9.

## One application, one mount

| | Utilities |
|---|---|
| Registry name | `utilities` |
| Mount path | `/utilities` |
| Factory | `utilityapps.main:create_app` |
| Logger prefix | `utilityapps` |
| Landing-page title | `Utilities` |
| Health | `GET /utilities/health`, route name `utilities_health` |

- The registry lists it last, after Residential's two, so an unset
  `CORDWARE_APPS` mounts it last and the landing page lists it so.
- The factory is a zero-argument callable returning a new `FastAPI`
  application with no schema pages. It reads no setting and opens no
  database: Utilities has none (spec §9).
- Each tool is a feature module inside this one application. A tool with
  a materially different trust boundary becomes its own mount instead.

## Health

`/utilities/health` answers `{"status": "ok"}` with no identity, no
setting and no Graph call, so Easy Auth can exclude it from sign-in, as it
does the other applications' probes. Adding it to the exclusions is
Cordware's private deployment step.

## Pages

| Page | Path | Reached by |
|---|---|---|
| Index | `/` (the bare mount) | Anyone Easy Auth lets in: the route checks no identity itself, since it names tools and holds nothing about anyone. Each tool gates its own routes. |
| Email Address Checker | `/email-check/` and the steps it posts to | The platform super-admin only (`utilityapps/spec/email_check.md` "Access") |

The index lists one card per tool, linking to its first page. Every page
links back to the host's landing page (`/`) and to `/.auth/logout`.

Templates write app paths through `url()` in `utilityapps/web.py`, which
adds the mount's prefix; `host_url()` marks a path that is the host's.

## Import boundaries

Enforced by `cordware/tests/test_import_boundary.py`:

- `utilityapps` imports neither `app` (Review Robin) nor `residentialapps`,
  and neither of them imports it. It may import `cordware`, never
  `cordware.main`, except in `utilityapps/tests/`, which builds the host.
- `cordware` imports it only through the registry's factory string.
