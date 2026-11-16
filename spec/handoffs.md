# Handoffs from another Cordware application

**Status:** shipped in segment 23A (`guide/archive/segment_23A_interop_poc.md`),
as the interoperability proof of concept; the reads back to the sender
(§10) in segment 23B (`guide/archive/segment_23B_interop_return.md`). The design it tries out is
`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
("the interop spec"); this file is the contract Review Robin actually
offers. The only sender today is Utilities' *Interop proof of concept*
(`utilityapps/spec/utilities.md`), which is also the example a real
sender starts from (`docs/interoperability_example.md`); a change to
this contract updates it in the same change. Apply Desk's segment
settles the final paths when it builds the real sender.

## 1. The flow

One click in the sending application, all in the operator's browser and
on one origin (interop spec §7.1); no server-to-server call and no
cross-app credential:

1. The sender opens a new tab **during the click** (so pop-up blockers
   allow it) on `GET /operator/handoffs/new`, a holding page.
2. It posts a **bundle** of roster CSVs, and optionally a Settings CSV, to `POST /operator/handoffs/sessions`.
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
| `POST /operator/handoffs/{transfer_id}/update` | the package gate `require_operator` | The re-send to the draft that transfer created (§6a, segment 23F). JSON, `no-store`, the §3 request checks. |

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
| `files` | CSV text by kind: `reviewers` and `reviewees` required; `relationships`, `observers` and `settings` optional. Any other kind is refused, the key named ASCII-escaped. `settings` is a Settings CSV (`spec/csv_contracts.md` §3.3), so a sender sets up the draft's instruments too |

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
  session's directory (`spec/quick_setup_card_spec.md`). **A settings
  file** goes through it too, after the rosters (`SLOT_ORDER`), with the
  Settings import's own checks and two-phase apply. Its `session.name`
  and `session.code` rows are fill-blanks (`spec/csv_contracts.md` §3.3)
  and the suggestion has set both, so the file cannot rename the draft;
  symmetric review stays off, the rosters being present. A refused
  settings file is `422 invalid_setup` with `slot` `settings`, as a
  refused roster is, and the draft goes with it.
- **What a settings file may set** is what the Settings import sets on
  a new session (`spec/csv_contracts.md` §3.3): instruments, rule sets,
  data shapes and session tags, the email templates (their CC and BCC
  included), and the session's other settings, among them its
  description, deadline, help contact, timezone and schedule. A schedule
  it carries counts as the operator's own: a `scheduled_activate_at`
  activates the draft once it is prepared, and on a native session a
  `responses_release_at` releases on its date. Never the draft's name and code (fill-blanks,
  set by the suggestion), its owner, or its state (`session.status` is
  ignored on import). **Symmetric review** turns on only while both
  rosters are empty, which a handoff never has, so a file asking for it
  is refused before anything is made: `422 invalid_setup`, `slot`
  `settings`, `reason` `symmetric_review`. The sender is the operator's
  own browser (one operator in both apps, `guide/interoperability.md`),
  so these are the operator's settings; a sender sends only what its
  session needs.
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
- **The link** (segment 23E, `guide/archive/segment_23E_linked_sessions.md`): a
  `source_app` with a profile in `app/services/linked_apps.py`
  (`applydesk`; `utilities`, the proof of concept) sets the draft's
  `linked_app` with its transfer record; any other links nothing. Session
  Home shows the link, and **Unlink** clears it (`session.unlinked`).
  A linked draft starts with the Relationships tab on
  (`relationships_enabled`, segment 23F): its application sends the pairs.
  A profile is a set of named locks (`linked_apps.Lock`) and the settings
  fields it owns (segment 23F rung 2a): Apply Desk takes every lock;
  Utilities keeps Review Robin's email on. Profiles are code, never data
  a bundle can set.
  The mark is set before the files apply, so the profile holds for them:
  an `observers` file is refused before the draft is made, after the
  replay lookup so a transfer completed before the link still answers
  `already_created` (`422 invalid_setup`, `slot` `observers`, `reason`
  `observers_off`), and a settings file naming a
  release date or turning observers on is refused as the Settings import
  refuses it (`spec/csv_contracts.md` §3.3). On a linked session the
  release window never opens, observers stay off, and the visibility
  card's after-the-window cells name the application
  (`spec/visibility_policy.md` §3.4).
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

## 6a. The re-send — a linked, unopened draft kept current

Segment 23F (`guide/segment_23F_linked_drafts.md`): while a linked
session is unopened, its rosters are the linked application's, which
re-sends them rather than Review Robin editing them (Apply Desk's ruling
24).

- **Naming the draft:** the path's `transfer_id` is the transfer that
  created it, as §10's reads name theirs; a sender never names a free
  session reference (interop spec §6.6). The body is §4's envelope with
  its own new `transfer_id`, `operation` `reviewrobin.update_draft_session`
  and no `session_suggestion`.
- **Files:** `reviewers` and `reviewees` required, `relationships`
  optional. The rosters are the application's whole picture: they replace
  the draft's, and the replace's own cascade drops the pairs, so an absent
  Relationships file leaves none. An `observers` file is refused as at the
  create (§5).
- **A settings file** is optional and carries only the session fields its
  application's profile owns (`LinkedProfile.owned_settings`): the name,
  code, description, timezone, help contact, Start, End, Relationships
  switch, and the session tags (`session_tags[N].tag`). Any other row is
  `422 invalid_setup`, `slot` `settings`, `reason` `not_owned`, naming the
  fields; instrument rows are not taken yet. A row of fewer than three
  cells is refused, as the Settings import refuses it. The rows are
  checked as the import's row checks check them, plus the schedule's order on the values
  the session will hold, a timezone the app knows and a name and code
  New session would accept (`422 invalid_setup`, `slot` `settings`); a
  code another session holds is `409 session_code_conflict`. They are
  written directly (`app/services/linked_settings.py`) through the
  services that own each field, audited as an operator's edit, in the
  save's unit with the rosters; name and code are written, not filled
  only when blank. Nothing else of the draft moves: no instrument is
  rebuilt. A field the file leaves out keeps the draft's value; tag rows,
  when present, replace the session's tags.
- **All or nothing**, through the create's pipeline
  (`_run_quick_setup_contents`, replacing); a refused file leaves the draft
  as it was (`422 invalid_setup` with `slot`), and a validated draft
  returns to draft as any roster replace makes it.
- **Refused:** a creating transfer unknown or incomplete, or whose session
  is not linked to this `source_app` (unlinked included), is
  `404 not_linked`; one the operator may not operate, `403`; a session
  activated or later, `409 session_opened` (a session reverted to draft is
  unopened again); one holding responses, `409 session_has_responses`.
- **Under the save's lock** the re-send is checked again: its transfer
  not yet applied (an overlapping retry answers `200 already_updated` and
  saves nothing, so it cannot overwrite a newer re-send), and the draft
  still linked, unopened and without responses, so an Unlink or an
  activation since the first check refuses it rather than being
  overwritten.
- **Replay:** `session.handoff_updated` records the re-send's
  `transfer_id`, in the same commit as its rosters, so no re-send applies
  without the record a retry reads. A repeat answers `200 already_updated`
  and applies nothing; another operator's is `409 duplicate_conflict`,
  and one the operator may no longer operate, checked now, `403`.
- **Receipt:** `200 {status: "updated", session_ref, session_code, session_home_url}`.

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
| `session.handoff_updated` | `counts(reviewers, reviewees)`, `context` `{transfer_id, source_app}` | once a re-send's rosters have saved (§6a) |
| `session.handoff_results_exported` | `counts(rows)`, `context` `{transfer_id, file, etag}` | a `results.csv` or `completion.csv` fetched (§10); a `304` writes nothing |

All four are registered in `EVENT_SCHEMAS`. The draft's own
`session.created`, the roster saves' events and a settings file's
`session.settings_imported` are written as for New session. A status read writes nothing: reads never audit.

## 9. Tests

`tests/integration/test_handoffs.py` (the routes),
`tests/integration/test_handoff_update.py` (the re-send), and
`utilityapps/tests/test_interop_poc.py` (the sender's page and bundle).

## 10. Reading back: status and results

The reverse flow: the sender pulls, on its operator's view,
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

**Status** (`status_schema_version` 3): Review Robin's own
readings of the session, each from the function its pages read, so a
number the sender sees is the one Review Robin shows. It is assembled by
a view adapter (`app/web/views/_handoffs.py`). Identity: `session_ref`, `linked_app` (segment 23E: the application the session is linked to, or null),
`session_code`, `name`, the lifecycle `state` (the enum) and `state_label`
(as Review Robin shows it), `session_home_url` and `as_of`. Then:

- `status_row`: the row every session page shows (`session_status_pills`).
  It carries `reviewers`, `reviewees`, `relationships`, `observers`,
  `assignments`, `instruments` and of those `instruments_set_up`
  (`instruments.is_configured`: a visible response field and all three
  assignment-rule links set), `invitations` (`not_created`, `not_sent`,
  `partial_sent`, `all_sent`), `responses_drafts` and
  `responses_submitted`.
- `schedule`: `display_timezone`, `scheduled_activate_at`,
  `activated_at`, `deadline`, `responses_release_at` and
  `responses_release_until`, as stored (ISO 8601, or null).
- `workflow`: the Workflow card's reading.
  - `setup_complete`, and its `checklist` of `reviewers`, `reviewees` and
    `instruments_set_up`. The card checks setup only in draft, so past
    draft `setup_complete` is true whatever the checklist reads. An
    incomplete setup offers no **Prepare**; Validate also raises
    `instruments.band1_not_set` (error) for an instrument with an
    assignment-rule link not set.
  - `actions`: the card's buttons showing now, enabled or not (with
    bulk email off, the send buttons show disabled), in order (`revert`,
    `prepare`, `send_invites`, `activate`, `send_reminders`, `close`,
    `release_responses`, `stop_release`, `archive`).
  - `invitations_generated`, `invitations_sent`, and `due`: the card's due
    prompts.
- `validation`: the Validate page's rules as they read now
  (`validate_session_setup`, read only, nothing stamped): the counts of
  `errors`, `warnings` and `info`, and `issues`, each with its `rule` key, `severity`,
  `message` and fix `page`.
- `instruments`: one entry per instrument, by `seq`: `name`,
  `short_label`, `set_up`, `scope` (`per_reviewee` or `group`), and
  included `assignments`.
- `progress`: Monitoring's summary.
  - `assignments`: the included assignments of active reviewers, and of
    those `assignments_completed`. "Completed" is Review Robin's own
    *complete*: every required field answered, saved or submitted (the
    reviewer-side rollup).
  - `reviewers_assigned`, and of those `reviewers_invited`,
    `reviewers_opened`, `reviewers_submitted` and `reviewers_incomplete`.
  - Always reported, never withheld. While any instrument is not set up
    (or there is none), `provisional` is true with `provisional_reason`
    `instruments_not_set_up`: an instrument lacks a visible response
    field or an assignment-rule link, so the assignments may not be the
    review's yet: an instrument not set up generates none. It covers the
    whole block, not only that instrument's share.
- `reviewers` and `reviewees`: Monitoring's two tables, listing only who
  has assignments (and, for reviewers, only the active).
  - A reviewer row: `email`, `name`, `state`, `assignments`,
    `completed`, `missing_required`, `invitation` and
    `last_reminder_at`.
  - A reviewee row: `key` (the application ID), `name`, `state`,
    `reviewers`, `completed` and `last_response_at`.
  - Both carry participants' details, as the Monitoring page does, to
    someone who may see that page.

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
