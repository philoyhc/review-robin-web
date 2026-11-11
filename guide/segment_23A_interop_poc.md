# Segment 23A — Interoperability proof of concept: one click to a populated Review Robin session

**Opened:** 2026-11-11 · **Theme:** a temporary Utilities tool that holds mock rosters and, in one click, creates and populates a Review Robin draft session and opens it in a new tab · **Related:** `cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md` ("the interop spec"), `guide/interoperability.md`, `applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md`, `spec/quick_setup_card_spec.md`

## Opportunity

ApplyDesk's MVP is to hand its review to Review Robin (author, 2026-11-11) rather than build assessors, instruments and panels itself. That rests on the interop spec's **initiate** step, which no code has tried. Its riskiest parts need no ApplyDesk to test:

- **No JSON route on RRW.** RRW has no `/api/` routes and no JSON create route; every create is a form post that redirects (interop spec §13.3 item 4).
- **The new tab.** Opening a tab during the click, filling it in the background and moving it to Session Home has never been tried under Cordware's one-origin Easy Auth (interop spec §7.1).
- **RRW's create is not atomic.** `POST /operator/sessions` commits the session before its files are checked, so a refused file leaves an empty draft (`spec/quick_setup_card_spec.md`, "Failure mode").
- **No replay guard.** A double click today makes two sessions.

A proof of concept with fixed mock data answers these in days, before ApplyDesk exists. Later, ApplyDesk swaps its own export in for the mock.

## Decision

**A temporary Utilities tool, *Interop proof of concept*, at `/utilities/interop-poc/`.**

1. **The page.** It shows a fixed mock exercise: a scholarship with six applications and three reviewers, held as `reviewers.csv` and `reviewees.csv`.
2. **The button.** **Create in Review Robin** first opens a new tab, during the click, on an RRW holding page, `GET /reviewrobin/operator/handoffs/new`.
3. **The post.** The page then posts the bundle as JSON to a new RRW route, `POST /reviewrobin/operator/handoffs/sessions`.
4. **The create.** RRW checks that the person is an RRW operator. It creates a draft session owned by them and imports the rosters through Quick Setup's own pipeline (`_run_quick_setup_contents`). It answers with the session's ref and its Session Home URL.
5. **The tab.** The page moves the tab there.

The create prepares nothing, activates nothing, invites no one and sends no mail (interop spec §3 invariant 4).

It follows the spec's rulings (§13.1):
- **Rosters only:** no `settings.csv`.
- **One operator in both apps:** Utilities is super-admin only, and RRW needs its own operator flag. The super-admin is not assumed to be an RRW operator.
- **Each application has its own key:** the application ID goes in `RevieweeEmail` as an opaque identifier (§13.3 item 1).
- **A link back for reviewers:** `ProfileLink` holds a placeholder for the ApplyDesk reviewer view that would show the application. It is how RRW reviewers would later read an application (`spec/csv_contracts.md`, the Reviewees `ProfileLink` row).

**Rejected:**
- **A server-to-server call from Utilities to RRW.** That needs a cross-app credential or forwarded identity, which §7.1 rules out. It would also import `app` from `utilityapps`, which the boundary forbids.
- **A plain form post to RRW's existing New session route.** It works without JavaScript, but it gives no JSON receipt, no replay guard and no way to keep the user on the source page while the tab fills.
- **The interop spec's `/reviewrobin/api/v1/…` paths.** RRW has no API layer, and the operator package already supplies the operator gate to every route under it. The final paths are ApplyDesk's segment's to settle.

## Semantics

- **Bundle** (JSON, `Content-Type: application/json`, else `415`; over 1 MiB, `413`). It carries:
  - `protocol` `"cordware.csv-handoff"`, `protocol_version` `1` and `operation` `"reviewrobin.create_draft_session"`. Anything else is `422` `unsupported_version`.
  - `source_app`, and a `transfer_id` (a UUID).
  - `session_suggestion` `{name, code}`.
  - `files`, keyed by kind:
    - `reviewers` and `reviewees` are required. `relationships` and `observers` are optional.
    - `settings`, or any other kind, is `422` `invalid_package`.

  The CSVs go through RRW's own parsers and caps (`spec/csv_contracts.md`). No second parser is written.
- **Cross-site.** A JSON-only body, as the directory endpoints do. If the browser sends `Sec-Fetch-Site`, it must be `same-origin`, else `403`. An `Origin` check is not used, because the gateway rewrites the host the app sees (Cordware's forward-proxy setup).
- **Who may.** RRW's `require_operator`, which is the package gate. A non-operator gets RRW's usual `303` to `/me`, which the page reports as `not_authorized`. Utilities' page and bundle are super-admin only (`utilityapps/access.py`).
- **Create.** The same steps as New session, without the scheduling fields:
  - the owner-eligibility lock and `create_session`;
  - the slots through `_run_quick_setup_contents` with the session's directory (`directory_or_none`);
  - `session.handoff_created`, audited with `context` `{transfer_id, source_app}`.
- **Not atomic.** The session commits first and the rosters after, as New session does today. A refused roster leaves the draft, and the receipt says `invalid_setup` with the slot. Making the create atomic changes an existing page and needs a ruling (interop spec §13.4 item 2); see Open questions.
- **Replay.** A `transfer_id` already recorded on a `session.handoff_created` event by the same user returns that session as `already_created` (`200`). A different user is `409` `duplicate_conflict`. Two concurrent first posts can still make two sessions: accepted for a proof of concept, since the button disables on click.
- **Code.** The mock suggests `POC-<YYMMDD-HHMMSS>`. A taken code is `409` `session_code_conflict`.
- **Receipt.** `201` `{status: "created", session_ref, session_home_url}`. The URL is app-relative and emitted through `app/web/urls.py`. Errors are `{"error": <code>}`. Every response is `no-store`.
- **The tab.** If the browser blocks the new window, the page shows **Open the session** as a link once the receipt arrives. The holding page says what is happening and, alone, offers nothing to do.

## Judgment calls — decided

- The tool sits in Utilities, not a new `applydesk/` package: it is disposable, and ApplyDesk's package lands with its own segment.
- Replay is guarded by the audit row rather than a new table: no migration for a proof of concept.
- The mock's reviewers are synthetic `example.edu` addresses plus the signed-in super-admin. On production, the synthetic ones show as unresolved, which is itself what the test should see.

## Blast radius (measured)

Taken 2026-11-11 at `e96d006`.

| What | Count | Command |
|---|---|---|
| Operator routing slices, to gain `_handoffs.py` | 23 | `ls app/web/routes_operator/*.py \| wc -l` |
| The Quick Setup pipeline the create reuses | 1 (`_run_quick_setup_contents`) | `grep -n "async def _run_quick_setup_contents" app/web/routes_operator/_quick_setup.py` |
| Audit schema registry, to gain one event | 1 (`EVENT_SCHEMAS`, `app/services/audit.py:433`) | `grep -n "EVENT_SCHEMAS" app/services/audit.py` |
| Commits on the create path (why it is not atomic) | 2 (`create_session`, then Quick Setup's unit) | `grep -n "commit" app/services/sessions.py app/web/routes_operator/_quick_setup.py` |
| Live specs | 36 files in `spec/` | `ls spec \| wc -l` |

## PR ladder

1. **Scaffold.** The Utilities page shows the mock data, with **Create in Review Robin** inert, and a note of what will be sent and what will not happen. RRW's holding page is static. Neither is listed on an index. Tests: both routes, their gates, RRW's URL crawl and spec coverage. Not touched: any create.
2. **RRW create route.** `POST /operator/handoffs/sessions` as Semantics says: the bundle checks, the create through the existing services, the `session.handoff_created` event in `EVENT_SCHEMAS`, replay and the error codes. Tests cover each error, replay, a refused roster, `Sec-Fetch-Site`, a non-operator, and that no assignment, invitation or mail exists after it. Not touched: the Utilities page.
3. **Wire the button.** The page script opens the tab, builds the bundle, posts it, moves the tab and shows the receipt or the error, with the blocked-pop-up fallback. This is the item's last build rung: `diff-reviewer` reads the cumulative diff from rung 1's base.
4. **Close.** Specs, `spec-writer` and the archive.

## Definition of done

- Clicking **Create in Review Robin** on `/utilities/interop-poc/` opens a tab that lands on a new session's Session Home, with six reviewees and three reviewers, no assignments and no invitations. Verified on localhost by the author, and on production after an import.
- A second click of the same transfer returns the same session, and a refused roster reports `invalid_setup`. Both are covered by tests in `tests/integration/test_handoffs.py`.
- `utilityapps/tests/test_interop_poc.py` covers the page, its gate and its bundle.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Atomic create** (a session and its rosters in one transaction) changes New session's behavior too. Ruled by the author before ApplyDesk's handoff, not here.
- **Retiring the tool.** Does it stay once ApplyDesk's handoff exists, or go? Author, at ApplyDesk's first handoff segment.

## Out of scope

- **Status, the `Import Review Robin results` step and settings or instruments.** The interop spec's observe and retrieve steps, and its D1 and D2 gates, wait for ApplyDesk.
- **Signed source proof (D3).** The package is labeled operator-supplied, and nothing claims a verified source.
- **The ApplyDesk package and reviewer view.** `ProfileLink` points at a placeholder.

## Doc impact

- `spec/handoffs.md` — new: the proof-of-concept create route, its bundle, receipts, errors, replay and its non-atomic create; a row in `spec/README.md`.
- `spec/permissions.md` — the new operator routes in the route table.
- `spec/architecture.md` — `session.handoff_created` in the audit-event list.
- `utilityapps/spec/utilities.md` — the *Interop proof of concept* page row and section.
- `guide/interoperability.md` — what the proof of concept settled for the revisit.
- `guide/todo_master.md` — the queue entry, deleted at close.
