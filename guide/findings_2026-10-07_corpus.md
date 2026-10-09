# Findings — corpus sweep (2026-10-07)

**Found by:** `guide/sweep_2026-10-07_corpus.md` · **Read at:** `ff7f4425`
(#2865) · **Open:** every row below that is not struck.

Every spec, `docs/` file and root document was read against the code it
describes, in nine verify-mode reads split by area. **Nothing in scope was
edited.** A sweeper may not re-align a spec to the code
(`rrw_sdd_in_practice.md` §4), so each divergence is listed here and the
fixes ship afterwards as ordinary PRs. A row is struck when it is done,
with the PR that did it, or marked declined with the reason.

**Ids** carry the area of the read that found them: **A** instruments and
the reviewer surface · **B** assignments, workflow, lifecycle, Validate ·
**C** Setup, Session Home and the lobby · **D** data in and out · **E** UI
and visual style · **F** architecture, roles and operations · **G** the
functional spec · **H** `docs/` · **I** root and process documents. They
restart at 1 in this file; an id from the 2026-10-05 register is written
"old A5". **Severity** is the reader's. **Decides:** *spec* means the spec
is wrong and an update in place fixes it; *code* means the code is wrong
against a spec that is right; *author* means it is a choice between fixing
the code and changing the contract; *trim* means history, provenance or a
tally to strip, keeping the reason it carried; *write* means a surface with
no adequate spec. In `docs/` and root rows, *doc* plays the part of *spec*.
Line numbers are at `ff7f4425`.

## 1. Code defects

Confirmed by reading the code; *reproduced* means a reader also ran it.

**High**

- ~~**H1**~~ — **Done in #2867** (ruled 2026-10-07: Remove refuses any user with history; Revoke takes access away). **Removing a user who created a session they no longer own
  deletes that session.** `users.remove_user` (`app/services/users.py`)
  refuses only while the target holds a `session_operators` row, then
  deletes the user; `User.review_sessions` carries `cascade="all,
  delete-orphan"`, so every session the user *created* goes with them —
  responses, rosters and all — even when another operator now owns it.
  The user's audit rows survive with `actor_user_id` nulled (the
  relationship sets it). `docs/backup_restore.md` and
  `docs/operations_runbook.md` present in-app removal as safe.
  *Reproduced* on SQLite with foreign keys on: Bob creates a session,
  Carol owns it, removing Bob deletes it. Found by Codex on #2866; the
  sweep's read had inferred an `IntegrityError` instead. Code, then doc.

**Medium**

- ~~**B4**~~ — **2026-10-07: the spec's "stays put", the fixer's choice with no ruling asked. Done in #2870** (an unedited Start, and the stored offsets on an unedited anchor, skip only the lead-time floor; every other check still runs). **A Details Save on a draft refuses a rename once the stored Start
  has passed.** `_session_home.py` `/config` re-validates the unedited
  scheduled Start through `parse_and_validate_scheduled_activate_at`
  (and the reminder offsets), so changing only the Name answers 422
  "Scheduled activation must be at least 1 hour(s) in the future".
  `spec/lifecycle.md` (aged values) says an aged value stays put; the lobby
  expander already exempts an unchanged End. *Reproduced.* Author: exempt
  an unchanged anchor, as the lobby does, or say the Details card refuses.
- ~~**A2**~~ — **Done in #2868.** **The first Save of any Instrument card with no sort writes a
  spurious event and can demote a validated session.**
  `_display_fields.py` `set_sort_display_fields` compares the stored value
  with the normalized one, and `NULL != []`, so an empty sort on a NULL
  column emits `instrument.sort_fields_updated` (`None → []`) and
  invalidates; the card's `/save` always calls it.
  `spec/sort_by_reviewee.md` says a no-op save emits nothing.
  *Reproduced.* Code.
- ~~**G3**~~ — **Done in #2869** (an event, as the spec reads: the per-row reminder writes `reminders.sent` with one entry; §2.12 now says the outbox row is the record of each email, matching §15). **The per-row Send reminder writes no audit event.**
  `_operations.py`'s per-row route reaches `invitations.send_reminder`,
  which queues the outbox row and stamps `last_reminder_at`; the bulk path
  emits `reminders.sent`, this one nothing. The functional spec says every
  mutating service writes an audit row and the audit records every send
  attempt. Author: an event, or a stated exception.

**Low**

- ~~**C4**~~ — **Done in #2896** (a 422, shared with the lobby). Over-long Name or Code on Session Home's Details Save, or on
  `POST /operator/sessions`, raises an unhandled `ValidationError` (500):
  `_session_home.py` and `_quick_setup.py` build `SessionCreate` outside a
  `try`, where the lobby catches it.
  `maxlength` hides it in a browser. *Reproduced.* Code.
- ~~**D4**~~ — **Done in #2896.** A whitespace-only email override cell in a Settings import is
  stored as an override (`_apply_email.py` tests `if value:`);
  `spec/email_template_editor.md` says whitespace resets. The editor then
  shows it overridden. *Reproduced.* Code.
- ~~**C5**~~ — **Done in #2909** (ruled 2026-10-09: the spec follows the code). The Quick Setup and Owners unlock cookies are cleared by every
  Session Home form response except the card's own: `main.py`'s
  `_UNLOCK_KEEP_COOKIE_RE` keeps them on Home, `/quick-setup` and
  `/owners` only, so a Details Save relocks the card.
  `spec/quick_setup_card_spec.md` says the unlock survives Session Home
  submissions. Author, then write.
- ~~**B7**~~ — **Done in #2896** (and a registry test keeps internals out of every why line). Three Validate `why` lines name internals the spec forbids:
  `include`, `rule_set_id` with a spec path, and `/me/sessions/{id}/results`
  (`validation.py`). Code (copy).
- ~~**F4**~~ — **Done in #2914** (ruled 2026-10-09: tighten the validator). The audit validator checks `counts` and `refs` only as
  `dict[str, int]`; `spec/architecture.md` adds non-negative counts and
  `_id`-suffixed ref keys. Author: tighten the validator or the spec.
- ~~**A4**~~ A Group instrument with no boundary tag previews every active
  reviewee as group members on the server (`views/_instruments.py`) where
  the client intersects. Not run in a browser. Author. — **Ruled 2026-10-08:
  the rule survivors.** With no boundary the Refresh returned no survivor set
  at all, so neither side filtered; now it returns the sample reviewer's
  survivors and both renders filter on them. Done in #2906.
- ~~**E7**~~ — **Done in #2896.** `theme_customizer.gen.py` maps `.pill-success` text to
  `--status-success-accent`; the pill uses `--status-success-fg`. A stale
  comment beside it names `--card-help-border`'s old primitive. Code
  (tooling).
- ~~**I9**~~ — **Done in #2896.** `tools/practice_kit.py` reports "all three harness lines present"
  over a list of seven. Code (copy).
- ~~**Stale copy and comments**~~ — **Done in #2896** (B6's docstring only; its spec half stays a row). No behavior: the audit-log page's "per-row
  pretty-print lands in 16C PR 3" (E11); `base.html`'s help-card contrast,
  border primitive, `.page-guidance-wide` opt-in count, two line refs and a
  box-shadow tally (E15); the unattached comment above `.card.placeholder`
  (E12); `_filters.py`'s `assignments_picked_handles` docstring (B6);
  `tests/conftest.py`'s pointer to the Rehydrate gate test, which is under
  `tests/integration/` (outside the corpus).
- ~~**Bc1**~~ — **Done in #2874** (found while fixing B4, #2870; medium, author; ruled 2026-10-07: refuse an edit that shifts a sent offset). **Deleting a
  fired offset can stop a later one from ever firing.** The invite and
  reminder observers record fired offsets by list index
  (`_consumed_invite_offset_indices` and its reminder twin; the outbox
  key `reminder:{sid}:{rid}:{offset_index}`). Delete a fired `-P3D` from
  `[-P3D, -PT12H]` and `-PT12H` moves to index 0, which reads as already
  fired. `spec/lifecycle.md` §8.2.6 says index-keyed dedup makes a
  re-ordered list safe; it holds only when nothing has fired. Author:
  key fired state on the offset value, or refuse edits that shift a
  fired index.
  Checked against the entry recorded at each sent position on the anchor the
  session will hold (Session Home, the lobby's End and the Settings
  import), so an anchor moved away and back is covered too.
- ~~**Bc2**~~ — **Done in #2876** (found while fixing Bc1; low, author; ruled 2026-10-07: moving End does not resend; the operator sends another by hand). **The reminder outbox key
  carries no anchor.** `_dispatch_scheduled_reminders` keys each send
  `reminder:{sid}:{rid}:{offset_index}` and skips a reviewer whose key
  exists, under any End, so after End moves a reviewer already sent
  reminder *n* never gets the new End's reminder *n* (the `_fired` row
  records `sent=0`). The manual **Send reminders** and per-row **Send
  reminder** carry no such key, so the operator can already send another;
  `spec/lifecycle.md` §8.2.6 states the rule.
- ~~**Bc3**~~ — **Done in #2877** (found while fixing Bc1, Codex on #2874; low, author) **The
  scheduled-event observer does not hold its lock across a pass.**
  `lock_session` returns the caller's already-loaded row (no
  `populate_existing`), so the observer fires from values read before the
  lock, and each recorded send commits, releasing the lock before the next.
  So a schedule save racing a Session Home GET at a fire moment can still
  leave an entry on a just-sent position (Bc1's outcome), and activation's
  `scheduled_activate_at is None` idempotency check reads a stale value.
  A lock in the save-time check alone was tried and reverted in #2874: it
  closed one order only and made every save block foreign-key inserts on
  the session (Postgres deadlock risk). **Ruled 2026-10-07: rework the
  observer's locking.** Each entry is decided, sent and recorded under a
  re-reading lock, and every schedule save locks before its gate.
- ~~**Bc4**~~ — **Done in #2881–#2885** (19U Item 1; found while fixing Bc3; medium, author) **The roster imports
  gate editability before any lock.** `_run_quick_setup_import` checks
  `is_editable` on the session loaded with the request, then saves; a
  scheduled activation committing in between leaves the roster replaced
  and assignments cascaded on a `ready` session, and
  `invalidate_if_validated`, reading the stale `validated`, writes
  `draft` over the committed `ready`. The same shape likely holds for
  every editability-gated save that does not take `lock_session`.
  Author: lock first in each such save, or have the status write
  compare-and-set against the status it read. Postgres only. The same
  gap lets a manual **Activate** that read `validated` activate a second
  time after the scheduled one. **Ruled 2026-10-07: (a) every state-gated
  save and every lifecycle transition, manual Activate included, decides
  its gate under the session lock inside the service** (Codex's ask on
  #2877). Planned as Item 1 of `guide/archive/segment_19U_post_assessment_7oct.md`.
- ~~**Bc5**~~ — **Done in #2889** (ruled 2026-10-08: extend the guard; the invitation services gate under the session lock, and the bulk Send and reminder commit once) (found while fixing Bc4, read on #2885; low, author) **The
  invitation Send and Regenerate gates decide on the loaded row.**
  `_require_validated_or_ready` / `_require_ready`
  (`app/web/routes_operator/_operations.py`) check the status the request
  loaded, outside the session lock, so a Revert committing in between can
  let a send land on a `draft` session. Bc4's ruling covered setup,
  roster, instrument, schedule and lifecycle writes, not sends. Author:
  extend the guard to the send paths, or accept the race.
- ~~**Bc6**~~ — **Done in #2888** (the started row is committed before the detour) (found while fixing Bc4, read on #2883; low, code) **Activate's
  warnings detour drops its started row.** `workflow_activate` writes
  `session.workflow_run_started`, then returns the detour redirect with
  no commit, so the row is rolled back with the request; the spec has
  the run paused at the acknowledgement, not unrecorded.
- ~~**Bc7**~~ — **Done in #2888** (the route rolls back, writes the failed row and re-raises) (found while fixing Bc4, read on #2883; low, code) **A Prepare
  whose Generate raises an exception the route does not catch
  (`IntegrityError`, `OperationalError`) leaves its committed
  `workflow_run_started` with no failed row.** Since #2883 the started
  row commits before the steps; Generate's partial commits made the same
  gap possible before.
- ~~**Bc8**~~ — **Done in #2890** (the render's repair is `instruments.repair_display_fields`, gated under the session lock) (found while fixing Bc4, read on #2884; low, author) **The
  Instruments page render writes with no state gate.** Building the page
  runs `ensure_locked_display_fields`, `prune_unpopulated_display_fields`
  and the display-field seeds, then commits
  (`app/web/views/_instruments.py`), on a session in any state. Author:
  gate the maintenance writes on `is_editable`, or leave them as
  idempotent repair. **Ruled 2026-10-08: gate them on `is_editable`.**
- ~~**Gc1**~~ — **Done in #2878** (found while fixing G1, Codex on #2875; low, author) **A
  roster tag value may contain a comma.** A group instrument names a group
  by its tag values joined with ", ", so two groups can render the same
  label (`("A", "B")` and `("A, B", "")`), and an older responses file
  naming a group that way cannot be matched. **Ruled 2026-10-07: no roster
  tag value (reviewers, reviewees, observers, relationships) may contain a
  comma, on import or edit; stored values stay as they are, with no
  warning.** Every importer and edit refuses a comma in a `tag_*` value
  (`comma_in_tag`); a row still holding one is refused when next edited
  until the comma is removed.
- ~~**Ac1**~~ — **Done in #2906** (found while fixing A4, read and raised by Codex on #2906; low, code) **The Band 2
  Refresh excludes self-reviews by the saved unit of review.** The
  member set follows the live Link 3 pill since #2906, but the
  whole-group versus pair-level self-review filter in
  `find_sample_in_scope_reviewee` (`app/services/instruments/_band1.py`)
  still reads the saved `group_kind`. With the pill switched and not yet
  saved, the sample can come from the other rule. Code: read the same
  grouped flag.
- **Carried:** old B27 / G6 (scheduled sends fire only from Session Home;
  `guide/post_azure_todo_checklist.md` §7), re-found as B3 and G4; old D4
  (`responses_import._stage` overwrites a duplicate row), re-found and
  reproduced as D1; old D19 (Rehydrate is incomplete;
  `guide/deferred_consolidated.md`).

## 2. Rulings needed

Each is a choice between changing the code and changing the contract. The
id points at its row in §3 or §1.

- **Instruments:** A4 (Group preview with no boundary), A7 (does the
  reviewer surface follow the visibility editor), G1 (Name locked on a
  group-scoped instrument).
- **Lifecycle and Setup:** Bc1 (fired offsets keyed by index), Bc2 (the
  reminder outbox key carries no anchor), Bc3 (the observer's lock
  across a pass), Bc4 (roster imports gate before the lock), Bc5 (invitation sends gate on the loaded row), Bc8 (the Instruments render's ungated writes), B1 (Quick Setup's availability against the
  `is_editable` predicate), B4 (aged Start on a rename), B5 (the P30D
  archive default nothing writes), C5 (unlock cookies across Session Home
  forms).
- **Data:** D2 (Rehydrate's scale promise), D5 (Status case), D9 (does
  Generate write the session flag back).
- **UI:** E10 (the audit log's local stylesheet), E12 (`.card.placeholder`,
  unused), E13 (role pills with no 2px edge).
- **Roles and operations:** F3 (`/add` against `/create`), F4 (the audit
  validator), F14 (`email_infra_options.md`'s ship ticks).
- **Functional spec:** G2 ("engagement" against Progress), G3 (the per-row
  reminder's audit), G8 (does the functional spec carry routes and event
  names).
- **Docs and root:** H2 (is the bulk-archive checkbox a confirm), I7 (email
  "queued" or "recorded"), I8 (the practices kit's engine builder).

Ruled 2026-10-07: B1, Bc1, Bc2, Bc3, Bc4, G1, G2, Gc1, H2 (rows say how).
Ruled 2026-10-08: Bc5, Bc8, A4, A7.
Ruled 2026-10-09: B5, C5, D2, D5, D9, E10, E12, E13, F3, F14, F4, G8.

## 3. Findings by file

One row per finding: id, severity, decides, file and lines, what the file
says against what the code does. Rows that duplicate a §1 defect name it.

**A — instruments and the reviewer surface**

- ~~**A1**~~ low spec instruments.md:1611 names an `instrument.band1_rules_updated` event — no such event_type (an invalidation reason only, _band1.py:120,171); Band 1 saves emit session_rule_set.created/.updated + instrument.group_boundary_updated — **Done in #2897.**
- ~~**A2**~~ med code sort_by_reviewee.md:225-229,247-248 no-op save emits nothing vs _display_fields.py:869-872 NULL != [] (§1) — **Done in #2868.**
- ~~**A3**~~ low spec reviewer-surface.md:962-966 dashboard match func.lower(...) vs func.lower(func.trim(...)) (_dashboard.py:102,112,123) — **Done in #2897.**
- ~~**A4**~~ low author instruments.md:934-942 group preview = rule-surviving subset vs server preview with no boundary tag = all active reviewees (§1) — **Ruled 2026-10-08: the rule survivors. Done in #2906.**
- ~~**A5**~~ low spec reviewer-surface.md:1527 short_label in "three places" (also the summary h2 :1246 and the results / collation headings); :72 "the four routes" vs five at :41-47 (Recall) — **Done in #2897.**
- ~~**A6**~~ low trim provenance: instruments.md:1561 "(findings G5; …)"; visibility_policy.md:151 "(2026-10-05)", :157-159 "now shows … as the editor always has", :214 "since findings G5"; role_landing_and_visibility.md:164 "now requires", :179 "used to carry"; reviewer-surface.md:384 "now is" — **Done in #2897.**
- ~~**A7**~~ low author visibility_policy.md:235 "whether the reviewer surface should follow is undecided" — **Ruled 2026-10-08: pills on both. Done in #2907.**
- ~~**A8**~~ low spec reviewer-surface.md:1170-1174 closed pill also shows on a ready session with no included assignment (session_lifecycle.py:808-812); :859-887 GET gating list lacks the expired bullet (read-only surface) — **Done in #2897.**
- ~~**A9**~~ low spec instruments.md:1035-1036 (at `e35ccb5c`; found while fixing Bc4, read on #2884) `preview-sample` "persists nothing" vs it saves the sample reviewee and group members through `set_band2_state` (`_instruments_band2.py`) — **Done in #2888.**

**B — assignments, workflow, lifecycle, Validate**

- ~~**B1**~~ med spec (author if the card should follow `is_editable`) lifecycle.md:560-565 Quick Setup body greyed with toggle visible but inert vs available only on draft with no responses, toggle hidden on validated (views/_quick_setup.py:201,340; _quick_setup_card.html:35-40), while the routes gate on is_editable; the card is narrower than the single predicate §3.1 / §5 say nothing undercuts; :560 also names the retired "Next Action card" — **Done in #2873** (ruled 2026-10-07: the card follows `is_editable` while no responses exist).
- ~~**B2**~~ low spec lifecycle.md:521-526 Observers exception "checkboxes only, bulk card follows the common gate", contradicting :423 vs :434; code gates the whole Unlock panel, selection and checkboxes on not archived (session_observers.html:13-18,229,559; setup_pages.md:360 right) — **Done in #2898.**
- **B3** — carried, old B27 / G6: lifecycle.md:864-870 the lazy observer runs on Session Home, Operations and the lobby vs Session Home only (_session_home.py:125). Not counted.
- ~~**B4**~~ med author lifecycle.md:886-889 aged value stays put vs Details Save re-validates the stored Start (§1) — **Done in #2870.**
- ~~**B5**~~ low author lifecycle.md:698,727 archive_offset default P30D vs nullable, no default, nothing writes it (review_session.py:108); settings_inventory.md:117 "no editor, CSV only" — **Ruled 2026-10-09: the spec marks P30D as the intended default. Done in #2908.**
- ~~**B6**~~ low spec assignments.md:932-937 reviewer-tail `@` guard "inherited from the roster pages" — C5 dropped it from filter_reviewers_rows / filter_observers_rows (_filters.py:316,526); assignments_picked_handles (:408) keeps it, its docstring (:394-404) stale — **Done in #2898.**
- ~~**B7**~~ low code validate_page.md:518-520 no internal names in a why line vs validation.py:1098-1112, 1171-1188, 1205-1218 (§1) — **Done in #2896.**
- ~~**B8**~~ low trim lifecycle.md:130-131 "(author's ruling, 2026-10-05, findings Cc5)", :836-837 "(findings G22, ruled 2026-10-06)", :849 "(author's ruling, 2026-10-06)"; self-staling "no callers": lifecycle.md:746-748, workflow_card.md:219, :933-938. Keep lifecycle.md:621-622 (data compatibility) — **Done in #2898.**

**C — Setup, Session Home and the lobby**

- ~~**C1**~~ low write quick_setup_card_spec.md:25 unavailable list omits archived, table :112-118 has no archived row; session_home.md:486-488 lists the same four (code greys archived, views/_quick_setup.py:196; session_home.md:517 right) — **Done in #2873** (the archived row, with B1).
- ~~**C2**~~ low spec session_home.md:540 "the five Setup pages" — six — **Done in #2899.**
- ~~**C3**~~ low spec session_home.md:149-150,568-575 the pause form is ready → draft only vs shared for expired (next_action_card.html:215-220; revert_session_to_draft accepts both) — **Done in #2899.**
- ~~**C4**~~ low code sessions_overview.md:277-281 over-long name is a form error vs 500 on Session Home /config and Create (§1) — **Done in #2896.**
- ~~**C5**~~ low author quick_setup_card_spec.md:81 unlock survives Session Home submissions vs cleared by /config, /revert, /workflow/*, /delete-data (main.py:41-42) (§1); session_owners.md:80-83 accurate — **Ruled 2026-10-09: the spec follows the code; only the Quick Setup and Owners cards' own posts keep the unlock. Done in #2909.**
- ~~**C6**~~ low trim sessions_overview.md Rehydrate off-by-default stated at :56-57, :195-196, :489-494; Go to Archive unconditional at :173-180, :200-203 — **Done in #2899.**
- ~~**C7**~~ low trim setup_pages.md:217-220 narrating parenthetical; sessions_overview.md:341-344 "undecided … new_ux_ideas.md" hedge — **Done in #2899.**

**D — data in and out**

- **D1** — carried, old D4, reproduced: rehydrate.md:417 every row loaded or dropped vs `_stage` overwrites a duplicate (assignment, field) — "rows 2, loaded 1, dropped 0", also when two instruments share a short label (responses_import.py:293-306). Not counted.
- ~~**D2**~~ low author rehydrate.md:460-466 Scale: streaming, batched inserts, a higher bound vs a full list and one flush (responses_import.py:129-175, 272-425); the MAX_ROWS / MAX_BYTES non-reuse holds — **Ruled 2026-10-09: the spec describes what ships; streaming stays deferred. Done in #2910.**
- ~~**D3**~~ low write csv_contracts.md:992-1000 roster re-upload deletes every pair naming a removed row vs every roster row deleted and re-added, so every relationship, assignment and response goes, even on an identical file (csv_imports.py:1189-1206) — **Done in #2900.**
- ~~**D4**~~ low code email_template_editor.md:100,260-261 whitespace resets vs stored as an override (_apply_email.py:49-52) (§1) — **Done in #2896.**
- ~~**D5**~~ low author csv_contracts.md:126,141,317 Status `active` / `inactive` only, else an error, vs lowercased first (csv_imports.py `_parse_status`); only Relationships (:355) says case-insensitive — **Ruled 2026-10-09: the spec says case-insensitive. Done in #2910.**
- ~~**D6**~~ low spec rehydrate.md:374-375 import lowercases emails vs stored as typed, only comparison keys normalized (csv_imports.py:1143-1166) — **Done in #2900.**
- ~~**D7**~~ low trim csv_contracts.md:957 names `_session_config_csv` — none; the code is export_settings_csv (_extracts.py:84) and build_setup_bundle (zip_bundle.py:90) — **Done in #2900.**
- ~~**D8**~~ low trim csv_contracts.md:583-584, :592, :652-653; rehydrate.md:82, :576; roundtrip_coverage.md:90; settings_inventory.md:583 (findings ids, ruling dates, "before … now"); hedges csv_contracts.md:728-733, :742-744 — **Done in #2900.**
- ~~**D9**~~ low author settings_inventory.md:110 Generate / Prepare "writes the session flag back" vs applies the flag to each pair's include and never writes the session flag (_generate.py:419,573-580) — **Ruled 2026-10-09: the spec says Generate re-applies the flag to the pairs. Done in #2910.**

**E — UI and visual style**

- ~~**E1**~~ low-med spec ui_elements.md:353-354 `.banner-success` is the reviewer surface's submission confirmation vs used only on session_rehydrate.html:120; the reviewer surface uses banner-info / banner-warning — **Done in #2901**.
- ~~**E2**~~ low spec ui_elements.md:1033 summary pill "1px lower" vs top:-1px, up (base.html:4551-4554) — **Done in #2901**.
- ~~**E3**~~ low-med spec operator_button_audit.md:530 (#71j) Assignments Clear only on a search, "pre-existing and open", vs shown when filter_q or status != all (session_assignments.html:321-326) — **Done in #2901**.
- ~~**E4**~~ low spec ui_elements.md:455 toggle note names `col-chip` (no such class; `.tag-chip` in `.col-chip-row`) and audience chips, deleted in E14 (the Visibility card is now a static pill-count and mode-cycle chips) — **Done in #2901**.
- ~~**E5**~~ low trim ui_elements.md:1017-1018 "since 2026-10-06 (findings E14…)", :1039 "E16;"; visual_style_rrw.md:225-226 "(findings Fc3); Segment 14B retires it". Keep the reasons — **Done in #2901**.
- ~~**E6**~~ low spec color_tokens.md:22 "tools/ harness LABELS" — none; theme_customizer.gen.py TARGETS (:110) — **Done in #2901**.
- ~~**E7**~~ low code ui_elements.md:614 success pill text `--status-success-fg` vs the customizer's `--status-success-accent` (theme_customizer.gen.py:173-175) (§1) — **Done in #2896.**
- ~~**E8**~~ low spec ui_elements.md:178-179 H2 top margin zeroed when the card's first child vs zero everywhere (base.html:1776-1781) — **Done in #2901**.
- ~~**E9**~~ low write `.rrw-sort-btn`, `th.rrw-sortable`, `.rrw-sort-badge` (base.html:4306-4351, eight tables) in neither ui_elements.md nor operator_button_audit.md (§11 has the cloned `.sort-btn`) — **Done in #2901**.
- ~~**E10**~~ low author sys_admin_session_audit_log.html:7-81 local `<style>` (audit-log table, columns, detail) uncatalogued, against base.html owning the CSS (as the E14 ruling) — **Ruled 2026-10-09: move it into base.html and catalogue it. Done in #2911.**
- ~~**E11**~~ low code sys_admin_session_audit_log.html:98-100 "lands in 16C PR 3" — it ships (§1) — **Done in #2896.**
- ~~**E12**~~ low author ui_elements.md:278-288 `.card.placeholder` (base.html:2056-2068): no markup uses it (the unattached comment above it went in #2896) — **Ruled 2026-10-09: keep it for scaffolds; the spec says so. Done in #2911.**
- ~~**E13**~~ low author ui_elements.md:626 every interactive chip has a 2px edge vs the dashboard's role pills and `rs-role-nav-muted` (reviewer/dashboard.html:53-67, reviewer/_role_chips.html:26) with none — **Ruled 2026-10-09: linked role pills take the edge. Done in #2912.**
- ~~**E14**~~ low spec operator_ui_concept.md:386 quotes the outbox intro incompletely (the partial adds reminder, responses-received and raw-URL sentences); the partial's header says sys_admin_sessions.html only, but sys_admin_session_outbox.html renders it — **Done in #2901**; the partial's header comment in #2911.
- ~~**E15**~~ low code base.html comments: :242-252 help-card border "~1.5:1" (now 2.54 / 1.95), :455-459 border primitive, :1971 "TWO pages opt in" (all four rosters), :3024, :3037 line refs, :1087 "eight box-shadow uses" (§1) — **Done in #2896.**

**F — architecture, roles and operations**

- ~~**F1**~~ med spec operations_pages.md:292 reviewer name links "when an Invitation row exists" vs :373-381 every row, reviewer-keyed; code links unconditionally (session_invitations.html:218-221) — **Done in #2871.**
- ~~**F2**~~ low trim operations_pages.md:402-404 "(findings Fc2); Segment 14B restores the label" (keep the constraint); :200-206 narrates "was aligned … was left counting" — **Done in #2902.**
- ~~**F3**~~ low author architecture.md:205-206 creation is `{collection}/add` vs reviewers/create, observers/create, page-break/create and bare collection POSTs (_setup_reviewers.py:370) — **Ruled 2026-10-09: `create` makes a row, `add` attaches a member. Done in #2913.**
- ~~**F4**~~ low author architecture.md:687-690, 759-761 counts non-negative, refs keys end `_id` vs audit.py:313-319 (§1) — **Ruled 2026-10-09: tighten the validator. Done in #2914.**
- ~~**F5**~~ low spec audience_and_identity_model.md:167-169 Promote / Demote shown only to a super-admin vs can_manage_admins, also any admin while none is configured (_sys_admin.py:233-236); permissions.md:170-177 right — **Done in #2902.**
- ~~**F6**~~ low spec audience_and_identity_model.md:147-151 per-row checkbox and bulk toolbar vs single selection (sys_admin_users.html:102-109, 390-395) — **Done in #2902.**
- ~~**F7**~~ low spec permissions.md:117 re-resolve list omits bulk-unarchive and bulk-delete-archived (_lobby.py:223-270) — **Done in #2902.**
- ~~**F8**~~ low spec permissions.md:193 not_in_workspace = "lacks both flags"; also when no users row matches (_session_home.py:759-764) — **Done in #2902.**
- ~~**F9**~~ low write permissions.md:82,222 401 only for no email claim vs also no headers with fake auth off (identity.py:113-117) — **Done in #2902.**
- ~~**F10**~~ low spec permissions.md:305 points at operator_ui_concept.md "Sys Admin"; the heading is "6. System Admin / System Setup Pages" — **Done in #2902.**
- ~~**F11**~~ low spec architecture.md:370 "optional list_options string" vs column list_csv (instrument_field.py:112-113); list_options is a Band 2 payload key — **Done in #2902.**
- ~~**F12**~~ low spec architecture.md:471 "Generate is idempotent (operator-paced…)" — no Generate control; generate_invitations is a Prepare step (_workflow.py:248) — **Done in #2902.**
- ~~**F13**~~ low spec email_infra_options.md:74-83 EmailMessage cc / bcc bare `list[str]` vs default_factory (email_send.py:62-63) — **Done in #2902.**
- ~~**F14**~~ low author email_infra_options.md ✅ / ◻ ship ticks at :348-353, :409-415, :483-485, :549-551 survived old F13 — **Ruled 2026-10-09: the ticks go, as F13 ruled. Done in #2913.**

**G — the functional spec** (all rrw_functional_spec.md)

- ~~**G1**~~ med author §5.8 :518-522 a group-scoped instrument has no locked rows (unticking Name drops member names); the service allows it and the reviewer surface honors it (_response_fields.py:417-427; _reviewer_summary.py:327-333), but the builder always locks Name (views/_instruments.py:661; instruments_index.html:1939-1943, 4045); instruments.md:871-874 "stays ticked" and :932 "when Name is selected" disagree — **Ruled 2026-10-07: Name stays locked on group instruments.** Spec in #2872; in #2875 the service and Settings import keep Name shown, and every reader that lists a group's members does so whatever a stored row says.
- ~~**G2**~~ med author §9.9 :1450 "engagement (opened / first-response / submitted)", §2.7 "invitation engagement" vs Progress = not started / in progress / submitted (views/_progress.py:30-35); nothing renders opened_at; operations_pages.md:298 right — **Done in #2872** (ruled 2026-10-07: the spec follows Progress).
- ~~**G3**~~ med author §2.12 :113-115 every send attempt audited, §5.13 every mutating service vs the per-row reminder (§1); §15 :2280-2282 contradicts §2.12 — **Done in #2869.**
- **G4** — carried, old B27 / G6: §8.3 :966-969 triggers fire on the next operator GET. Same as B3. Not counted.
- ~~**G5**~~ low spec §5.12 :606-608 an invitation created "(or auto-send schedule)" vs only Prepare creates (invitations.py:155); §11.4 :1984-1987 says so — **Done in #2903.**
- ~~**G6**~~ low trim §12.5 :2135-2137 "seeded entries omitted from the Settings extract" — nothing seeds (_serialize.py:562); "Four of the five roster pairs (… Settings)" loose — **Done in #2903.**
- ~~**G7**~~ low write §9.1 :1070-1072 lobby expander "rename and deadline adjust" omits Code and Tags; §9.2 :1129-1130 "Clone" vs "Duplicate" / "Duplicate settings only" — **Done in #2903.**
- ~~**G8**~~ low :1448-1449 email status sent / queued / not sent omits sending and failed (email_outbox.py:23) [write]; glossary :2463-2468 "D6 source" plan label [trim]; preamble :7-8 URLs live in per-surface specs, yet the file carries routes and event names [author] — **Write and trim parts done in #2903**; the preamble ruled 2026-10-09 (soften it, no sweep) and **done in #2915.**

**H — docs/**

- ~~**H1**~~ high code backup_restore.md:85-87, operations_runbook.md:62-67 in-app removal is safe vs remove_user cascade-deleting every session the user created (§1); deployment_dev.md:321-327 and deployment_nus.md:316-318 on raw DELETE need re-reading against it — **Done in #2867**; the raw-DELETE docs hold as written
- ~~**H2**~~ med author security_posture.md:216-243 §5.7 "no gaps found" omits POST /operator/sessions/bulk-archive (purge_and_archive deletes responses, rosters and the audit log with no confirm parameter, unlike bulk-delete; the UI has only the "Archive after purging" checkboxes) and Sys Admin remove-from-all-sessions and delete user. Is a checkbox a confirm? — **Done in #2872** (ruled 2026-10-07: the ticked purge box is the confirmation; §5.7 lists purge-and-archive and the Sys Admin removes).
- ~~**H3**~~ low-med doc known_limitations.md:60-62 targeted reminders missing vs the per-row Send reminder and send_reminders_to_incomplete; what is missing is delivery (its own :51-55) — **Done in #2904**.
- ~~**H4**~~ low trim cli_setup.md:379, :394, :646-647 still prescribe the `admin:repo_hook` scope (old H14 applied in part) — **Done in #2904**.
- ~~**H5**~~ low doc known_limitations.md:69-71 failure "is logged" vs a log line and an audit event, session.scheduled_event_failed — **Done in #2904**.
- ~~**H6**~~ low doc backup_restore.md:64-67, architecture.md:116-117 omit Rehydrate's dropped-responses CSV (_rehydrate.py:246); deployment_nus.md:354-355 "404 in a deployed environment" vs 404 everywhere unless REHYDRATE_ENABLED — **Done in #2904** (the architecture.md citation names no stash sentence; unchanged).
- ~~**H7**~~ low trim security_posture.md:90-92, 109-133 narrate earlier drafts, :135 "a dozen sites" (13); database.md:157-164 "added by this review"; unenforced_conventions.md §1.2 "17 routing modules" (16), §1.1, §2.1, §2.2 dated tallies — **Done in #2904**.
- ~~**H8**~~ low guide/codex_assessment_30sep.md:11 cites docs/nus_azure_status_v7.md (gone) — **Left as is: declined as old H13, dated records are history.** Not counted.

**I — root and process documents**

- ~~**I1**~~ med doc rrw_sdd_in_practice.md:46 quotes a functional-spec header ("the functional contract is stable; ship-state may move ahead of it", "points at the sweep record") removed in 19M; spec/README.md:20 gives currency to the sweep records. Also "now 2,416 lines" (2,562) — **Done in #2871.**
- ~~**I2**~~ low doc rrw_sdd_in_practice.md:205 21 Claude and 4 Codex assessments vs the appendix :308 "19 + 3" — **Done in #2905**.
- ~~**I3**~~ low trim rrw_sdd_in_practice.md undated figures moved: CLAUDE.md "297" lines (:235; 301), tests 4,800 (:306; 5,445 collected), churn 1.1x (:269; 1.2x), duplication 6.3% (:270, :311; 5.8%), spec files 40 (:58; 35), spec lines 24,362 (25,603), docs 18 (14). Re-take with a date, or drop — **Done in #2905** (no edit: the header anchors the figures at `3559c7a7`, where they reproduce).
- ~~**I4**~~ low doc rrw_sdd_in_practice.md:107 (+ :244, :302) "last 200 merges" plan 76% / spec 31% do not reproduce (77 / 26 at 3559c7a7; 89 / 70 at HEAD); the window is undefined — **Done in #2905** (the window is now defined; the figures reproduce at `3559c7a7`).
- ~~**I5**~~ low doc README.md:42, :81 "any non-archived session can be archived" vs can_archive refuses ready (session_lifecycle.py:80-86); the Workflow card offers it on expired only — **Done in #2905**.
- ~~**I6**~~ low doc README.md:41 "per-row rename" vs the expander edits Name, Code, Deadline and Tags — **Done in #2905**.
- **I7** low author rrw_design_rationale.md:195 email "queued but not yet wired" vs "recorded, not sent" elsewhere (README.md:103); invitations flip to sent, responses-received stays queued
- **I8** low author new_project_practices_setup.md:307-326 one shared engine builder with URL write-back vs this repo's three (conftest.py:60-62, session.py:30, env.py:25), none writing back
- ~~**I9**~~ low code tools/practice_kit.py:285 "three" over seven (§1) — **Done in #2896.**
- **I10** low author azure_ask.md:228-229 migrations round-tripped on SQLite and Postgres, wrong at its date (2026-07-09). A dated record; old I5 left it so

**Outside the corpus** (found by the I read; low, no area id)

- ~~tests/conftest.py:17 cites the Rehydrate gate test under `tests/unit/`; it is in `tests/integration/`.~~ — **Done in #2896.**
- ~~guide/README.md's `codex_assessment_*` row places `DATED_DOC` in test_doc_conventions.py; it is in test_doc_references.py:77.~~ — **Done in #2905.**
- ~~guide/post_azure_todo_checklist.md:106 gives azure_ask.md 244 lines; it has 258.~~ — **Done in #2905.**
