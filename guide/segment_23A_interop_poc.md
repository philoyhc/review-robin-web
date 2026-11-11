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
- **All or nothing** (author, 2026-11-11). A handoff create leaves either a session with every roster or nothing at all. A refused roster is `422` `invalid_setup`, and the body carries the slot and the importer's own issue lines, so the sending app can show the operator why. New session's own behavior is not changed (`spec/quick_setup_card_spec.md`, "Failure mode"). How it is done (one unit, or the draft removed on refusal) is rung 2's to choose, and is recorded in Judgment calls.
- **Replay.** A `transfer_id` already recorded on a `session.handoff_created` event by the same user returns that session as `already_created` (`200`). A different user is `409` `duplicate_conflict`. Two concurrent first posts can still make two sessions: accepted for a proof of concept, since the button disables on click.
- **Code.** The mock suggests `POC-<YYMMDD-HHMMSS>`. A taken code is `409` `session_code_conflict`.
- **Receipt.** `201` `{status: "created", session_ref, session_home_url}`. The URL is app-relative and emitted through `app/web/urls.py`. Errors are `{"error": <code>}`. Every response is `no-store`.
- **Kept as a model.** The tool stays once ApplyDesk's handoff exists (author, 2026-11-11), a working reference for the next app that hands work to Review Robin.
- **The tab.** If the browser blocks the new window, the page shows **Open the session** as a link once the receipt arrives. The holding page says what is happening and, alone, offers nothing to do.

## Judgment calls — decided

- The tool sits in Utilities, not a new `applydesk/` package: it is disposable, and ApplyDesk's package lands with its own segment.
- Replay is guarded by the audit row rather than a new table: no migration for a proof of concept.
- All or nothing by discarding the draft on a refusal, not by one transaction: New session's two commits stay, so its own behavior is untouched (rung 2, 2026-11-11).
- A replay never deletes: a transfer cut off before its rosters answers `409 transfer_incomplete` with the draft's link, and completion is a recorded event, not inferred from roster counts, which an operator may clear (Codex, #3780).
- A replay re-checks `permissions.user_can_view_session`: the sender once is not the operator now (Codex, #3780).
- The sender keeps its transfer on a `5xx`, a network error or an unreadable answer; any other refusal starts a new one (cold read; Codex, #3781).
- The mock's reviewers are synthetic `example.edu` addresses plus the signed-in super-admin. On production, the synthetic ones show as unresolved, which is itself what the test should see.

## Blast radius (measured)

Taken 2026-11-11 at `e96d006`.

| What | Count | Command |
|---|---|---|
| Operator routing slices, to gain `_handoffs.py` | 23 | `ls app/web/routes_operator/*.py \| wc -l` |
| The Quick Setup pipeline the create reuses | 1 (`_run_quick_setup_contents`) | `grep -n "async def _run_quick_setup_contents" app/web/routes_operator/_quick_setup.py` |
| Audit schema registry, to gain one event | 1 (`EVENT_SCHEMAS`, `app/services/audit.py:433`) | `grep -n "EVENT_SCHEMAS" app/services/audit.py` |
| Commits on the create path (New session's, which the handoff keeps; its all-or-nothing is a discard) | 2 (`create_session`, then Quick Setup's unit) | `grep -n "commit" app/services/sessions.py app/web/routes_operator/_quick_setup.py` |
| Live specs | 36 files in `spec/` | `ls spec \| wc -l` |

## Status

**Closed 2026-11-11.** The ladder shipped as planned: rung 1 #3779, rung 2 #3780, rung 3 #3781, rung 4 this close.

- **Intended vs done.** As Semantics says, plus a second audit event, `session.handoff_completed`, and the error codes `directory_sign_in`, `transfer_incomplete` and `invalid_setup`'s `empty_roster` reason (`spec/handoffs.md`). The replay and completion rules live in `app/services/handoffs.py`; the route only translates (Codex, #3780).
- **The mock has four reviewers**, not three: the signed-in operator is added so the session has a reviewer who can sign in. The definition of done's count reads accordingly.
- **Verified** in local Chromium with fake auth: the tab lands on Session Home with 4 reviewers and 6 reviewees, no assignments, no invitations; a mocked `transfer_incomplete` shows its draft link. Localhost and production checks are the author's.
- **Reads.** One `diff-reviewer` read of rungs 1–3's cumulative diff, before rung 2 merged: 8 findings, all fixed (a deep-nested body and a lone surrogate as 500s; an undeclared length; an exception or empty roster leaving a draft; the replay record written late; a lapsed directory sign-in labelled a refused file; `Sec-Fetch-Site: none` accepted; the page dropping its transfer on a `5xx`). Codex then found 7 on #3780 (surrogate, cancellation, roster-count completion, stale-actor replay, rules in the route, NUL, an unescaped unknown key) and 1 on #3781 (an unreadable receipt); all fixed.
- **Carried to the revisit** (`guide/interoperability.md` §4): concurrent first posts of one transfer, and a first-visit race in `get_or_create_user` on a brand-new user.

## PR ladder

1. **Scaffold.** The Utilities page shows the mock data, with **Create in Review Robin** inert, and a note of what will be sent and what will not happen. RRW's holding page is static. Neither is listed on an index. Tests: both routes, their gates, RRW's URL crawl and spec coverage. Not touched: any create.
2. **RRW create route.** `POST /operator/handoffs/sessions` as Semantics says: the bundle checks, the create through the existing services, the `session.handoff_created` event in `EVENT_SCHEMAS`, replay and the error codes. Tests cover each error, replay, a refused roster, `Sec-Fetch-Site`, a non-operator, and that no assignment, invitation or mail exists after it. Not touched: the Utilities page.
3. **Wire the button.** The page script opens the tab, builds the bundle, posts it, moves the tab and shows the receipt or the error (an `invalid_setup` with its slot and issue lines), with the blocked-pop-up fallback. This is the item's last build rung: `diff-reviewer` reads the cumulative diff from rung 1's base.
4. **Close.** Specs, `spec-writer` and the archive.

## Definition of done

- Clicking **Create in Review Robin** on `/utilities/interop-poc/` opens a tab that lands on a new session's Session Home, with six reviewees and four reviewers (three plus the operator), no assignments and no invitations. Verified on localhost by the author, and on production after an import.
- A second click of the same transfer returns the same session, and a refused roster reports `invalid_setup` with its slot and issue lines and leaves no session. Both are covered by tests in `tests/integration/test_handoffs.py`.
- `utilityapps/tests/test_interop_poc.py` covers the page, its gate and its bundle.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Atomic create~~ All or nothing for the handoff create, with the refusal's reasons returned to the sending app (author, 2026-11-11). New session unchanged.
- ~~Retiring the tool~~ It stays as a model once ApplyDesk's handoff exists (author, 2026-11-11).

## Out of scope

- **Status, the `Import Review Robin results` step and settings or instruments.** The interop spec's observe and retrieve steps, and its D1 and D2 gates, wait for ApplyDesk.
- **Signed source proof (D3).** The package is labeled operator-supplied, and nothing claims a verified source.
- **The ApplyDesk package and reviewer view.** `ProfileLink` points at a placeholder.

## Doc impact

- `spec/handoffs.md` — new: the proof-of-concept create route, its bundle, receipts, errors, replay and its all-or-nothing create; a row in `spec/README.md`.
- `spec/permissions.md` — the new operator routes in the route table.
- `spec/architecture.md` — `session.handoff_created` and `session.handoff_completed` with the `counts` envelope's events.
- `utilityapps/spec/utilities.md` — the *Interop proof of concept* page row and section.
- `guide/interoperability.md` — what the proof of concept settled for the revisit (§4).
- `app/web/spec_registry.py` — `_handoffs` and `_quick_setup` map to `spec/handoffs.md`; the declared debt is cleared.
- `guide/todo_master.md` — the queue entry, deleted at close.
