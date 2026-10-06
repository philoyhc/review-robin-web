# Findings — corpus sweep (2026-10-05)

**Found by:** `guide/sweep_2026-10-05_corpus.md` · **Read at:** `2d7e5b5f`
(#2826) · **Open:** every row below that is not struck.

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
restart at 1 in this file; an id from the 2026-10-03 register is written
"old A5". **Severity** is the reader's. **Decides:** *spec* means the spec
is wrong and an update in place fixes it; *code* means the code is wrong
against a spec that is right; *author* means it is a choice between fixing
the code and changing the contract; *trim* means history, provenance or a
tally to strip, keeping the reason it carried; *write* means a surface with
no adequate spec. In `docs/` and root rows, *doc* plays the part of *spec*.
Line numbers are at `2d7e5b5f`.

## 1. Code defects

Confirmed by reading the code; *reproduced* means a reader (or the sweep's
author, marked *re-checked*) also ran it.

**High**

- ~~**F1 / Fc1**~~ — **Done in #2828.** Correction found at the fix: the test that pinned invite-as-admin ran with no super-admin configured, when any admin may grant, not as a super-admin. **An admin can create an admin by inviting a fresh
  email.** `users.invite(is_sys_admin=True)` has no super-admin guard
  (`app/services/users.py` `invite`; route `_sys_admin.py` `invite_user`;
  the checkbox shows to every admin), while `promote` refuses with
  `requires_super_admin`. `spec/permissions.md` §4 says only a super-admin
  (or any admin while none is configured) may grant the flag. The test
  that pins invite-as-admin runs as the fake identity, a super-admin.
  *Re-checked.* Decides: code, the safer fix; the author confirms the
  rule.

**Medium**

- ~~**A16 / Ac1**~~ — **2026-10-05: all or nothing, the fixer's choice with no ruling asked. Done in #2834.** **The Instrument card's Save is not atomic.** Band 1,
  Link 3, self-review, column widths, sort, identity and visibility commit
  in service calls before the Band 2 snapshot is validated
  (`routes_operator/_instruments.py` `/save`), so a 422 for a bad
  response-field shape leaves the rest persisted while the card reports
  failure, and the configured pill is not repainted. *Reproduced.* Author.
- ~~**A17 / Ac2**~~ — **Ruled 2026-10-05: a normalizing migration. Done in #2833** (`14db60023e88`). **Legacy visibility rows break round trip and Save.**
  `instrument_view_policies` rows written by the backfill migration
  `a7e3b1d92c64` that predate the per-cell rule are never normalized: an
  export→import of a reviewer `while_ongoing` NULL row is refused (blocking
  Quick Setup re-import and Rehydrate), and an observer `while_ongoing =
  raw` row makes every Save of that card 422. Only Replicate tolerates
  them. *Reproduced.* Author: a normalizing migration, or tolerance.
- ~~**G / Gc1**~~ — **Done in #2829.** **A reminder after a token regenerate mails a dead link.**
  `send_reminder` reuses `most_recent_invitation_url`, the URL in the last
  invitation outbox body, after `regenerate_token` / `regenerate_all_tokens`
  rotated the hash; the bulk and scheduled reminder paths both reach it, and
  only the per-row button hides for `pending`. *Re-checked.* Code. Related
  to the `regenerate_token` stub in `guide/todo_master.md`.
- ~~**B8 / Bc2**~~ — **Ruled 2026-10-05: stay `validated`. Done in #2832.** **A failed Activate demotes `validated` → `draft`,**
  including pressing Activate in State 4Err with errors at re-validation;
  the comment in `_workflow.py` describing it is inverted. The spec never
  says so. Author.
- ~~**B2 / Bc1**~~ — **Ruled 2026-10-05: match Session Home. Done in #2832.** **The lobby expander's Name / Code / Deadline gate is
  `is_draft`; Session Home's is `draft` or `validated`.** Unlisted as an
  exception to `spec/lifecycle.md`'s single-predicate rule. Author.
- ~~**C1 / Cc1**~~ — **Done in #2829.** `Showing 0 <noun>.` renders beside the no-match message on
  all four roster pages. *Reproduced.* Code.
- ~~**C3 / Cc2**~~ — **Done in #2829.** On `expired` / `archived`, Reviewers, Reviewees and
  Relationships render a live editor row from a typed `?add=1` or
  `?edit_id=` whose Save answers 409 (they gate on `is_ready`; Observers is
  right). *Reproduced.* Code.
- ~~**D2 / Dc1**~~ — **Done in #2829.** **The Settings CSV round trip is not byte-stable:**
  `instruments[n].order` is exported 0-based and re-imported as `n` from 1.
  *Reproduced.* Code.
- ~~**D12 / Dc2**~~ — **Done in #2829.** A Settings import writes `responses_received_enabled:
  true` into `email_template_overrides` for a session with none, so
  Validate then reports custom overrides. *Reproduced.* Code.
- ~~**D18 / Dc3**~~ — **Done in #2829.** `parse_responses_csv` silently drops a non-blank row
  shorter than 21 cells: neither loaded nor dropped. *Reproduced.* Code.
- ~~**D11 / Dc4**~~ — **Done in #2830**, with a cell past the `csv` module's field limit refused too (see Dc8). Roster, relationship and observer CSVs, roster
  label headers and data-shape names have no length check against their
  `String(255)` / `String(2000)` columns (the Settings import does);
  Postgres would answer 500. *Reproduced on SQLite; the 500 is inferred.*
  Code.
- ~~**E7 / Ec8**~~ — **Done in #2830.** `.chrome-link` has a rule only inside `.chrome-user`, so
  the Owners card's Remove buttons render as browser-default buttons and
  the audit log's `Older events →` is an unstyled link; the button audit
  calls the reuse deliberate. Code.
- ~~**Ec1**~~ — **Done in #2830** (`--row-pending-bg`). Pending Band 3 rows use a raw `rgba(254, 243, 199, 0.5)` fill
  (`base.html`) with no token and no dark override; about 3:1 for body text
  in dark by arithmetic, and invisible to the contrast audit. Code.
- ~~**I2 / Ic1**~~ — **Ruled 2026-10-05: drop the Chromium step until `tests/browser/` exists. Done in #2831.** The practice kit ships `ci.yml` verbatim, Playwright and
  Chromium step included, but its `dev` extra omits `playwright`: a
  kit-built repository's first CI run fails. Code (the kit).
- ~~**H12 / Hc1**~~ — **Ruled 2026-10-05: require `TEST_DATABASE_URL`. Done in #2831.** `tests/conftest.py` falls back to `DATABASE_URL` and
  runs `DROP SCHEMA public CASCADE` on any non-SQLite target; the docs
  that describe the fallback carry no warning. Author.

**Found while fixing** (2026-10-05, after the read)

- ~~**Dc8**~~ — **Done in #2835.** Rehydrate (`app/services/session_rehydrate.py`
  `_emails_from_csv`, `_row_count`, `_parse_settings`) and Quick Setup's
  settings reader (`routes_operator/_quick_setup.py`) let `csv.Error` from
  a cell past the 131,072-character field limit escape as a 500; the
  roster parsers refuse it since #2830. Code.
- ~~**Cc3**~~ — **Done in #2835.** The single-row roster create / edit forms and the friendly-label
  editor have no length check against their `String(n)` columns; the CSV
  paths have one since #2830. The Postgres 500 is inferred. Code.
- ~~**Cc4**~~ — **Done in #2835.** After Regenerate, the Invitations drill-in still shows the
  link from the last invitation sent, which no longer works. Code.
- ~~**Cc5**~~ — **Ruled 2026-10-05: a change that does not affect validation demotes neither on Session Home nor in the lobby, and no Details field can. Done in #2836.** A Session Home Details Save that changes nothing still demotes
  a `validated` session to `draft`; the lobby expander checks for a change
  since #2832. Author.
- ~~**Cc6**~~ — **Done in #2835**, for Start and the release window too. The Session Home config card re-parses an untouched deadline
  box on every Save, so a deadline in the repeated hour after a DST
  fall-back comes back an hour early (`_session_home.py`
  `_apply_session_config_form`); the lobby compares the box's text since
  #2832 (`sessions.datetime_box_unedited`). Code.
- ~~**Dc9**~~ — **Declined 2026-10-05 (author): Rehydrate is incomplete and not reachable (rehydrate_enabled is false), so a limit on it is moot.** A free-text answer with no maximum can be longer than the
  `csv` module's 131,072-character field limit: the responses extract
  writes it, and Rehydrate refuses the set (`spec/rehydrate.md` §9,
  since #2835). Author: raise the parser's limit or cap answers.
- **Dc10** — A Settings-CSV apply onto a session whose `instruments`
  relationship is already loaded resolves data shapes against the
  deleted rows: `_wipe_instruments_and_dependents` deletes with
  `db.delete()` and `_apply_instruments` adds new `Instrument` rows
  without touching the collection, so `_apply_data_shapes` reads stale
  instruments, and the insert fails with an FK `IntegrityError` once
  ids are not reused (SQLite's reuse hides it). Present on main before
  D20; no current route loads the relationship first. Expire
  `review_session.instruments` after the rebuild, or query `Instrument`
  directly. Code. Found by the D20 cold read (#2856).
- **Ec10** — `error.html` (a standalone page with its own `<style>`)
  still gives its card `box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06)`
  against the "no drop shadows" rule (`spec/visual_style_general.md`),
  the rule E16 applied to the reorder toast. Separately, the
  Instruments page still defines `window.newModelToggleAudience`, which
  nothing calls since the audience-chip markup went (d2cbe8d9). Code.
  Found by the E14 cold read (#2857).
- **Fc2** — The reviewer drill-in on Manage Invitations labels its send
  time "Email sent:" (`operator/session_invitations_reviewer_detail.html`),
  which reads as delivered while sending is off — the claim F12's note
  corrects on the page above it. Reword with the 14B copy (Segment 14B
  "Copy to retire"), or add it to that list. Copy. Found by the F12 cold
  read (#2858).
- ~~**Ec9**~~ — **Done in #2850.** The Link 3 builder's boundary cells disagree between a card
  as rendered and one just edited: the template gives every saved cell
  an X (the first disabled), while `newModelRefreshUnitButtons`, called
  only from add and remove, turns every cell but the last into a
  disabled AND (`operator/instruments_index.html`). A saved two-tag unit
  therefore shows X X on load and AND X after any edit. Run the refresh
  on load, or render the AND server-side. Code.
- **Gc3** — `spec/rehydrate.md` ("Rehydrate therefore carries no
  view-policy code of its own") names "config-only clone" among the
  consumers of the settings round-trip. Clone copies in the database
  and never goes through the CSV; since G5 it copies the grid through
  `copy_view_policies`. Prose. Found by the G5 cold read (#2859).
- ~~**Gc2**~~ — **Done in #2850.** The Sessions Diagnostics visibility-grid audit
  (`operator/sys_admin_sessions.html`) still says a row written by an
  import before the guard "is still stored, and the resolver honours
  it", naming a session-ongoing reviewee grant. Migration
  `14db60023e88` (#2833) rewrote every such cell to off, so the warning
  describes rows that can no longer exist; the copy also carries a
  segment number. Code (template copy).

**Low**

- ~~**Ac3**~~ low-med — **Ruled 2026-10-05: non-identifying order. Done in #2840** (participant token, then reviewer id). Anonymized reviewee results order rows by reviewer
  name, so the position of a dashed row can identify its reviewer. Author.
- ~~**Ac4**~~ — **Done in #2840** (one scoped COUNT). `reviewer_review_count_for_user` loads every active reviewer
  in the workspace on each reviewer-chrome render.
- ~~**D9 / Dc5**~~ — **Ruled 2026-10-05: fix order in code. Done in #2840.** `data_shape_extract` has no `ORDER BY`, and By instrument
  breaks ties unordered: output order can differ between runs on Postgres.
- ~~**D6 / Dc6**~~ — **Ruled 2026-10-05: document as is. Done in #2838.** Responses on inactive pairs are in `responses.csv` and
  absent from By instrument, metadata and Data shaper output; nothing says
  so. Author.
- ~~**D10 / Dc7**~~ — **Ruled 2026-10-05: report row detail. Done in #2840.** A Settings row under three cells refuses the whole file
  with no row detail.
- ~~**Ec2**~~ — **Done in #2839** (`--space-6`; `tests/unit/test_css_tokens_resolve.py` now checks every `var()` resolves). `var(--space-5)` in `base.html` names no token; the padding
  falls to 0.
- ~~**H2 / Hc4**~~ — **Done in #2837.** Three `data_shape` foreign keys carry no index, against
  `docs/database.md`'s rule.
- ~~**I / Ic3**~~ — **Done in #2838** (18Q passes; 20 now fails only C3, correctly, until the segment is built). `close_check` fails 18Q (C2, a retired `docs/` path in its
  Doc impact) and 20 (C1, no `Doc impact` heading) as the plans stand.
- ~~**I / Ic2**~~ — **Done in #2838.** The session-start hook warns about Chromium in a
  kit-built repository with no `tests/browser/`.
- ~~**Ec3–Ec6**~~ — **Done in #2839** (Ec4 removed sixteen, the count at the fix). Dead CSS (`.instrument-card-short-label`); fifteen classes
  in markup with no rule, script, test or spec; the two Instruments error
  banners' inline flex where `.banner-actions` exists; a bare
  `<small class="muted">` where `.form-help` is owed.
- ~~**Stale comments**~~ — **Done in #2838**, with the archived extract-data plan pointers across `app/`. No behavior: `results.html` header; the
  `data-rs-discard` note in `review_surface.html`; `_dashboard.py` on
  pre-open; `instrument.py` citing an archived spec and a dropped table;
  `_instrument_crud.py` "two acceptance flags"; `_quick_setup_card.html`
  and `views/_quick_setup.py`; `_validate.py`'s step number; `monitoring.py`
  on the at-risk fraction; `app/config.py`'s `operator_contact_email` and
  `audit_strict_mode` comments; three in `base.html` and one in
  `session_setup_status_row.html`.
- **Carried:** old B27 / G6 (scheduled sends only on Session Home;
  `guide/post_azure_todo_checklist.md` §7, with the auto-send caption on
  `expired` / `archived`); old D4 and D19 (Rehydrate, in
  `guide/deferred_consolidated.md`).

## 2. Rulings needed

Each is a choice between changing the code and changing the contract. The
id points at its row in §3 or §1.

- **Instruments:** ~~A5~~ (Band 2 group preview for a pair-context boundary),
  ~~A9~~ (Integer bounds on stored non-whole rows), ~~A16~~ (Save atomicity), ~~A17~~
  (legacy visibility rows), ~~Ac3~~ (anonymized row order).
- **Lifecycle and workflow:** ~~B2~~ (lobby gate), ~~B8~~ (Activate failure
  demotes), ~~B12~~ (Validate commits a derived cache; carve out or stop).
- **Setup:** ~~C5~~ (the exact-handle match on Invitations and Responses).
- **Data:** ~~D1~~ (bracket index or row position orders instruments), ~~D6~~
  (inactive pairs across lenses), ~~D9~~ (extract row order), ~~D10~~ (short-row
  detail), ~~D17~~ (Rehydrate preview counts), ~~D19~~ (short-label uniqueness),
  ~~D20~~ (data-shape refs to unlabeled instruments).
- **UI:** ~~E1~~ (chip edge 1px or 2px), ~~E14~~ (the Instruments page's local
  stylesheet), ~~E16~~ (the reorder toast's shadow).
- **Roles and operations:** ~~F1~~ (confirm the invite rule), ~~F12~~ (the
  "counters cannot move" note), ~~F13~~ (14B's plan inside
  `spec/email_infra_options.md`).
- **Functional spec:** ~~G5~~ (Duplicate drops visibility policies, deadline
  and schedule), ~~G22~~ (Settings import skips the schedule ordering chain),
  ~~G26~~ (audit log "immutable" against Delete session and Purge).
- **Docs and root:** ~~H5~~ (Postgres private endpoint, Azure-only), ~~H11~~
  (`deployment_nus.md` §6.3 against `deploy_nus.yml`), ~~H12~~ (the test
  fixture's schema drop), ~~I2~~ (the kit's CI), ~~I8~~ (`azure_ask.md` unindexed).

All ruled 2026-10-06. The rows marked *Ruled* in §3 are code changes, landing one PR each.

## 3. Findings by file

One row per finding: id, severity, decides, file and lines, what the file
says against what the code does. Rows that duplicate a §1 defect name it.

**A — instruments and the reviewer surface**

- ~~**A1**~~ low spec participant_model.md:159 min/max live-update partial on all four schedule inputs vs Create only — **Done in #2841.**
- ~~**A2**~~ low spec instruments.md:982 _inline_list_options vs _inline_list_csv — **Done in #2841.**
- ~~**A3**~~ low spec instruments.md:226-228 form wraps body vs empty form + form= attrs — **Done in #2841.**
- ~~**A4**~~ low spec instruments.md:939 "... + N more" vs ", +N more" — **Done in #2841.**
- ~~**A5**~~ low author instruments.md:937-939 group preview rule-surviving subset vs reviewee-side boundary only (views/_instruments.py:555-588) — **Done in #2853** (ruled 2026-10-06: the spec states the pair-context fallback, and the fallback applies Links 1–2).
- ~~**A6**~~ low write instruments.md:1030-1032 route inventory omits edit/fields/display-fields/preview-sample — **Done in #2841.**
- ~~**A7**~~ low spec reviewer-surface.md:350-353 page_statuses every instrument vs only those with included assignments — **Done in #2841.**
- ~~**A8**~~ low spec reviewer-surface.md:924-926 every GET/POST runs observe_deadline vs surface/save/submit/clear/recall + operator Instruments GET only — **Done in #2841.**
- ~~**A9**~~ low author reviewer-surface.md:463-467 bounds as entered vs int() truncation on stored legacy rows (views/_instruments.py:166-225) — **Done in #2854** (ruled 2026-10-06: Integer bounds print as entered).
- ~~**A10**~~ low code participant_model.md:108; reviewer-surface.md:1073-1075 /me reviewee role needs email-identified vs _dashboard.py:96-105 no check, no strip — **Done in #2841.**
- ~~**A11**~~ low trim instruments.md:128-130,144-145 provenance + restated — **Done in #2841.**
- ~~**A12**~~ low trim instruments.md:162-168,410-414 rollout/migration history — **Done in #2841.**
- ~~**A13**~~ low trim reviewer-surface.md:1532-1533; sort_by_reviewee.md:280,208; participant_model.md:70-71,73 — **Done in #2841.**
- ~~**A14**~~ low trim plan slice ids participant_model.md:70,73,100,130,161,182-183; reviewer-surface.md:1352,1449,1454 — **Done in #2841.**
- ~~**A15**~~ low spec sort_by_reviewee.md:338,371 "four rosters" vs three (observers unsorted) — **Done in #2841.**
- ~~**A16**~~ low author instruments.md:1104-1106,1395-1396 bad row 422 edits intact vs non-atomic save (=Ac1) — **Done in #2834.**
- ~~**A17**~~ low spec visibility_policy.md:128-139 §4.1 legacy rows only handled for Replicate (=Ac2) — **Done in #2833.**

**B — assignments, workflow, lifecycle, Validate**

- ~~**B1**~~ med spec lifecycle.md:417-420 observers "no readiness rule references them" vs observers.duplicate_email, cross_roster_identity (validation.py:1114-1156) — **Done in #2842.**
- ~~**B2**~~ med author lifecycle.md:424-426 lobby expander narrower predicate (is_draft) unlisted exception — **Done in #2832.**
- ~~**B3**~~ low spec lifecycle.md:178-181 revert on Setup page while validated: none; only Workflow card; "Next Action card" old name — **Done in #2842.**
- ~~**B4**~~ low spec lifecycle.md:725-727 skipped trigger clears column: only activation; invites/reminders mark consumed via audit — **Done in #2842.**
- ~~**B5**~~ low spec lifecycle.md:804-811 _schedule_ordering_js partial only in session_new.html; Session Home own script, no min/max — **Done in #2842.**
- ~~**B6**~~ low spec lifecycle.md:827-829 past fire time rejected: Release-from, End have no floor; garbled example — **Done in #2842.**
- ~~**B7**~~ low trim lifecycle.md:155 "legacy internal name Pause"; :570 "Audit events (full list)" overclaims — **Done in #2842.**
- ~~**B8**~~ med author workflow_card.md:498-501,549-554,359-367 Activate failure path vs _workflow.py:346-416 (no mark_validated; demotes on any failure incl. 4Err pre-flight) — **Done in #2832.**
- ~~**B9**~~ low trim workflow_card.md:379-380 "today's worst case is 4" — **Done in #2842.**
- ~~**B10**~~ low trim workflow_card.md:621-625, 856-863 open-work/ship-state notes — **Done in #2842.**
- ~~**B11**~~ low write workflow_card.md:171-186 archived state: card renders empty body — **Done in #2842.**
- ~~**B12**~~ med author validate_page.md:42-44,393-394,514-516 "never writes" vs persist_reconcile_warm commits cache (_operations.py:192) — **Done in #2852** (ruled 2026-10-06: spec carve-out for the derived reconcile cache).
- ~~**B13**~~ low spec validate_page.md:114-116,136-139 status strings vs ✓/— and bare numbers (_validate.py:186-239) — **Done in #2842.**
- ~~**B14**~~ low write validate_page.md:46-56 query params omit return_to, super_*, prepare_confirm — **Done in #2842.**
- ~~**B15**~~ med spec assignments.md:184-188,205 combinator NONE_OF vs ALL_OF/ANY_OF/PIPELINE (rules.py:36-41) — **Done in #2842.**
- ~~**B16**~~ low spec assignments.md:155-159 predicate fields also reviewer.email/reviewee.email — **Done in #2842.**
- ~~**B17**~~ low spec assignments.md:95-98,25 per-row Include toggle vs read-only pill — **Done in #2842.**
- ~~**B18**~~ low spec assignments.md:414-415 self-review rows always materialised vs omitted with exclude — **Done in #2842.**
- ~~**B19**~~ low spec assignments.md:985 example 500 vs cap 200 — **Done in #2842.**
- ~~**B20**~~ low spec assignments.md:545-547 "... + N more" vs ", +N more", show_members — **Done in #2842.**
- ~~**B21**~~ low trim assignments.md:1190-1191 history; :1283-1285 measurement; :34-40 superseded designs — **Done in #2842.**

**C — Setup, Session Home and the lobby**

- ~~**C1**~~ med code setup_pages.md:540-550 no count line on no-match vs "Showing 0 …" — **Done in #2829.**
- ~~**C2**~~ med spec setup_pages.md:540-548 quoted template gate shape stale (real: session_reviewers.html:690, :822) — **Done in #2843.**
- ~~**C3**~~ med code setup_pages.md:1653-1672 page offers only what routes accept vs is_ready-only gating — **Done in #2829.**
- ~~**C4**~~ low spec setup_pages.md:1633-1637 tag_slot_presence/chip_slots vs *_column_state + tag_slot_counts (views/_setup.py:340-450); drop "LIMIT 1" — **Done in #2843.**
- ~~**C5**~~ low author setup_pages.md:1074-1085,1112-1115 exact-handle match only for offered labels vs ops filters any "(…)" tail (_filters.py:182,235); "@" requirement unstated (:316,:526) — **Done in #2855** (ruled 2026-10-06: the ops filters exact-match only an offered label).
- ~~**C6**~~ med spec sessions_overview.md:29-31 audience "authenticated users… reviewers land on /r/" vs require_operator; /me routes — **Done in #2843.**
- ~~**C7**~~ low spec sessions_overview.md:186-190,163-166,44,60-61 Rehydrate listed live vs off by default (contradicts :477-480) — **Done in #2843.**
- ~~**C8**~~ low spec session_home.md:214-215 Extract Setup card placement — **Done in #2843.**
- ~~**C9**~~ low spec setup_pages.md:266-267 preview card also on empty editable roster — **Done in #2843.**
- ~~**C10**~~ low spec setup_pages.md:664 data-rrw-sortable dropped in edit/add mode — **Done in #2843.**
- ~~**C11**~~ low spec setup_pages.md:188 pair-context slot offered only for active rows (views/_instruments.py:859-860) — **Done in #2843.**
- ~~**C12**~~ low spec quick_setup_card_spec.md:29-50,114; session_home.md:453 "Settings" vs shipped "Session settings" — **Done in #2843.**
- ~~**C13**~~ low spec session_owners.md:150 set_owners signature — **Done in #2843.**
- ~~**C14**~~ low spec quick_setup_card_spec.md:63, sessions_overview.md:317 cite "§ What a delete takes with it" — not a heading — **Done in #2843.**
- ~~**C15**~~ low spec spec/README.md:42 setup_pages row omits Instruments, Email Template — **Done in #2843.**
- ~~**C16**~~ low trim history: setup_pages.md:119,527,615; quick_setup_card_spec.md:51; session_home.md:160 — **Done in #2843.**
- ~~**C17**~~ low trim sessions_overview.md:341-350 contrast/luminance figures — **Done in #2843.**

**D — data in and out**

- ~~**D1**~~ med author csv_contracts.md:621-623; roundtrip_coverage.md:64,185-187 row position authoritative vs bracket index (_apply_instrument.py:380,398; reproduced) — **Settled in #2829**: the spec and code both make the `[n]` number authoritative.
- ~~**D2**~~ med code csv_contracts.md:690-695 byte-stable vs order drift (=Dc1) — **Done in #2829.**
- ~~**D3**~~ low spec settings_inventory.md:581 only unknown top-level path ignored vs unknown session.<key> silently dropped (_apply_session.py:20-80) — **Done in #2844.**
- ~~**D4**~~ low spec settings_inventory.md:404 ?rule_based_error param absent from app/ — **Done in #2844.**
- ~~**D5**~~ med spec extract_data.md:453 no instruments selected -> every roster entry vs zero-response entities dropped (entity_metadata_extract) — **Done in #2844.**
- ~~**D6**~~ low write extract_data.md silent on include=True filtering across lenses vs responses.csv unfiltered — **Done in #2838.**
- ~~**D7**~~ low spec csv_contracts.md:50 header always first vs Responses preamble, by-instrument meta block — **Done in #2844.**
- ~~**D8**~~ low trim csv_contracts.md:100,281,3-9 "Five extracts/importers" tallies; Observers & Settings extracts no §2 entry — **Done in #2844.**
- ~~**D9**~~ med author csv_contracts.md:984-987 every extract row order pinned + tested vs data_shape_extract no order_by; by_instrument ties — **Done in #2840.**
- ~~**D10**~~ low author csv_contracts.md:452-454,973-975 collect every error vs short row rejects file (_quick_setup.py:1180-1199) — **Done in #2840.**
- ~~**D11**~~ low write no per-cell length limits documented for roster/relationship/observer CSV (=Dc4) — **Done in #2830.**
- ~~**D12**~~ med code email_template_editor.md:155-158,259-260 no-overrides indistinguishable vs import writes enabled flag (=Dc2) — **Done in #2829.**
- ~~**D13**~~ low spec email_template_editor.md:242-243 cites "✅ All" not in roundtrip_coverage — **Done in #2844.**
- ~~**D14**~~ low spec roundtrip_coverage.md:8 "proposed rehydrate" vs built, gated; link ../spec/ — **Done in #2844.**
- ~~**D15**~~ low spec roundtrip_coverage.md:138; rehydrate.md:534-536 regenerate resets include=True vs recomputes (_generate.py:566-578) — **Done in #2844.**
- ~~**D16**~~ low spec rehydrate.md:141-143 pure analyze_rehydrate_set(files) vs (db, *, files, user) reads DB — **Done in #2844.**
- ~~**D17**~~ low author rehydrate.md:129-131 preview assignments-to-generate absent; "instruments" = distinct short labels (session_rehydrate.py:354-367) — **Declined 2026-10-06 (author): Rehydrate is incomplete and not reachable, as Dc9.**
- ~~**D18**~~ med code rehydrate.md:408,423-425 two outcomes per row vs short rows vanish (=Dc3) — **Done in #2829.**
- ~~**D19**~~ med author rehydrate.md:394 InstrumentShortLabel unique per session vs no constraint; last duplicate wins (responses_import.py:229-231) — **Declined 2026-10-06 (author): Rehydrate is incomplete and not reachable, as Dc9.**
- ~~**D20**~~ low author roundtrip_coverage.md:113; settings_inventory.md:509-510,582 data-shape refs portable vs empty ref for unlabeled instrument widens scope on re-import — **Done in #2856** (ruled 2026-10-06: a `data_shapes[i].instrument` row carries the `[n]` number as the fallback ref).
- ~~**D21**~~ low trim settings_inventory.md:361,581,576,582; rehydrate.md:252-253,367-373,537-544; extract_data.md:1045-1047; email_template_editor.md:62 — **Done in #2844.**
- ~~**D22**~~ low write csv_contracts.md §3.3 required Settings fields and csv_list data_type undocumented — **Done in #2844.**
- ~~**D23**~~ low spec email_template_editor.md:223-225 cc_bcc_for raw vs stripped — **Done in #2844.**

**E — UI and visual style**

- ~~**E1**~~ med author ui_elements.md:625,644-647 chip edge 1px vs base.html:2627-2631 2px; test_chip_edge "two_pixel_edge" — **Done in #2852** (ruled 2026-10-06: the spec says 2px, the border plus an inset shadow).
- ~~**E2**~~ med spec ui_elements.md:37-40 general wins vs visual_style_rrw.md:70-83 app wins; ui_elements implements rrw — **Done in #2845.**
- ~~**E3**~~ low trim color_tokens.md:244 "nine dark tokens → --blue-glow" vs 8 — **Done in #2845.**
- ~~**E4**~~ med write operator_button_audit.md no rows for session_rehydrate.html (5 controls) — **Done in #2845.**
- ~~**E5**~~ low-med write operator_button_audit.md:406-407 sort-save-error-banner Cancel no row — **Done in #2845.**
- ~~**E6**~~ low-med write operator_button_audit.md:428-458,641-648 Band 3 X, ▲▼, Band 1 +/AND-OR/op-cycle/X no rows; §16 points to non-existent "instruments.md § Band 1" — **Done in #2845.**
- ~~**E7**~~ med code operator_button_audit.md:136,243,781; session_owners.md:193 chrome-link "reuse" — renders unstyled (=Ec8) — **Done in #2830.**
- ~~**E8**~~ low spec ui_elements.md:458; operator_button_audit.md:866-870 .tab-strip-page "chrome grey like Setup row" vs Setup row blue-pale — **Done in #2845.**
- ~~**E9**~~ low spec operator_button_audit.md:50 chrome link "defined in visual_style_rrw" vs ui_elements §1 — **Done in #2845.**
- ~~**E10**~~ low trim operator_button_audit.md:538-549,76,413 retired rows kept "because cited" — none cited — **Done in #2845.**
- ~~**E11**~~ low spec operator_ui_concept.md:75-80,113-117 URLs lack /operator prefix — **Done in #2845.**
- ~~**E12**~~ low trim tallies: ui_elements.md:570,694,274,704,949-952; operator_ui_concept.md:454-455; operator_button_audit.md:268,357 — **Done in #2845.**
- ~~**E13**~~ low trim history: ui_elements.md:203-204,271-274; visual_style_general.md:25,117; operator_button_audit.md:382 — **Done in #2845.**
- ~~**E14**~~ low-med author instruments_index.html:8-266 258-line local <style> primitives uncatalogued (save-error-banner, sort-btn/sort-badge, instrument-card-*, page-break-card*, reorder-toast) — **Done in #2857** (ruled 2026-10-06: move the block into `base.html` and catalogue it).
- ~~**E15**~~ low write uncatalogued base.html primitives (.roster-card/.unlock-*, .row-expander-*/.exp-*, .roster-readouts, .tag-mode-chip/.pill-tag-clear, .quick-setup-*, .setup-coverage-*, .severity-filter-*, .email-preview-*; email-preview-body <pre> not .code-block) — **Done in #2845.**
- ~~**E16**~~ low author visual_style_general.md:145,215; ui_elements.md:925 no drop shadows vs .instrument-reorder-toast box-shadow (instruments_index.html:257) — **Done in #2857** (ruled 2026-10-06: drop the shadow, with E14).

**F — architecture, roles and operations**

- ~~**F1**~~ med author permissions.md:33,166-167,170; architecture.md:859-861; audience_and_identity_model.md:117,141 — super-admin alone adds admins vs invite path (= Fc1) — **Done in #2828.**
- ~~**F2**~~ low spec architecture.md:24 "scheduled archive/delete partially deferred" vs nothing scheduled; retention_* inert (review_session.py:129-130) — **Done in #2846.**
- ~~**F3**~~ low spec architecture.md:231-232 require_json_object list omits _instruments.py:1133,1178 — **Done in #2846.**
- ~~**F4**~~ low spec architecture.md:842-849 session_operators row confers access vs router gate is_operator or is_sys_admin (deps.py:188) — **Done in #2846.**
- ~~**F5**~~ low trim architecture.md:72-76,201-203,214,219,230-237 provenance (R1..R7 labels, add-group retired history) — **Done in #2846.**
- ~~**F6**~~ low spec spec/README.md:26 architecture row omits route conventions, static assets, spec registration, write-path, invariants (fold) — **Done in #2846.**
- ~~**F7**~~ low spec spec/README.md:25 windows throughout/always vs not stored/not authorable (visibility_policy.md:97,103-104) — **Done in #2846.**
- ~~**F8**~~ low spec permissions.md:265-269 every op writes one event vs adopt on already-owner writes none (_sys_admin.py:272-285) — **Done in #2846.**
- ~~**F9**~~ low trim permissions.md:204 "author's ruling, 2026-09-23" — **Done in #2846.**
- ~~**F10**~~ low spec audience_and_identity_model.md:328-331 "Both audiences" vs four + admin — **Done in #2846.**
- ~~**F11**~~ low trim permissions.md:118,285,287 tallies ("seven", "four") — **Done in #2846.**
- ~~**F12**~~ low-med author operations_pages.md:167-171 (pinned test_page_guidance.py:544) "four of eight counters cannot move" vs send stamps sent_at/last_reminder_at today (invitations.py:384-390,765-768) — **Done in #2858** (ruled 2026-10-06: reword the note: recorded, not delivered).
- ~~**F13**~~ low author email_infra_options.md:588-675 ✅/◻ ticks + migration path = plan; move to segment_14B? — **Done in #2852** (ruled 2026-10-06: the spec's checklist retired; the 14B plan's `## Status` already holds it).

**G — the functional spec**

- ~~**G1**~~ med spec :684-686,1051-1053 observers_enabled gates collation vs ungated (deps.py:482-535; participant_model §2) — **Done in #2847.**
- ~~**G2**~~ med spec :1759-1763,2493-2495 boundary tags "Group by" on Display Fields vs Link 3 builder group_kind; first identity line is visible tag display values — **Done in #2847.**
- ~~**G3**~~ med spec :2264-2270,1271-1274,2467-2472 "one loss outside regeneration" vs roster re-upload, Quick Setup replace, settings replace cascades — **Done in #2847.**
- ~~**G4**~~ med spec :927-929 description on pre-open/post-close vs overview card, results, collation (pre_open.html has none) — **Done in #2847.**
- ~~**G5**~~ med author :1089-1095 clone = setup + rosters vs drops visibility policies, deadline, schedule anchors/offsets (session_clone.py:103-114) — **Done in #2859** (ruled 2026-10-06: Duplicate copies the visibility grid; the spec says the schedule resets).
- ~~**G6**~~ low spec :1353-1354 self-review toggle locked "while ready" vs all but draft/validated — **Done in #2847.**
- ~~**G7**~~ low spec :1359-1360 Include checkbox vs pill — **Done in #2847.**
- ~~**G8**~~ low spec :1741-1746 every header sortable vs Group header not — **Done in #2847.**
- ~~**G9**~~ low spec :2161-2162 CreatedAt (UTC) vs CreatedAt — **Done in #2847.**
- ~~**G10**~~ low spec :1152-1157 "Submit all", defaults locked; omits availability gate (draft, no responses) — **Done in #2847.**
- ~~**G11**~~ low spec :1486-1488 coverage "none" vs "no responses" — **Done in #2847.**
- ~~**G12**~~ low spec :1880-1881 observer gated on window like reviewee vs no window gate; while_ongoing Summarized for observers — **Done in #2847.**
- ~~**G13**~~ low write :194-208,877-879,1584-1585 empty SUPER_ADMIN_EMAILS lets any admin manage admins — **Done in #2847.**
- ~~**G14**~~ low write :202-208,1584-1585 Accounts Management omits Invite by email (incl. as admin) and revoke-refused-while-owning — **Done in #2847.**
- ~~**G15**~~ low write :1587-1590 Sessions Diagnostics visibility-grid audit unmentioned — **Done in #2847.**
- ~~**G16**~~ low write :1025-1026,1371-1376 Link 3 "Self reviews" exclude-at-rule control missing — **Done in #2847.**
- ~~**G17**~~ low trim :499-505,524-526,1040-1041,1308-1309,1355-1356,1424-1428 features described by denial (old G17 partly fixed) — **Done in #2847.**
- ~~**G18**~~ low trim :718,739-740,1666 "Pause" history + identifier (old G3 partly fixed) — **Done in #2847.**
- ~~**G19**~~ low trim same rule stated twice (217-223/252-256; 1134-1137/1173-1176/908-912; 736-740/1419-1428; branching ×4) — **Done in #2847.**
- ~~**G20**~~ low trim :12-18,2039-2086 Currency note, §11.6 "wired today" inventory — **Done in #2847.**
- ~~**G21**~~ low spec :4-10 etc identifiers in tech-neutral spec (require_reviewee_with_current_grant, _DEFAULT_DISPLAY_LABELS, …) — **Done in #2847.**
- **G22** low author :969-972 every anchor obeys ordering chain vs settings CSV import skips checks (_apply_session.py:44-58,117-150) — **Ruled 2026-10-06: the import enforces the ordering chain.**
- ~~**G23**~~ low spec :1988-1991 reminders "invited-but-incomplete" vs every incomplete with a row; never-sent falls back to invitation — **Done in #2847.**
- ~~**G24**~~ low spec :1072-1075 expander rename/deadline ungated vs draft only (tags any state) — **Done in #2847.**
- ~~**G25**~~ low spec :668-669 while_ongoing "(session lifetime)" vs status=ready — **Done in #2847.**
- ~~**G26**~~ low author :121-123,621-622 vs :2377-2381,2393-2399 audit append-only/immutable vs delete session & purge delete audit rows — **Done in #2852** (ruled 2026-10-06: the spec qualifies it — never edited, deleted only by Delete session or a Purge that takes the audit log).

**H — docs/**

- ~~**H1**~~ med doc security_posture.md:379 "one GET that writes is Session Home" vs extract GETs audit+commit (_extracts.py:84-105 …:746, _extract_data.py:345), /me/invite/{token} record_open (_invite.py:71-75), first-sign-in users row (deps.py:167-176) — **Done in #2848.**
- ~~**H2**~~ low doc/code database.md:134-136 every FK index=True vs data_shape.py:69-76,112-115 — **Done in #2837.**
- ~~**H3**~~ low doc deployment_dev.md:323 review_sessions.created_by_user_id vs table sessions — **Done in #2848.**
- ~~**H4**~~ low doc known_limitations.md:16-18 App Insights "stop applying" at cutover vs not wired (architecture.md:108-112, deployment_nus.md:129-130); same security_posture.md:441-443 — **Done in #2848.**
- ~~**H5**~~ low author security_posture.md:441-442, known_limitations.md:12-14 Postgres "private endpoint" vs nus_azure_status.md:31 "provisioned privately" (Azure-only) — **Done in #2852** (ruled 2026-10-06: both docs say privately provisioned, no public access, until the mechanism is confirmed).
- ~~**H6**~~ low doc architecture.md:106 "before the App Service swap" vs no swap (main_app…yml:118-122, deploy_nus.yml) — **Done in #2848.**
- ~~**H7**~~ low doc security_posture.md:210,237 "Result: no gaps found" (2026-05-18) vs gap closed 2026-09-07 at :239-291 — **Done in #2848.**
- ~~**H8**~~ low doc security_posture.md:218-229 destructive table omits roster delete-all (reviewers/reviewees ack; observers confirm only) — **Done in #2848.**
- ~~**H9**~~ low trim local_setup.md:72 "(auth, database…)" no auth doc — **Done in #2848.**
- ~~**H10**~~ low trim known_limitations.md:94 "all 70 pairs" tally (test floor >=70) — **Done in #2848.**
- ~~**H11**~~ low author deployment_nus.md:225-234 vs :236-241/§6.4 edit personal workflow vs separate deploy_nus.yml — **Done in #2852** (ruled 2026-10-06: §6.3 points at `deploy_nus.yml`; the approval gate moved to §9 step 9).
- ~~**H12**~~ low author database.md:99-101, local_setup.md:316-317 TEST_DATABASE_URL/DATABASE_URL no warning schema drop — **Done in #2831.**
- ~~**H13**~~ low (dated records) guide/archive/sweep_2026-10-03_corpus.md, codex_assessment_30sep.md, codebase_assessment_30sep.md/.json cite nus_azure_status_v7.md — **Left as is: dated records are history.**
- ~~**H14**~~ low doc cli_setup.md:142-145 "environment secrets" vs repo secrets; gh auth refresh -s admin:repo_hook (unverified) — **Done in #2848** (repository secrets, not environment ones; the specific `gh` scope advice is dropped, since the repo cannot confirm it).

**I — root and process documents**

- ~~**I1**~~ med doc rrw_sdd_in_practice.md:165 quotes spec-writer charter "flag drift … rather than silently rewriting" — not in spec-writer.md (now "Do not re-align", :40) — **Done in #2849.**
- ~~**I2**~~ med author new_project_practices_setup.md:153, :279-281 ci.yml verbatim + dev extras omit playwright — **Done in #2831.**
- ~~**I3**~~ low doc new_project_practices_setup.md:237-241 "around 130 dangling … five places" vs 88 measured, constitution.md:42 sixth source, CONTRIBUTING 2 refs — **Done in #2849.**
- ~~**I4**~~ low doc new_project_practices_setup.md:204-209 omits test_index_currency.py (CLAUDE.md:224) from lines-to-drop — **Done in #2849.**
- ~~**I5**~~ low doc rrw_design_rationale.md:185,225 "migrations round-tripped on both dialects" vs Postgres only (azure_ask.md is a record) — **Done in #2849.**
- ~~**I6**~~ low doc rrw_sdd_in_practice.md:163, constitution.md:50 diff-reviewer "no edit tools"/"read-only" vs Bash in tools (charter, not construction) — **Done in #2849.**
- ~~**I7**~~ low doc CLAUDE.md:213-214 hook rebuilds also when pip --version fails (session-start.sh:56-60) — **Done in #2849.**
- ~~**I8**~~ low author README.md:204-220 omits azure_ask.md — **Done in #2852** (ruled 2026-10-06: a README line; retirement stays queued).
- ~~**I9**~~ low doc rrw_sdd_in_practice.md:54-55 each folder archive/ has its own index vs docs/archive has none (rows in docs/README.md) — **Done in #2849.**
