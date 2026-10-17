# Findings — bug sweep (2026-10-16)

**Found by:** six bug-hunting reads run beside
`guide/codebase_assessment_16oct.md` · **Read at:** `3d8adb38` (#3081) ·
**Open:** 21 of 46 rows (refreshed 2026-10-17: R2, L1, O1, S1, S2, E1, E2, R3,
R4, S3, S5, S6, S7, O4, O6, S8, S9, S10, P4, E4, E3, E5, P1, P3 and P5 done).

Unlike the corpus sweeps, this one read the code for defects rather than the
specs for drift. Each read took one area, wrote scratch tests against the
in-memory SQLite suite, and reported only what a test reproduced or a reading
of the code made certain. **Nothing in `app/` was edited.** The scratch tests
were not committed; a fix PR writes its own test. A row is struck when it is
done, with the PR that did it, or marked declined with the reason.

**Ids** carry the area of the read: **R** responses and participant data ·
**L** lifecycle and scheduling · **O** operator pages, extracts and email ·
**S** Setup, imports and instruments · **P** permissions and identity ·
**E** the assignment engine. A finding two reads made is listed once, under
the first. **Severity** is the reader's, adjusted where two reads disagreed.
**Decides:** *code* means the code is wrong against a spec that is right;
*author* means a choice between fixing the code and changing the contract;
*spec* means the spec is wrong. Line numbers are at `3d8adb38`.

## 1. High

- **R1** — **A Save after Submit changes a submitted answer and keeps its
  `submitted_at`**, so the edited value is released as submitted with no
  resubmit (`app/services/responses/_core.py:313`). `spec/reviewer-surface.md`
  "Persistence semantics" says Save never touches `submitted_at`, and the code
  does as it says; but a *new* answer saved after Submit flips the pill back
  to in progress, so the two paths disagree. *Reproduced.* Author: clear the
  stamp on a changed row, or say an edit after Submit is treated as submitted.
- ~~**R2**~~ — **Done in #3097**: every download builds its header with `app/web/downloads.py`'s `content_disposition` — an ASCII `filename` plus `filename*=UTF-8''` when the name needs it — and a unit test refuses a raw one (`tests/unit/test_downloads.py`, `tests/integration/test_download_filenames.py`). **A session code outside Latin-1 makes every CSV download answer
  500**, because the filename goes into `Content-Disposition` raw
  (`app/services/extracts/__init__.py:40` and 19 other sites); a `"` in the
  code corrupts the header too. The extract's audit event is committed before
  the failure. *Reproduced* (also found by the O read). Code: one helper with
  an ASCII fallback plus `filename*=UTF-8''`.
- ~~**L1**~~ — **Done in #3093**: phase 1 runs the details card's offset rules, the lead-time floor waived (`session_offset_errors`), and an out-of-range duration is a parse error rather than an `OverflowError`. **A Settings CSV import stores reminder and invite offsets
  unvalidated**, and an out-of-range one makes Session Home answer 500 on every
  load and holds a scheduled activation forever (`OverflowError`)
  (`app/services/session_config_io/_apply_session.py:75-85`, raised from
  `_duration.py:51` via `_workflow_card.py:506`). *Reproduced.* Code: run the
  same checks as `/config` in phase 1.
- ~~**O1**~~ — **Done in #3095**: Select all ticks only the rows shown and the header reads them alone; a row the filter hides is unticked (`tests/browser/test_lobby_select_all_filter.py`). **The lobby's and Archive's Select all tick rows the filter has
  hidden**, so bulk Delete, Purge, Unarchive and tag edits act on sessions the
  operator cannot see, and hidden rows stay ticked
  (`app/web/templates/operator/sessions_list.html:388-392,794`,
  `sessions_archived.html:203-206`). `spec/ui_elements.md` §10's funnel says
  Select all covers the visible rows; Assignments already does it.
  *Reproduced* in Chromium. Code.
- ~~**S1**~~ — **Done in #3096**: a Save that adds, removes, reorders or changes a response field un-validates the session and writes `instrument.response_fields_saved`; an identical re-save, a seeded instrument's included, does neither (`tests/integration/test_band2_save_invalidates.py`). **The instrument card's Save can change or delete response fields
  without un-validating the session or writing an audit row**
  (`app/services/instruments/_band2.py:110-353`; the no-op check at `:331`
  returns early, the sync at `:289` writes). An empty field list is accepted,
  so a validated session then fails Activate. `spec/instruments.md:1654` and
  `spec/lifecycle.md` §2.3 require both. *Reproduced.* Code.
- ~~**S2**~~ — **Done in #3085** (phase 1 refuses a `rules_json` the engine rejects and a `band2_state` that is not an object). **A Settings CSV import stores `rules_json` and `band2_state`
  without checking their shape** (`_apply_rule_set.py:52` runs only
  `json.loads`; `_apply_instrument.py:270`), and `/instruments`, `/assignments`
  and `/validate` then answer 500 until a Band 1 re-save replaces it.
  `spec/csv_contracts.md:469` puts shape checks in phase 1. *Reproduced* by
  two reads. Code: `TypeAdapter(Rule)` per entry, raising `_ParseError`.
- ~~**E1**~~ — **Done in #3085** by refusing the rule on Save. Ruled 2026-10-16: Link 2 takes reviewer and pair-context operands, as the card offers, and the specs say so. While the field is a pair-context tag the card's script hides the pair-context operands. The rendered list stays complete, because narrowing it would drop a stored `reviewee.tagN IS THE SAME AS pair_context.tagM` on the next Save. *Superseded the same day by #3086 (stage 1 of `guide/archive/assignment_rule_clarify.md`): the card offers no pair-context tag, the script is gone, and the Save refusal stays for stored rules. Item 2 of that plan (#3088–#3091) brought relationship tags back with Save choosing each one's field by Link and operator, so the card cannot build a same-side rule; the refusal stays for stored and forged ones.* **The Band 1 card offers a rule the engine rejects.** With a
  pair-context tag as Link 2's field, the operand list still offers
  pair-context tags (`instruments_index.html:718-719`);
  `set_band1_assignment_rules` stores the rule unvalidated
  (`_band1.py:92`, `:174`), and `/assignments` and `/validate` answer 500 while
  Prepare fails (`app/schemas/rules.py:183`). `spec/assignments.md:174-179`
  says the operand is a reviewer-side namespace. *Reproduced.* Code: validate
  on save, filter the operand list.
- ~~**E2**~~ — **Done in #3098**: a regroup clears every group that gains a member, and a group that only shrinks or splits keeps its answer (author's rulings 2026-10-17: the group is the subject; #3099 and the shrink-keeps PR extended it everywhere; `spec/assignments.md`; `tests/integration/test_regroup_clears_changed_groups.py`). **Changing an instrument's group boundary or unit of review leaves
  one group holding different answers** (`_instrument_crud.py:990`
  `set_group_boundary`, `:1069` `set_unit_of_review`): both rewrite
  `group_kind` but never reconcile the copies, and the next Save overwrites one
  member's answer with another's. Reachable in draft after a revert with
  responses saved. `spec/assignments.md:603` lists the moves that give up a
  copy and omits this one. *Reproduced.* Code, then spec.

## 2. Medium

- ~~**R3**~~ — **Done in #3106**: a numeric answer must be a plain ASCII number (`DECIMAL_PATTERN`) a float can hold, so `nan`, `inf`, `1e400`, an Integer past 4300 digits and a value whose step offset overflows are refused, and the extracts count an already-stored non-finite value as other (`canonical_number`; `tests/integration/test_bad_input_refused.py`). `nan`, `inf` and very large numbers: a stepped field answers 500 on
  Save; `NaN` passes min/max and then breaks the extracts' `_format_number`
  (`_core.py:125-138`, `entity_metadata_extract.py:313`,
  `data_shape_extract.py:141`). *Reproduced.* Code.
- ~~**R4**~~ — **Done in #3106**: a valid number is stored canonical from its typed digits (`04` → `4`, `+2.50` → `2.5`, `1e23` exact), the data-shape step columns are labelled by the same formatter (`text.decimal_text`), and `0_5` or full-width digits are refused (`canonical_number`; `tests/integration/test_bad_input_refused.py`). Non-canonical numbers (`04`, `2.0`, `+4`, `0_5`, full-width digits)
  are stored raw; data-shape step columns miss them and branching reads `0_5`
  as unanswered, deleting branch answers. *Reproduced.* Code: canonicalize
  with `DECIMAL_PATTERN`.
- **R5** — The reviewer `summary.csv` group name lists members the reviewer is
  not assigned, excluded ones included (`responses_extract.py:150-170`).
  *Reproduced.* Code.
- **R6** — `Response.saved_at` never updates and `version` never increments
  (`app/db/models/response.py:32-36`). *Reproduced.* Author: maintain them or
  retire them.
- **L2** — Far-future dates and durations answer 500 (`OverflowError`) on
  Create, `/config`, the lobby edit, activation and release; a stored year-9999
  deadline breaks the lobby for an owner east of UTC
  (`date_formatting.py:153`). *Reproduced.* Code.
- **L3** — Reviewer Save, Submit, Clear and Recall are not decided under the
  session lock, so a write can land after Close or Revert on Postgres
  (`_surface/_context.py:126-158`). `spec/lifecycle.md` §8.3. *Code reading;*
  the race needs Postgres. Code.
- **L4** — Scheduled events fire only from Session Home
  (`_session_home.py:124`); `spec/lifecycle.md` §8.3 says the Operations pages
  and the lobby too. `guide/post_azure_todo_checklist.md` item 7 tracks the
  scheduler. Author: say so in the spec, or add the callers.
- **O2** — After Regenerate all, the Invitations table and counters still say
  "sent" while the rows are pending (`_invitations.py:113-124`;
  `spec/operations_pages.md` "Invitation card"). *Reproduced.* Code.
- ~~**S3**~~ — **Done in #3107**: phase 1 holds each `field_key` to the card's `_validate_field_key` and refuses a bad one as a row error (`spec/csv_contracts.md` §3.3; `tests/unit/test_settings_import_bug_sweep.py`). **The Settings import accepts any `field_key`; one containing `]` can
  never be answered, so a required field blocks Submit**
  (`_apply_instrument.py:116`). *Reproduced.* Code: `_validate_field_key`.
- **S4** — A Settings file with no instrument rows deletes every instrument
  (`_apply.py:181`), and a direct Prepare POST then creates a Default
  instrument whose Band 1 links are Not set. *Reproduced.* Author: refuse the
  file, or keep instruments it doesn't name.
- ~~**S5**~~ — **Done in #3107**: a second instrument naming a rule set gets its own copy, named as Band 1 names one (`spec/instruments.md`, `Delete` semantics; `tests/unit/test_settings_import_bug_sweep.py`). **The import can pin several instruments to one rule set**
  (`_apply_instrument.py:398`), so a Band 1 edit on one changes the others;
  `spec/instruments.md:1585`. *Reproduced.* Code.
- ~~**S6**~~ — **Done in #3107**: the import leaves either toggle on while its roster has rows, as `sessions.update_session` does (`spec/participant_model.md` §2; `tests/unit/test_settings_import_bug_sweep.py`). **The import turns Relationships and Observers off while they hold
  rows** (`_apply_session.py:64`), against the lock-on-data rule in
  `spec/participant_model.md:46`. *Reproduced.* Code.
- ~~**S7**~~ — **Done in #3107**: `decode_csv` refuses a roster file holding a NUL, and `split_rows` refuses a Settings row holding one, so the Setup pages and Quick Setup report it; Rehydrate, gated off and incomplete (`spec/rehydrate.md`), is not covered and needs this check before it ships (`tests/unit/test_roster_csv_bug_sweep.py`, `tests/unit/test_settings_import_bug_sweep.py`). **A NUL byte in a roster or Settings CSV is accepted**
  (`csv_imports.py:90`); Postgres refuses it with a 500. *Reproduced* to the
  driver; not run against a live Postgres. Code.
- ~~**P1**~~ — **Done in (this PR)**: Demote, single-row and in a batch, takes Revoke's `still_owner` when the target has no Operator flag, after locking the row as Revoke does (`spec/permissions.md` §4.1; `tests/integration/test_sys_admin_users.py::test_demote_refuses_an_owner_left_with_no_operator_flag`). Demoting a sys-admin who is a session's only owner orphans it: the
  owner is bounced by `require_operator`, and Revoke, Delete and Remove all
  refuse (`app/services/users.py:283`, `:305`, batch at `:598`).
  `spec/permissions.md` §4.2 holds owners to be operators; `revoke` guards
  this, `demote` doesn't. *Reproduced.* Code.
- **P2** — A sys-admin who doesn't own a session can POST `/clone` with
  `mode=all` and read the full roster through the copy, while the roster page
  itself answers 403; no event lands on the source
  (`routes_operator/_lobby.py:343-372`, `session_clone.py:396-404`).
  `spec/permissions.md` §3 lists clone as a deliberate relaxation.
  *Reproduced.* Author: gate it on ownership, or at least audit the source.
- ~~**E3**~~ — **Done in (this PR)**: Prepare gives a kept self-review row with both sides active its instrument's toggle state (the value most such rows hold), so a toggled-off instrument stays off and a reactivated reviewer's row rejoins the rest (`spec/assignments.md`; `tests/unit/test_replace_assignments_self_reviews_active.py::test_a_kept_self_review_row_keeps_its_toggled_include`). The next Prepare turns a per-instrument self-review "off" back on:
  `replace_assignments` resets `include` on kept self-review rows
  (`_generate.py:582-586`), and any roster edit sends the session back
  through Prepare. `spec/assignments.md:406`, `:443`. *Reproduced.* Code.

## 3. Low

- **R7** — The surface's status pill and the dashboard disagree on
  all-optional blank rows and on a new answer after Submit
  (`_surface/_status.py:59`). Code.
- **R8** — *(First half done in #3106: a form key with an id past 18 digits is ignored.)* A 20-digit assignment id answers 500 (`_core.py:57`); and, by
  reading, the observer CSV's self-review rows expose the reviewer through the
  reviewee columns. Code.
- **L5** — Archiving a `ready` session leaves every instrument's
  `accepting_responses` set, and unarchive carries it into `draft`
  (`_workflow.py:622`). That is harmless for writes, which
  `session_accepts_responses` gates on `ready`. But `spec/lifecycle.md`
  says the flag is cleared at every exit from `ready`, and archive is an
  exit it doesn't list. (The missing `can_archive` gate is not a finding:
  `spec/lifecycle.md:47` has `/workflow/archive` accept any non-archived
  state. Codex on #3084.) Author: clear the flag on archive, or say it is
  moot outside `ready`.
- **L6** — Close early, then Release, then Revert: every Session Home Save is
  refused by the ordering check on boxes nobody edited
  (`_session_home.py:483`). *Reproduced.* Code.
- **L7** — Purge rosters leaves Observers, which are personal data
  (`session_purge.py:96-170`). *Reproduced* by two reads. Code.
- **L8** — A timezone change moves stored instants, and the spec contradicts
  itself (`spec/settings_inventory.md:109` against
  `spec/session_home.md:368`); Create's preview re-renders only `#deadline`.
  Author.
- **O3** — The audit log's date filter answers 500 at calendar edges, in the
  viewer and the CSV (`app/services/audit.py:983`, `:990`). Code.
- ~~**O4**~~ — **Done in #3106**: the port must be 1 to 65535 (`tests/integration/test_bad_input_refused.py`). The SMTP port is unchecked: a 500 or a negative value stored
  (`_settings.py:103`). Code.
- **O5** — The audit-log CSV's recorded row count is off by one, and the
  comment says otherwise (`_extracts.py:796-800`). Code.
- ~~**O6**~~ — **Done in #3106**: an app-wide dependency answers 404 for an id path or query parameter past a 64-bit column, the answer Postgres gives (`app/web/oversized_ids.py`; `tests/integration/test_bad_input_refused.py`). Oversized integer ids in paths and queries answer 500 on SQLite;
  Postgres compares them. Code.
- **O7** — Error text taken from the URL is shown on trusted chrome:
  `super_error`, `quick_setup_detail`, `owners_error`, `rf_save_error`,
  `sort_save_error` (`next_action_card.html:443`,
  `instruments_index.html:135`, `:158`). Escaped, so not XSS, but a link can
  put any sentence on the page; `spec/permissions.md` §4.1 rules that out for
  Accounts. *Reproduced* (also found by the P read). Code: codes, not text.
- **O8** — The SMTP Save always records "password changed", because the
  encrypted value differs every time (`operator_settings.py:154-157`). Code.
- **O9** — `instruments_index.html:1433` puts `| tojson` inside a quoted
  attribute, breaking it (benign today). Code.
- **O10** — *Latent, no caller yet:* `email_send.py` builds the From display
  name without `formataddr` and doesn't refuse CR/LF in subject, cc or bcc.
  Fix before segment 14B sends mail.
- ~~**S8**~~ — **Done in #3107**: `field_labels.upsert` returns early on an unchanged label, with no event and no invalidation (`tests/integration/test_field_labels_resolver.py`). **Saving unchanged friendly labels un-validates the session and
  writes a same-to-same event** (`field_labels.py:267`). Code.
- ~~**S9**~~ — **Done in #3107**: `_read_dict_rows` refuses a file whose header names one column twice as a blocking issue (`spec/csv_contracts.md` §1a; `tests/unit/test_roster_csv_bug_sweep.py`). **A header mapped twice (`ReviewerTag1` and `ReviewerTag1.Tutor`)
  silently drops one column** (`field_label_csv.py:89`, `csv_imports.py:183`).
  Code.
- ~~**S10**~~ — **Done in #3107**: `observers.imported` and `observers.deleted_all` omit `cascaded_assignments`, as they omit `cascaded_relationships` (`spec/architecture.md`; `tests/integration/test_relationship_cascade_accounting.py`). **Observer audit events report `cascaded_assignments` that were never
  deleted** (`csv_imports.py:1380`, `:1566`). Code.
- ~~**P3**~~ — **Done in (this PR)**: `get_or_create_user` stores the claim stripped, as `find_user` compares it (`docs/security_posture.md` §5.5a; `tests/integration/test_operator_allowlist_gate.py::test_get_or_create_user_stores_a_padded_claim_trimmed`). An email claim with surrounding spaces works once, then answers 500
  on every request: `deps.py:179` stores it untrimmed and `find_user` (`:131`)
  compares trimmed. `docs/security_posture.md` §5.5a. Code.
- ~~**P4**~~ — **Done in #3106**: ids typed as text go through `app.services.text.parse_id`, ASCII digits only (`tests/integration/test_bad_input_refused.py`). Unicode digits such as `²` pass `isdigit()` and fail `int()`: 500
  (`_setup_observers.py:722`, `_band2.py:213`, `:396`);
  `app/web/return_to.py` already documents the trap. Code.
- ~~**P5**~~ — **Done in (this PR)**: `_claim` walks the types in the order given, then the token's claims (`tests/test_identity.py::test_rich_claims_follow_the_stated_priority_not_token_order`). `app/auth/identity.py` `_claim` returns the first claim in token
  order, not the stated priority, so `preferred_username` can win over
  `emailaddress` (`:45-56`, `:76-81`). Fails closed. Code.
- ~~**E4**~~ — **Done in #3086**: a rule or boundary stored with a tag the card no longer offers keeps its option (`data-new-model-stored-only`), so a Save keeps it, and `+` adds a cell without it (`spec/instruments.md`, Band 1; `tests/integration/test_band1_filled_empty.py`). **A Band 1 rule on a tag column now empty has no `<option>`, so the
  card's next Save silently rewrites the rule to the first field
  (`instruments_index.html:647-650`); Link 3's boundary boxes look the same
  and would trigger E2. Template shape *reproduced*; what the browser posts
  needs the author's check. Code.
- ~~**E5**~~ — **Done in (this PR)**: the name and handle predicates use `icontains(..., autoescape=True)` (`tests/integration/test_assignments_search_tags.py`, two cases added to the conformance table). `_` and `%` act as wildcards in the Assignments search
  (`app/services/assignments/_coverage.py:208`, `:249`), which the Python
  matcher it must mirror doesn't do. Code: `contains(..., autoescape=True)`.

## 4. What came up clean

Each read also reported what it tried and found sound: an XSS crawl of 18
operator pages; all 192 routes walked for their gates; 36 child-id routes sent
another session's ids (every one 404); body-borne ids scoped; reviewer Save
fuzzed with foreign ids and keys; participant gates and invite tokens;
`return_to`; a 600-seed property test of self-review classification, the
reconcile cache and group copies on tag and relationship moves; roster and
Settings round-trips byte-identical; Quick Setup all-or-nothing;
`EVENT_SCHEMAS` covering every emitter (155). Postgres-only behavior was not
exercised.
