# Handoffs from another Cordware application

**Status:** shipped in segment 23A (`guide/archive/segment_23A_interop_poc.md`),
as the interoperability proof of concept; the reads back to the sender
(§10) in segment 23B (`guide/archive/segment_23B_interop_return.md`). The design it tries out is
`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
("the interop spec"); this file is the contract Review Robin actually
offers. The only sender today is Utilities' *Interop proof of concept*
(`utilityapps/spec/utilities.md`). ApplyDesk's segment settles the final
paths when it builds the real sender.

## 1. The flow

One click in the sending application, all in the operator's browser and
on one origin (interop spec §7.1); no server-to-server call and no
cross-app credential:

1. The sender opens a new tab **during the click** (so pop-up blockers
   allow it) on `GET /operator/handoffs/new`, a holding page.
2. It posts a **bundle** of roster CSVs to `POST /operator/handoffs/sessions`.
3. Review Robin creates a **draft** session from it, all or nothing, and
   answers with a receipt carrying the session's Session Home URL.
4. The sender moves the tab there. If the tab was blocked, it shows the
   URL as a link.

The create prepares nothing, activates nothing, invites no one and sends
no mail (interop spec §3 invariant 4): the draft waits for its operator.

## 2. Routes

| Route | Gate | What it does |
|---|---|---|
| `GET /operator/handoffs/new` | the package gate `require_operator` | The holding page: says a draft is being set up and that nothing is sent, links the Sessions lobby, and offers nothing else to do. `no-store`. |
| `POST /operator/handoffs/sessions` | the package gate `require_operator` | The create (§3–§6). Every answer is JSON and `no-store`. |

A non-operator gets the package gate's usual `303` to `/me`, as does an
operator the owner-eligibility lock refuses (`OperatorAllowlistDenied`,
§5); a sender posting with `redirect: "manual"` reads either as
`not_authorized`. The
create route lives in `app/web/routes_operator/_quick_setup.py`, whose
pipeline it runs; its rules are `app/services/handoffs.py`.

## 3. Request checks

In this order, each refused before anything is read further:

| Check | Refusal |
|---|---|
| `Sec-Fetch-Site`, when sent, is `same-origin` (`none` and `same-site` are refused) | `403 not_authorized` |
| `Content-Type` is `application/json` — the cross-site guard, as the directory endpoints' (no `Origin` check: the gateway rewrites the host the app sees) | `415 invalid_package` |
| `Content-Length` is declared | `411 invalid_package` |
| The body is at most 1 MiB (`handoffs.MAX_BYTES`), declared and read | `413 invalid_package` |

## 4. The bundle

A JSON object:

| Key | Value |
|---|---|
| `protocol`, `protocol_version`, `operation` | `"cordware.csv-handoff"`, `1`, `"reviewrobin.create_draft_session"`; anything else is `422 unsupported_version` |
| `transfer_id` | a UUID, chosen by the sender per transfer |
| `source_app` | the sender's name, 1–64 characters |
| `session_suggestion` | `{name, code}`: the draft's name (1–255) and code (1–64), checked as New session checks them |
| `files` | CSV text by kind: `reviewers` and `reviewees` required, `relationships` and `observers` optional (rosters only, interop spec §13.1). `settings` or any other kind is refused, the key named ASCII-escaped |

Every text must be valid Unicode with no NUL character (Postgres text
refuses one). Any envelope fault is `422 invalid_package` with lines in
`details`. The CSVs themselves are Quick Setup's to check, with its own
parsers and caps (`spec/csv_contracts.md`); nothing parses them twice.

## 5. The create — all or nothing

- **Who owns it:** the signed-in operator, through the owner-eligibility
  lock (`session_owners.lock_owner_eligible`) and `sessions.create_session`,
  as New session does, without its scheduling fields.
- **Before anything is made**, in this order: a taken code is
  `409 session_code_conflict`; a name or code New session would refuse is
  `422 invalid_package`; an operator the owner-eligibility lock refuses
  gets the `303` of §2.
- **The rosters** go through Quick Setup's pipeline
  (`_run_quick_setup_contents`), every slot saved in one unit, with the
  session's directory (`spec/quick_setup_card_spec.md`).
- **Refused, the draft goes with it** (author, 2026-11-11): the route
  rolls back and deletes the session, its audit events included. A
  refused roster is `422 invalid_setup` with `slot`, `reason` and the
  importer's own `details`; a lapsed directory sign-in is
  `409 directory_sign_in`; a roster with no rows is `422 invalid_setup`
  with `reason` `empty_roster`. An unexpected error while the rosters save
  discards it too. A failure after the save, while recording completion,
  leaves the draft with its rosters, which a replay completes (§6).
  New session's own behavior is unchanged: it still keeps the draft when a
  file is refused.
- **Receipt:** `201` `{status: "created", session_ref, session_code, session_home_url}`.
  The URL is app-relative, emitted through `app/web/urls.py`.

## 6. Replay

A `transfer_id` already used is a replay. Two audit events record a
transfer, so the proof of concept needs no table:

- `session.handoff_created`, written with the draft before its rosters,
  in the same commit, so neither lands without the other
  (`sessions.create_session(commit=False)`);
- `session.handoff_completed`, written once the rosters have saved — the
  mark of a finished transfer, whatever the rosters hold later.

| Replay finds | Answer |
|---|---|
| another sender's transfer | `409 duplicate_conflict` |
| a session the sender may no longer operate (`permissions.user_can_view_session`, checked now, not at the first post) | `403 not_authorized` |
| a completed transfer | `200` receipt, `status: "already_created"` |
| no completion record, but both rosters saved (cut off between the save and the record) | the record is written; `200 already_created` |
| no completion record and no rosters, the draft under 5 minutes old (`handoffs.IN_PROGRESS`: the first try may still be checking the directory or saving) | `409 transfer_in_progress`; the sender keeps its transfer and tries again |
| no completion record and no rosters, the draft older (cut off before the save) | `409 transfer_incomplete` with the draft's `session_home_url`. **Nothing is deleted on a replay**: the draft stays for its operator, and the sender's next try is a new transfer |

Two concurrent first posts of one transfer can still make two sessions:
accepted for a proof of concept, whose sender disables its button.

## 7. Errors

Every refusal is `{"error": <code>}`, with `details` (lines for the sender
to show) and, where they apply, `slot`, `reason` and `session_home_url`.
The codes are the interop spec's vocabulary (§7.3) plus `directory_sign_in`,
`transfer_in_progress` and `transfer_incomplete`. A sender keeps its
`transfer_id` on a `5xx`, a network error, an answer it cannot read or
`transfer_in_progress`, so trying again finds a session already made;
after any other refusal it starts a new transfer.

## 8. Audit

| Event | Envelope | When |
|---|---|---|
| `session.handoff_created` | `counts(files=n)`, `context` `{transfer_id, source_app}` | with the draft, before its rosters |
| `session.handoff_completed` | `counts(reviewers, reviewees)`, same `context` | once the rosters have saved, or on the replay that finds them saved |
| `session.handoff_results_exported` | `counts(rows)`, `context` `{transfer_id, file, etag}` | a `results.csv` or `completion.csv` fetched (§10); a `304` writes nothing |

All three are registered in `EVENT_SCHEMAS`. The draft's own
`session.created` and the roster saves' events are written as for New
session. A status read writes nothing: reads never audit.

## 9. Tests

`tests/integration/test_handoffs.py` (the routes), and
`utilityapps/tests/test_interop_poc.py` (the sender's page and bundle).

## 10. Reading back: status and results

The reverse flow (segment 23B): the sender pulls, on its operator's view,
over the same transport (§1). Nothing is pushed: Review Robin calls no
other application.

| Route | Answers |
|---|---|
| `GET /operator/handoffs/{transfer_id}/status` | JSON: the live status |
| `GET /operator/handoffs/{transfer_id}/results.csv` | the submitted answers |
| `GET /operator/handoffs/{transfer_id}/completion.csv` | where each assignment stands |

**Link and permission.** Each route is keyed by the transfer, never a free
session reference, so a sender reads only what its own handoff made
(interop spec §6.6; `handoffs.linked`):

- an unknown transfer, or a malformed one, is `404 not_linked`;
- the caller must operate the session now
  (`permissions.user_can_view_session`), else `403 not_authorized`;
- a transfer that never completed (§6) is `409 transfer_incomplete`, with
  its draft's `session_home_url`.

Refusals are §7's JSON. Every answer is `no-store`, under the package gate.

**Status** (`status_schema_version` 1): `session_ref`, `session_code`,
`name`, the lifecycle `state` (the enum) and `state_label` (as Review
Robin shows it), `session_home_url` and `as_of`. Its counts name their
denominators; there is no single percentage (interop spec D4):

- `reviewers`, `reviewees`: the rosters; `instruments`, and of those
  `group_instruments`;
- `assignments`: the included assignments of active reviewers, and of
  those `assignments_completed`, Review Robin's own *complete*: every
  required field answered, saved or submitted (the reviewer-side rollup,
  `monitoring.per_reviewer_progress`);
- `reviewers_assigned`: active reviewers with assignments, and of those
  `reviewers_invited`, `reviewers_opened`, `reviewers_submitted`.

A read changes nothing: no lifecycle step runs, so it reports what the
clock has already done.

**The CSVs** (UTF-8, `text/csv`). Both take the assignments the status
counts, on per-reviewee instruments: group-scoped instruments are left
out, since a group's meaning for one application is undefined (interop
spec §6.5).

- `results.csv`: one row per **submitted** answer (saved drafts are left
  out), values as stored. Its columns borrow `responses.csv`'s names:
  `ReviewerEmail`, `RevieweeEmail` (the application ID), `InstrumentSeq`
  (`Instrument.session_seq`, stable where `responses.csv`'s
  `InstrumentName` is positional), `InstrumentLabel`, `FieldKey`,
  `FieldLabel`, `ResponseType`, `Value`, `SubmittedAt` (the session's
  zone). No preamble. An answer has no ID of its own (`Version` resets
  after a clear), so a fetch is a complete snapshot: a receiver reconciles
  on reviewer, application, instrument and field.
- `completion.csv`: one row per assignment, `ReviewerEmail`,
  `RevieweeEmail`, `InstrumentSeq`, `State`:
  - `submitted`: its answers are all submitted, or it has none and its
    reviewer has submitted (optional fields left blank leave no rows);
  - `in_progress`: it has answers, not all submitted (an edit after a
    submit clears that answer's stamp);
  - `not_started`: neither.

**Snapshot identity.** Each CSV carries an `ETag` (SHA-256 of its bytes)
and `X-Review-Robin-As-Of`. `If-None-Match` naming that tag (a list, a
weak `W/` tag, or `*`) answers `304`: the interop spec's *Already up to
date*. The download name is `<code>_results.csv` / `<code>_completion.csv`.
