# Segment 23B — Interoperability proof of concept: status and results back to the sender

**Opened:** 2026-11-11 · **Theme:** the reverse flow of 23A's handoff: the sending application reads a handed-off session's live status and pulls its submitted results, tried in the same Utilities tool · **Related:** `guide/archive/segment_23A_interop_poc.md`, `spec/handoffs.md`, `cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md` ("the interop spec") §6.4–§6.6, §10.2 (D2, D4), `guide/interoperability.md` §4

## Opportunity

23A proved the **initiate** step: one click turns another application's rosters into a Review Robin draft. ApplyDesk's MVP also needs the other half:

- **Status.** While Review Robin runs the review, ApplyDesk shows its progress (interop spec §6.4).
- **Results.** When it is done, ApplyDesk imports the submitted answers against each application (§6.5).

Neither has any code. RRW's nearest output, `responses.csv`, is not a feed: `InstrumentName` is positional (`instrument_{n}`), and `Version` resets after a clear (§6.5, "Important existing RRW export limitation"). A proof of concept settles the transport, the keys and the permission check before ApplyDesk exists.

## Decision

**Pull on the operator's view, not push.** The sender asks; Review Robin answers, over the same browser-mediated, same-origin transport as 23A's create (§7.1). Two read routes, both keyed by the handoff's `transfer_id`:

1. **`GET /operator/handoffs/{transfer_id}/status`** — a JSON status projection: the session, its lifecycle state, counts with their denominators and an as-of time. No answers.
2. **`GET /operator/handoffs/{transfer_id}/results`** — a JSON results snapshot: a manifest, one row per submitted answer, and one completion row per assignment. Audited as an export.

The Utilities tool keeps the transfers it created (in the browser, for the proof of concept) and offers **Refresh status** and **Fetch results** on each.

"Review Robin sending status updates" (author, 2026-11-11) is met by the sender reading status when its page loads or on a click. The interop spec asks for exactly that: no background synchronization (§6.4).

**Rejected:**
- **Push from Review Robin** (a webhook or server call to ApplyDesk when something changes). Review Robin would need ApplyDesk's address and a credential to call it, a cross-app credential §7.1 rules out, and a delivery queue. A later notification (the Telegram channel, item 22 of Cordware's temp to-do list) can tell an operator to look; it carries no data.
- **Keying by session ref.** A free session ID would let a sender read any session its operator happens to own (§6.6, "Never allow a free-text RRW session ID"). The `transfer_id` names only a session made by that handoff.
- **`responses.csv` as the payload.** It is positional and analysis-shaped; the snapshot is built beside it from the same reads, and `responses.csv` stays as it is (`guide/interoperability.md` §1).

## Semantics

- **Link and permission.** A route resolves `transfer_id` through `session.handoff_created` (`handoffs.prior_transfer`). An unknown transfer, or one whose session is gone, is `404 not_linked`. The caller must operate that session now (`permissions.user_can_view_session`), else `403 not_authorized`, as 23A's replay. An unfinished transfer (no `session.handoff_completed`) is `409 transfer_incomplete`. Both routes answer JSON, `no-store`, under the package gate.
- **Status** (`status_schema_version` 1): `session_ref`, `session_code`, `name`, lifecycle `state` (the enum) and its display label, `session_home_url`, `as_of`, and counts:
  - `reviewers`, `reviewees`, `instruments`;
  - `assignments` (obligations), and of those, `assignments_submitted`;
  - `reviewers_assigned`, then of those `reviewers_invited`, `reviewers_opened` and `reviewers_submitted` (`monitoring.summary_counts`).

  Every count names its denominator, and there is no single percentage (D4). A read changes nothing: no lazy lifecycle step runs, so status reports what the clock (14E) has already done.
- **Results** (`result_schema_version` 1):
  - **Manifest:** `session_ref`, `transfer_id`, `as_of`, `scope` (`submitted`), `complete` (true), row counts, and a SHA-256 `digest` of the rows.
  - **Answer rows:** submitted answers only (§6.5: drafts excluded, missing stays missing). Each row is keyed by `reviewer_email`, `reviewee_key` (`Reviewee.email_or_identifier`, the application ID), `instrument_seq` (`Instrument.session_seq`) and `field_key`, and carries `instrument_label`, `field_label`, `response_type`, `value` and `submitted_at`.
  - **Completion rows:** one per assignment, with `reviewer_email`, `reviewee_key`, `instrument_seq` and `state` (`not_started` / `in_progress` / `submitted`). No answers.
- **Group-scoped instruments** are left out of both row sets and counted in the manifest (`excluded_group_instruments`): group-to-application meaning is undefined (§6.5).
- **Keys.** `instrument_seq` + `field_key` is stable (interop spec §13.3 item 2). An answer has no ID of its own: `Version` resets after a clear. A snapshot is therefore a complete replacement, and the receiver reconciles on (`reviewer_email`, `reviewee_key`, `instrument_seq`, `field_key`). That is D2's proof-of-concept answer; ApplyDesk's segment settles it.
- **Audit.** A results fetch writes `session.handoff_results_exported` (`counts` of rows; `context` `{transfer_id, digest}`). A status read writes nothing: reads never audit (`spec/permissions.md` §6).
- **The page.** A failed refresh shows *unavailable, last checked …*, never old counts as current and never zero (§6.4). *Status last checked at T* and *results fetched at U* are shown apart. Fetched results show as a table and download as CSV. Nothing is stored server-side.

## Judgment calls — decided

- JSON for both routes, not a ZIP: the browser fetches them same-origin and the page renders them. The receiving format is ApplyDesk's segment's to settle (§6.5 allows "one normalized CSV, several CSVs …").
- The Utilities page keeps its transfers in `localStorage`. Utilities has no database, and ApplyDesk will store the link itself. Clearing the browser loses the list, not the sessions.
- The routes live in `_handoffs.py` (the holding page's slice): they run no Quick Setup pipeline. The projections are `app/services/handoffs.py` functions over `monitoring` and the response reads.

## Blast radius (measured)

Taken 2026-11-11 at `732b9ab`.

| What | Count | Command |
|---|---|---|
| Functions in the handoff service, to gain the two projections | 12 | `grep -c "def " app/services/handoffs.py` |
| The status counts it reuses | 1 (`monitoring.summary_counts`, at `app/services/monitoring.py:476`) | `grep -n "def summary_counts" app/services/monitoring.py` |
| Its existing callers | 3 files | `grep -rln "summary_counts(" app \| wc -l` |
| The responses read it sits beside | 1 (`serialize_responses`, `app/services/extracts/responses_extract.py:247`) | `grep -n "def serialize_responses" app/services/extracts/responses_extract.py` |
| Routes in `_handoffs.py` today | 1 | `grep -n "@router" app/web/routes_operator/_handoffs.py \| wc -l` |
| Tests to extend | 26 + 7 | `grep -c "^def test_" tests/integration/test_handoffs.py utilityapps/tests/test_interop_poc.py` |

## PR ladder

1. **Scaffold.** The Utilities page gains a **Sent to Review Robin** card: the transfers this browser created (code, when), each with inert **Refresh status** and **Fetch results** buttons, and placeholder panes showing the fields each will fill. Not touched: RRW.
2. **Status route.** `handoffs.status(...)`, the route, `not_linked` / `not_authorized` / `transfer_incomplete`, and tests: every count against a seeded session, the link check, the permission check, and that a read changes nothing. Not touched: the page.
3. **Results route.** `handoffs.results(...)`, the route, the audit event in `EVENT_SCHEMAS`, and tests: submitted-only, drafts excluded, completion states, group-scoped exclusion, digest stable across two reads of unchanged data, and the keys.
4. **Wire the page.** The card refreshes status, fetches and shows results, downloads CSV, and handles *unavailable*. This is the last build rung: `diff-reviewer` reads the cumulative diff from rung 1's base.
5. **Close.** Specs, `spec-writer` and the archive.

## Definition of done

- On `/utilities/interop-poc/`, a session created there shows its live status on **Refresh status**. After a reviewer submits in Review Robin, **Fetch results** shows that reviewer's answers keyed by application ID. Verified on localhost by the author, and on production after an import.
- `tests/integration/test_handoffs.py` covers both routes, their link and permission refusals, submitted-only results and the audit event. `utilityapps/tests/test_interop_poc.py` covers the card.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Rich-text and multi-choice values** in a results row: the stored value as is, or a display form? Decided at rung 3 from what the response types store; recorded in Judgment calls.

## Out of scope

- **Push and notifications**, and any background sync (Decision).
- **Draft answers, group-scoped results and corrections or withdrawals** beyond full-snapshot replacement: D2 and D7, for ApplyDesk's segment.
- **The ApplyDesk importer and its storage** of results and links.
- **Instruments sent from the sender** (author, 2026-11-11): the sender tags its rosters, and operators adjust instruments in Review Robin.

## Doc impact

- `spec/handoffs.md` — the two read routes, the status and results projections, `not_linked`, and the export audit event.
- `spec/permissions.md` — the two routes in the per-route matrix.
- `spec/architecture.md` — `session.handoff_results_exported` with the `counts` envelope's events.
- `utilityapps/spec/utilities.md` — the *Sent to Review Robin* card.
- `guide/interoperability.md` — what the reverse flow settled (D2 and D4 for the proof of concept), in §4.
- `guide/todo_master.md` — the queue entry, deleted at close.
