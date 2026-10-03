# Findings — corpus sweep (2026-10-03)

**Found by:** `guide/sweep_2026-10-03_corpus.md` · **Read at:** `17986214`
(#2780) · **Open:** every row below that is not struck.

Every spec, `docs/` file and root document was read against the code it
describes, in nine verify-mode reads split by area. **Nothing in `spec/`
was edited.** A sweeper may not re-align a spec to the code
(`rrw_sdd_in_practice.md` §4), so each divergence is listed here and the
fixes ship afterwards as ordinary PRs. A row is struck when it is done,
with the PR that did it, or marked declined with the reason.

**Ids** carry the area of the read that found them, as in the previous
register: **A** instruments and the reviewer surface · **B** assignments,
workflow, lifecycle, Validate · **C** Setup, Session Home and the lobby ·
**D** data in and out · **E** UI and visual style · **F** architecture,
roles and operations · **G** the functional spec · **H** deployment and
operations docs · **I** root and process documents. They restart at 1 in
this file; an id cited from the 2026-10-01 register is written "old A6".
**Severity** is the reader's. **Decides:** *spec* means the spec is wrong
and an update in place fixes it; *code* means the code is wrong against a
spec that is right; *author* means it is a choice between fixing the code
and changing the contract; *trim* means history, provenance or a tally to
strip, keeping the reason it carried.

## 1. Code defects

Confirmed by reading the code; the ones marked *reproduced* were also run.

- ~~**C1**~~ high — **Done in #2782.** **The lobby row-expander Save wipes a draft session's
  other settings.** `_lobby.py:321-336` builds `SessionCreate(name, code,
  description, deadline, help_contact)` and `sessions.update_session`
  (`sessions.py:193-211`) writes every field it lists from that payload.
  Renaming a draft resets `scheduled_activate_at`, `invite_offsets`,
  `reminder_offsets` and `responses_release_at/until` to empty, and turns
  `relationships_enabled` / `observers_enabled` off unless their roster
  has rows. *Reproduced.* `spec/sessions_overview.md:252-262` says Save
  changes Name, Code and Deadline.
- ~~**D1**~~ med — **Done in #2783.** **A Settings CSV with a duplicate data-shape name, or two
  response fields with one `field_key` in an instrument, answers 500.**
  Phase 1 (`_apply_parse._cross_row_errors`) checks rule-set names only;
  phase 2 hits the unique constraint and `_run_quick_setup_settings`
  (`_quick_setup.py:1090`) has no handler. *Reproduced.* Breaks the
  two-phase promise in `spec/csv_contracts.md` §3.3 and §7.3.
- ~~**D2**~~ med — **Ruled 2026-10-03: case-fold in code. Done in #2793.** No backfill: a field an earlier import stored lowercase is mended by a Band 2 save or an export and re-import. A lowercase response-field `data_type`
  (`integer`) is stored verbatim with no validation, so the field is
  silently mistyped (`_apply_instrument.py:127-128, 437-442`).
  `csv_contracts.md` §4.5 says it is accepted. Case-fold in code, or
  narrow the spec (which also muddles `long_text`, a response type).
  *Reproduced.*
- ~~**B1**~~ med — **Done in #2784.** The Band 2 preview does not follow old B7. It builds
  `self_groups` from the surviving pairs (`_band1.py:1002-1009`) and
  loads active reviewees only (`:876`); Generate reads membership off the
  whole roster. When a Link rule filters the reviewer's own row, the
  preview shows a sample Generate would exclude. `spec/assignments.md`
  :334-341 is right.
- ~~**A1**~~ med — **Done in #2785.** Observer collation numbers instruments from `#0`
  (`_observer_collation.py:146` enumerates without `start=1`). Every
  other surface starts at 1. No test covers it.
- ~~**A2**~~ med — **Ruled 2026-10-03: name the instrument by its label. Done in #2794.** Each entry now starts with the instrument's status-pill label (`#2 Peer review:`, bare `#2` without a short label). The reviewer's missing-required and error cards
  say "Page N" where N is the session-wide instrument position
  (`_session_position_map`; `review_surface.html:161,191`), so with two
  instruments on page 1 the second's gap reads "Page 2". Fix the number,
  or label it `#N`. `reviewer-surface.md:174,795`.
- ~~**C2**~~ med — **Done in #2786.** The Relationships page guidance says an upload "clears
  any assignments already generated" (`session_relationships.html:122-124`);
  `save_relationships` deletes none.
- ~~**D3**~~ low — **Done in #2788.** `email_overrides.<any kind>.enabled` in a Settings CSV
  flips `responses_received_enabled` (`_apply_email.py:25-33`).
  *Reproduced* with `invitation.enabled=false`.
- ~~**C3**~~ low — **Done in #2789.** Operator Settings' sample line reads "UTC UTC" for a UTC
  operator (`operator_settings.html:123`); `timezone_display.md:107-108`
  says a bare UTC shows once.
- ~~**A4**~~ low — **Done in #2790.** `require_reviewee_with_current_grant` logs
  `"user_id": reviewee.id` (`deps.py:478`), a reviewee id.
- ~~**A5**~~ low — **Ruled 2026-10-03: refuse non-whole bounds. Done in #2792.** The defect is upstream of the reviewer surface: Band 2 refuses a fractional Integer bound, but the Settings CSV import stored it on the field while `validation` cast it to a whole number. The import now refuses it. As found: Integer placeholders and the constraint line truncate
  bounds with `int(...)` (`views/_instruments.py:187,226`);
  `reviewer-surface.md:450-454` says bounds print as entered.
- ~~**B3 = C4**~~ low — **Done in #2791.** `_require_not_archived` (`_shared.py:191-204`) says
  "cohort rule edits are not allowed" for all eight Observers routes.
- **A6 low** — Integer/Decimal shape check skips `step <= max - min`
  when `max == min` (`_band2.py:464-470`). The spec is stricter; leave it.
- **D31 low** (found while fixing D1) — Quick Setup's Settings upload
  discards `ApplyResult.errors`: `_run_quick_setup_settings` returns
  `"parse"` and the slot shows only "Could not import session
  settings." `spec/csv_contracts.md` §3.3 ("the route surfaces them")
  and §7 item 3 ("the full validation report") promise more.
- **D32 low** (found while fixing D1) — A Settings CSV data-shape name or
  `field_key` over 255 characters passes phase 1 and fails phase 2 on
  Postgres as a `DataError`, a 500 (`data_shape.py:58`,
  `instrument_field.py:51`).
- **B35 low spec** (found while fixing B21) — `lifecycle.md` §8.2.3
  keeps Auto-archive (`not_draft`) and Auto-delete (`not_archived`)
  skip rows, but those columns have no consumer (`lifecycle.md:622-623`)
  and no `…_skipped` event exists for either; the codes are only the
  manual routes' errors. Trim them as B21 did, or keep them as the
  deferred design.
- ~~**D33**~~ med (found while fixing D13) — **Done in #2801.** No Extract
  download committed its audit row: `audit.write_event` only flushes and
  `get_db` closes without committing, and none of the 12 older routes in
  `_extracts.py` committed, so every `session.*_extracted` row rolled
  back in production. The SAVEPOINT test fixture hid it; a real-commit
  test now covers eleven of them (the sys-admin audit log is the one
  left out).
- **Stale code comments and dead code.** `_assignments.py:410-420`
  (generate docstring) and the `missing_confirm` banner naming a form
  that does not exist (B2); `session_lifecycle.py:1-6, 54-55, 333, 659,
  970` and `next_action_card.html:35` (B4, G); `_surface/_status.py:23-24`
  (A10); `views/_extract_data.py:12-14`, `routes_operator/_extract_data.py:1-8`,
  `session_extract_data.html:262-286`, `_serialize.py:44-62, 554-565`,
  the test-only `compute_self_review_data_state`, and the unread
  `DEBUG` / `APP_NAME` settings (D5); `import-config`'s unread
  `?config_imported=ok` (C5); `base.html:2801, 3852, 5179` (the last cites
  a missing `spec/assumptions.md`) and the hover underline on the <!-- path-ref-ok -->
  `.chrome-app-identity` span at `:513` (E); dead CSS with no markup —
  `.field-builder*`, `.display-edit`, `.instrument-edit`,
  `.description-text`, `.help-preview`, the `.page-grid` placement
  classes, `.btn-icon.danger/.action`, `.order-cell/.order-arrows`,
  `.pill-handle`, `.form-error`, `.card.disabled`, `.quick-setup-divider`,
  `.rule-edit-row`, `.btn.alert-solid` (E1–E4); test comments citing
  `rrw_functional_spec.md:1114` (G); `test_monitoring_prefetch.py:387-395`
  (F25).

## 2. Rulings needed

The author's calls. Where the spec is stricter than the code it is left
stricter until ruled on.

**Behavior that reaches people.**
- ~~**A2**~~ (above; ruled 2026-10-03, done in #2794): "Page N" or "#N" on the reviewer's missing-answer cards.
- ~~**A3**~~ — **Ruled 2026-10-03: hide them. Done in #2798.** The observer collation rendered `visible=False` response fields
  (`_observer_collation.py:189`, `collation.py:87`); every other surface
  hides them, and `instruments.md:1040-1045` never names observers.
- ~~**A18**~~ — **Ruled 2026-10-03: follow the spec. Done in #2798**, on the results page and the observer collation alike. String summarize at zero responses showed "Total length: 0
  characters" (`results.html:81`), not the em-dash
  `participant_model.md:82` and `visibility_policy.md:65` ask for.
- ~~**B18**~~ — **Ruled 2026-10-03: update the spec. Done in #2797.** `lifecycle.md:321` promised an "auto-closed at X" pill from
  `deadline_closed_at`; nothing renders one.
- ~~**G7**~~ — **Ruled 2026-10-03: mark it. Done in #2799**, a "Self review" pill after the name. `rrw_functional_spec.md` §10.3 says the reviewer surface marks
  a self-review row; nothing did.
- ~~**G5**~~ — **Ruled 2026-10-03: config-only. Done in #2797.** The session self-reviews-active flag has no editor; only the
  Settings CSV and Duplicate set it. Build one, or say it is config-only
  (also `settings_inventory.md:104`).
- ~~**D2**~~ (above; ruled 2026-10-03, done in #2793) and ~~**D6**~~ (ruled 2026-10-03: follow the code; done in #2797, the message now says the responses-received email omits the line): `email_template.no_help_contact` said emails
  fall back to a placeholder; the editor spec and the defaults drop the
  line.
- ~~**D13**~~ — **Ruled 2026-10-03: zip every data-shaped response. Done in #2800**, `GET /export/data_shapes_bundle.zip`. The Data shaper's outer Zip all was an inert placeholder in
  code and spec, while the intro card's Zip all already bundles every
  saved shape. Remove the button or specify it.

**Routes and controls with no contract.**
- ~~**B7**~~ — **Ruled 2026-10-03: retire. Done in #2801**; the audit key stays registered so old rows filter. `POST /assignments/delete-all` existed with gates but no page
  posts to it and `assignments.md` says assignments are never deleted.
- ~~**A16**~~ — **Ruled 2026-10-03: retire. Done in #2801**; Recall, which is live, joins the spec's route list. The inert consolidated `POST /me/sessions/{id}/save`.
- ~~**A22**~~ — **Ruled 2026-10-03: retire. Done in #2801**; tests use an `add_group_instrument` helper. `POST /instruments/add-group`, a fixture back door.
- ~~**B15**~~ — **Ruled 2026-10-03: retire. Done in #2801**, with `needs_regeneration_after_revert`, its only input. `is_pre_generate`, kept "for external consumers", had only a
  test consumer and costs queries per render.
- ~~**B21**~~ — **Ruled 2026-10-03: retire. Done in #2801**: the rows go, and a note says the window is read-time. Release-from/until preconditions and skip reasons in
  `lifecycle.md:729-730` that nothing emits.
- ~~**B11, B13, A25, C16, F4**~~ — **Ruled 2026-10-03: fix as recommended. Done in #2801**: B13 (Generate copies an answered group's answer onto a new member), B11 (Clear shows for a status filter), C16 (identity and Profile labels are literals on Reviewees too), F4 (308) and A25 (an archived session's page says it has closed). Clear's visibility with a status filter; a
  new member of an answered group gets no answer copy on Generate; the
  pre-open page also serving `archived`; identity labels through the
  resolver; `/monitoring`'s 303 against the 308 house rule.

**Spec contracts the tree no longer meets.**
- **E3, E4, E14**: retire the dead `.btn-icon` modifiers, unrendered
  classes and three consumerless tokens (`--text-on-amber`, `--space-12`,
  `--space-16`), or keep them on purpose.
- ~~**E9, E18**~~, **E19**, ~~**E23, E16**~~ — **Ruled 2026-10-03: update the spec. Done in #2806** (E19's underline goes with the dead-code deletion): `error.html`'s raw-hex palette; no H1 on
  the Create page; the app-identity span; 1px vs 2px borders; the
  `#667080` counterfactual.
- ~~**D9, D11**~~, **D23** — **Ruled 2026-10-03: update the spec.** D9 and D11 (the posture stated; phase 2's wipe names the assignments and responses) **done in #2806**; D23 goes with the dead-code deletion: the golden-fixture claim for Settings CSV order;
  formula-injection posture for extracts; `DEBUG` / `APP_NAME` unread and
  `APP_ENV` called informational though it gates boot.
- ~~**H10**~~ — **Ruled 2026-10-03: update the docs. Done in #2806**: provisioned, earmarked for 18Q, unused. one stated purpose for the storage account (diagnostics only,
  or the planned blob store).
- ~~**I12**~~ — **Ruled 2026-10-03. Done in #2806.** README.md says a group instrument needs a pinned rule before it
  can open; nothing in code or spec says so.
- ~~**I18**~~ — **Ruled 2026-10-03. Done in #2806**: five §6 decisions plus §6.3's trade-off make the six articles. "six decisions" of `rrw_sdd_in_practice.md` §6 against seven
  headings.

**Old findings reopened.**
- ~~**H-retire (old H21, H24)**~~ — **Ruled 2026-10-03: retire. Done in #2796**, moved to `docs/archive/` with `docs/README.md` rows, as `archive/quickstart.md` was. `docs/azure_provision.md` and <!-- path-ref-ok -->
  `docs/azure_github_setup.md` were bannered "Superseded" (c74bc155), not <!-- path-ref-ok -->
  retired; the old register's "Done in #2738" overstates. Inbound
  references to repoint first: `docs/README.md:27-29`,
  `docs/architecture.md:83,128,135`, `docs/cli_setup.md:3,648`,
  `docs/deployment_nus.md:16-17`, `spec/rehydrate.md:185`,
  `guide/segment_20_operator_polish_and_documentation.md:53`,
  `guide/todo_master.md:2070`. `guide/post_azure_todo_checklist.md:101`
  still queues the question. Retire, or record "kept as the estimate
  record".
- **I5**: `docs/status.md` has no timeline row for #2720–#2780 (this
  sweep's row is the first since #2718).
- ~~**I7, H23**~~ — **Ruled 2026-10-03: update the documents. Done in #2796.** `known_limitations.md` does not say scheduled sends fire
  only on a Session Home visit (old B19); the backup, runbook and
  troubleshooting docs have no NUS coverage until cutover.

## 3. Findings by file

**A — instruments and the reviewer surface**

- `reviewer-surface.md`:
  - A7 low-med spec · :744-745 (and `instruments.md:938`): group identity is "boundary tag values"; code composes it from the visible `reviewee.tag_*` display fields, the boundary key only as fallback (`_group_collapse.py:46-68`, preview `tagPills`).
  - A8 low spec · :326: per-page "not started" is `.pill-info`, not `.pill-empty` (`_progress.py:36`).
  - A9 low spec · :331-333: pill label is `#N label`, the heading `#N: label` (`_context.py:609`); :1447 is right.
  - A10 low spec · :356-359: preview does pass `page_statuses` (`_context.py:600-618`), as :992-993 says.
  - A11 low-med spec · :1203-1204: summary `<h2>` is the instrument heading, never `Instrument.name` (`_reviewer_summary.py:438-445`); conflicts with :1454-1456.
  - A12 low spec · :170-171: every instrument on the page renders, not exactly one.
  - A13 low spec · :690-714, :1561-1562: the view shape is incomplete (`InstrumentHeading`, `placeholder`, `sort_values`, group fields).
  - A14 low spec · :150-151, 236, 308: Submit stamps Response rows only (`_core.py:805-815`); :289-290 is right.
  - A15 low spec · :271-273, 283-284: Save filters by the page's instruments' assignments, not "by position" (`_routes.py:210-218`).
  - A16 author · :39-46: route list omits the inert `POST …/save` and `recall`.
  - A23 low write: the header's "Questions? Contact {help_contact}" (`review_surface.html:85`).
  - A24 low write · :889-901: `observe_deadline` also reopens instruments closed before the deadline.
  - A25 author · :828-837: the pre-open page also serves `archived`.
  - trim: :885, 927, 968-980, 1000, 1005-1012, 1175, the viewport measurements at :1085, and "Segment 17B owns these" at :1480-1546.
- `instruments.md`:
  - A20 low spec · :1561-1565: "may share" a `SessionRuleSet` on delete; Replicate now clones it.
  - A21 low-med write: the expanded card's top button row (`instruments_index.html:786-817`).
  - A22 author: `add-group` route (above).
  - trim: :102, 120-125, 149, 359, 425-432, 884, 947-948, 1017, 1085, 1411-1415, 1513-1537, 1615, and the scattered `(19T Item N)` tags.
- `participant_model.md`: A17 low spec · :94: the surface renders `pre_open.html` (200), not 403/redirect. A18 author (above).
- `visibility_policy.md`: A19 low spec · :202: `peer_reviewer` defaults to Raw while ongoing with no row. trim :78, 124, 133-135, 198, 202.
- `sort_by_reviewee.md`: matches the code. trim :31, 41, 95, 126, 156, 226-232, 327.

**B — assignments, workflow, lifecycle, Validate**

- `assignments.md`:
  - B5 med spec · :603-606, 771-778: the Self-review toggle reads the `is_self_review` column through `_active_self_review_rows` (`_self_review.py:486, 540`); it loads no rows and does not call the group helper.
  - B6 low spec · :1246-1248 (and `validate_page.md:271`): `assignments.instrument_empty` is multi-instrument only and skipped before the first Generate.
  - B7 author: delete-all route (above).
  - B8 low spec · :1093 (and `workflow_card.md:944`): Generate's `confirm_replace` gate and `?needs_confirm=1`.
  - B9 low spec · :258-259: a rule row materializes only when `rules_json` is non-empty, not in "group mode".
  - B10 low spec · :1254-1292: the worked example contradicts itself.
  - B11, B13 author (above).
  - B12 trim: :72-73, 383-390, 494-495, 694-702, 719-727, 753, 1030-1036, 1123-1125, and the findings and ruling citations.
- `workflow_card.md`:
  - B14 low spec · :344, 349-360: Archive ships `.btn.danger-solid` (Alert); "Pri/Sec/Dgr" is pre-19B vocabulary; the banner Cancel is `.btn.alert`.
  - B15 author (above).
  - B16 low spec · :875: `expired` / `archived` with no invitations get the draft Prepare copy.
  - B17 trim: :26-27, 203-206, 224, 362-374, 387-396, 611-619, 642-649, 976-977.
- `lifecycle.md`:
  - B18 author (above).
  - B19 low spec · :858-862: skipped activation shows a Workflow-card signal line, not a Session Home banner.
  - B20 low spec · :863-866: event names are `session.scheduled_invites_fired`, `scheduled_reminders_fired`, `responses_purged`, `rosters_purged`, `audit_log_purged`.
  - B21 author (above).
  - B22 low spec · :724: scheduled activation also skips on `has_errors` / `needs_acknowledge` and acknowledges warnings itself (`_activation.py:95-110`), against §2.4.
  - B23 low spec · :230: "~24 route sites" (29); drop the tally.
  - B24 low spec · :488, 543: the selected count is bare text, not a pill.
  - B25 low write · §3.2: `_require_selected_response_loss_ack` (`_shared.py:283-306`).
  - B26 low spec · :569: "Audit events (full list)" omits the `session.scheduled_*` family, `activation_scheduled`, `scheduled_event_failed`.
  - B27 known: :803-814, the sweep only on Session Home (old B19, carried).
  - B28 trim: :244-247, 287-290, 325-326, 725.
- `validate_page.md`:
  - B29 med-low spec · :270: `reviewer_missing_for_instrument` flags every active reviewer with no row on an instrument that has one, as `assignments.md:1239-1245` says.
  - B30 low spec · :154-161: chip labels are "All issues (N)", "Errors only (N)", "Warnings only (N)", "Info (N)".
  - B31 low spec · :260, 424-429: `unreachable_for_results` anchors `#reviewee-row-{id}`.
  - B32 low write: the preconditions of `no_visible_response_fields` and `no_display_fields`.
  - B33 trim: :39, 122-123, 131-141, 145, 235, 261, 274, 464-468.
- `reconciling_regeneration.md`: B34 low spec · :147-149: Prepare also runs Invite.

**C — Setup, Session Home and the lobby**

- `setup_pages.md`:
  - C6 med spec · :1179-1183: the button-state table's Add column and 0-row rows; `Add new` is a toolbar link and the expander renders only with a selection (`session_reviewers.html:792-816, 1194-1218`); contradicts :766-768.
  - C7 med retire · :1010-1014: a stale "capped at 200 (500 filtered)" paragraph inside delete-all; contradicts :486-547.
  - C16 author: identity labels via the resolver.
  - C21 low write · :24-33: the Relationships page 404s unless `relationships_enabled` (`_shared.py:223-236`).
  - C22 low write · :1656-1657: the Observers CSV's optional `CohortRule` column.
  - trim: pervasive provenance (:33, 85, 186, 239, 291-296, 720-721, 876-877, 1049-1051, 1209-1212, 1288, 1321, 1330, 1341-1345, 1376, 1438, 1552), the 821px measurement, and the tallies at :21, 471, 1506.
- `quick_setup_card_spec.md`:
  - C8 low spec · :46: the Settings CSV is the 3-column form.
  - C9 low spec · :120: the helpers check `lifecycle.is_editable` inline.
  - C10 low spec · :29, 31, 124-128: the new-session variant always renders Observers.
  - trim: :33, 51, 69, 71, 75, 85, 94, 132, 138-139, 143.
- `session_home.md`:
  - C11 low spec · :558-562: `is_setup_empty` uses `has_unconfigured`, not the assignment count.
  - C15 low spec · :67, 352-354: plain labels; Description sits in the left column.
  - C18 low spec · :134, 205: quoted `workflow_card.md` headings.
  - trim: :126, 138-143, 190, 205, 372-376, 386, 492-494.
- `sessions_overview.md`:
  - C1 code (above).
  - C12 low spec · :409: the heading is "Cohort match rule editor".
  - C13 low spec · :229: "expired (labelled Closed)", not "closed".
  - C20 med write: the archived-sessions page (`sessions_archived.html`, `_lobby.py:44-47`).
  - C23 low write: point at the Purge and archive eligibility in `lifecycle.md` and `extract_data.md`.
  - trim: :265-266, 281, 403, 415-419, 433-435.
- `timezone_display.md`: C14 low spec · :102-105: only Settings has a live preview. C3 code (above). trim :116-119.
- `preview_hub.md`: consolidate — the file is retirement narrative around two 308s; move the contract into `operations_pages.md` and keep a stub (`spec_registry.py:108,119`).
- `session_owners.md`: C17 low spec · :217-218: the `self_only` refusal is pinned in `test_session_owners.py`.
- `spec/README.md`: C19 low spec · :41: the session_home row lists Extract Setup as a Home card and omits Owners.

**D — data in and out**

- `csv_contracts.md`:
  - D1, D2 code (above).
  - D7 med spec · §6 :911-928: no Responses tile; `responses.csv` only via the bundle; Observers tile, Quick Setup Observers slot and Observers upload missing; the Spec column points at `guide/archive/`.
  - D8 med-low spec · §3.1 :292-294: Setup pages re-render at 400; only Quick Setup 303s.
  - D9 author · §4.2 :704-706: the "golden-fixture" test checks only determinism and the first three sections.
  - D10 low spec: "no import counterpart" for responses (:153-157, 680; also `settings_inventory.md:552-553, 602`, `rehydrate.md:59`); "two roster importers" omits observers (:25-26); §10 described as a five-extract table (:34-35); wide vs long (:167-169, 235); the audit CSV route and its filters (:195).
  - D11 low write: §3.3 phase 2 deletes all instruments, assignments and responses (`_apply_instrument.py:293-334`); author on formula injection.
  - D12 trim: :212-227 (repoint `rrw_functional_spec.md:2151, 2158` first), 349, 373, 401, 474-486, 518, 538-550, 559, 577-587, 603, 626-664, 775, 947; tallies :488, 497.
- `extract_data.md`:
  - D13 author (above).
  - D14 low spec: "three regions" lists four (:90); `discrete_step_values` lives in `data_shape_extract.py:210` (:618-619, reopens old D12); Integer step defaults to 1 (:665); text buttons, not icons (:923, 967, 982, 999); POST returns 201 with the row (:933); three sync functions (:1178-1182); by-instrument rows are reviewer × group with fields as columns (:321-324).
  - D15 low consolidate: the Extract Setup card contract (:1131-1163) is also in `session_home.md:213-260`.
  - D16 trim: :63, 101, 220, 226-229, 241, 308, 1098-1100.
- `roundtrip_coverage.md`: D17 low spec · :23-24: there is no column-width localStorage. trim :62, 95, 119, 162.
- `rehydrate.md`:
  - D18 med spec · :205-207: reviewer and reviewee headers end in `Status`; the analyzer checks fewer headers than "must match" claims (:143-145, 203, 222-228).
  - D19 carried (old D16/D18); `guide/deferred_consolidated.md:841` says three routes (four).
  - D20 low spec: the importer exists (:59); the rename reason (:318-320); no Alert tint (:104-115); `replace_assignments` (:363).
  - D4 deferred: `responses_import._stage` overwrites duplicate rows.
  - D21 trim: :9-11, 353-359, 519.
- `settings_inventory.md`:
  - D22 med spec · :600: unknown attributes are rejected for every `instruments[]` sub-structure, `view_policies[]`, `session_tags[]`, `data_shapes[]` and `email_overrides`, not only rule sets.
  - D23 author (above) · :425, 428.
  - D24 low spec: the Email Template body (:216-219); no Danger sub-card (:248-249); Rehydrate unpacks ZIPs (:607-612).
  - D25 low write: `users.is_operator` / `is_sys_admin`, the "Clear all settings" card, `sessions.activated_at`.
  - D26 low consolidate: the precedence block (:555-586) restates `csv_contracts.md`.
  - D27 trim: :52, 147-162, 219, 356, 405-406, 490, 557-558, 563, 582.
- `email_template_editor.md`: D28 low spec: the enabled row exports lowercase `true` (:250); Relationships and Observers tabs are toggled (:23-24); the "(17)" tally (:291, old D27 partial). D29 low write: the composer's From and To rows. D30 trim :201, 232. D3, D6 (above).

**E — UI and visual style**

- `ui_elements.md`:
  - E1 med retire · :598-603, 704 (and `visual_style_rrw.md:105`): `.display-edit`, `.instrument-edit`, `.field-builder`, `.locked` have no markup.
  - E2 low-med spec · :699, 1024: the `.page-grid` placement classes and the L-shape claim.
  - E3, E4 author (above).
  - E5 low spec · :519: `.col-shrink` is on the Timezone and select-all columns.
  - E6 low spec · :111-114: the strips set their background directly; `--tab-marker-color` is unused.
  - E7 low spec · :116-121: the triangle rests at `--border-default`.
  - E8 low spec · :29-30: an ambiguous "here".
  - E9 author · :9: `error.html` is standalone.
  - E10 med-low trim · :578-581, 594: the grep recipe and form-help counts (reopens old E9/E35).
  - E11 med-low trim: :129, 190, 258-264, 278, 291, 430-433, 439-441, 450, 722-740, 836-856, 917-921, 949-950 (reopens old E9).
  - E12 low consolidate · :988-1027: "Cross-cutting rules" repeats §4, §6 and §10.
  - E13 low: the `.session-row-selected` row is one 6,000-character cell; restructure as a list, keeping the 6px rail text a test reads.
  - write: `.card-columns`, `.pill-role-*`, the skip link and `main#main-content`.
- `color_tokens.md`: tables and ratios match exactly. E14 author (above). E15 trim :454-456. E16 author :216.
- `visual_style_rrw.md`:
  - E17 med spec · :268-269, 273: Operations pages carry no lock card (P4); the roster lock card covers ready, expired and archived.
  - E18, E19 author (above).
  - E20 low spec · :316-323, 389-394: the user menu has Guide, Admin and the tier suffix.
  - E21 trim: :65, 71, 97, 98, 103, 253, 277, 709-713, 754, 812.
- `visual_style_general.md`: E22 low-med write · :141, 157: override rows for the Home anchor and the tab hover. E23 author :217. E24 trim :88.
- `operator_ui_concept.md`:
  - E25 med-low spec · :240: the breadcrumb is "New session".
  - E26 low-med spec · :182: the Home anchor reads "Session Home"; the name is a tooltip.
  - E27 low spec · :154: no Extract Data card on Home.
  - E28 low spec: Observers in the status row (:187); the lobby and archived pages adopt the sort (:95); Regenerate & prepare (:236).
  - E29 trim: :63, 93, 103, 119, 236, 242, 262-263, 391.
- `operator_button_audit.md`: every row matches its control.
  - E30 med write: about 20 controls with no row — the roster Unlock/Lock toggle on Reviewers, Reviewees and Relationships; Instruments' Expand/Collapse all, the header mirror of Lock/Save/Cancel/Unlock, the two banner Cancels, the page-break `×`, Refresh sample, the response-field `+` and `↰` / `↳`; the Sys Admin tabs; the Diagnostics and Outbox back links; the audit log's "Older events →".
  - E31 low spec · :289, 315, 342, 415: the lock card also renders when closed.
  - E32 low spec · #100, #101: Settings and About hide on their own page.
  - E33 low spec · :794-796, #120: the `.btn-pair` margins are an inline style.
  - E34 trim (reopens old E35).

**F — architecture, roles and operations**

- `architecture.md`:
  - F1 med spec · :274-277, 363-368, 373-375 (and `visual_style_rrw.md:127`): a Session status card and the shipped action row, not "All Instrument Status" and per-instrument toggles.
  - F2 med spec · :453: magic links are deferred under `audience_and_identity_model.md:338`, not "Segment 16A" (reopens old F11).
  - F3 low-med spec · :716-717, 773 (and `lifecycle.md:574`): `setup_mutation` is never emitted; `operator_revert` rides `session.invalidated` only (reopens old F5).
  - F4 author (above).
  - F5 low spec · :402-410: revert also accepts expired → draft.
  - F6 low spec · :377-380: the deferred list is stale.
  - F7 trim: :98-99, 118, 130-137, 682; `_field_refs.py` is also imported by `_instrument_crud.py` (:95-96).
- `permissions.md`:
  - F8 low-med spec · :72, 77-87: two gates live in `_shared.py`; `require_reviewee_with_current_grant` is missing from §2.
  - F9 low spec · :98-100: `/me/invite/{token}` also 404s for an inactive reviewer.
  - F10 low spec · :115: the matrix omits `recall` and `summary.csv`.
  - F11 low trim · :113, 277-283: tallies (reopens old F10).
  - F12 low spec · :260: `remove_from_all_sessions` with no sessions writes no event.
- `audience_and_identity_model.md`: F13 med spec · :421-423: participant chrome does render a Guide link (`_top_bar.html:41-46`). F14 low spec: promote/demote falls back to any admin; point at `permissions.md:167-172`. F15 trim :44, 287, 339.
- `role_navigator.md`: F16 low-med spec · :130: the partial branches on chip state, not role. F17 low spec · :112-115: the `body.ui-v2` scope. F18 trim :70.
- `domain_assumptions.md`: F19 low retire/restate · :45-47. F20 low spec · :72-74: the heading is "5a. Banner behaviour conventions".
- `operations_pages.md`:
  - F21 low spec · :75: no "five-stage stepper".
  - F22 low-med move · :113, 302-308, 514-516, 632-636: measurements and the rejected rename (reopens old F20).
  - F23 trim: provenance throughout.
  - F24 low spec · :136-141: Send invites' conditions.
- `email_infra_options.md`: F26 med-low spec · :158-159: CC/BCC only, no reply-to (reopens old F22). F27 low spec · :336-341: `smtp_transport`. F28 trim.
- `blob_storage.md`: clean; `app/services/blob_store.py` is a planned path, escaped and correct. <!-- path-ref-ok -->
- `role_landing_and_visibility.md`: clean.
- `spec/README.md`: F29 low spec · :20: the functional-spec row's "last swept" date, against the file's own rule.

**G — the functional spec** (`rrw_functional_spec.md`)

- G1 med spec · :1396-1399 §9.8: the setup checklist renders in every draft state; States 7–10 have no detail block.
- G2 med spec · :1504, 2084, 2111: the Relationships tile and CSV are not gated on `relationships_enabled`.
- G3 med retire · :242-243, 728-733, 1417-1419: no operator copy says "Pause the session"; five other specs use the word, not six.
- G4 med spec · :539-543, 1250-1251: inactive people keep their pairs, `include=False` (old B2).
- G5 author (above).
- G6 known · :964-966: scheduled sends fire only on Session Home (old B19, carried).
- G7 author (above).
- G8 low-med spec · :668-671: the reviewer's own view has a fixed Raw baseline while ongoing.
- G9 low spec · :1304-1308: the per-cell valid modes; point at `visibility_policy.md`.
- G10 low-med spec · :522-524: the per-instrument display-field label override is retired.
- G11 low spec · :1004: tag labels do not reach the schedule timeline.
- G12 low write · :1642: the dashboard's "View responses" and "Until" columns have no owning spec.
- G13 low write · :1100-1115: the Create form carries the Quick Setup card.
- G14 low spec · :2539-2578: §19 omits `session_owners.md`.
- G15 low retire · :2146-2158: the §12.4 and §12.5 stubs (keep the numbering or fix the `#127` anchor).
- G16 low trim: tallies at :731, 1195, 1221, 1384, 1438.
- G17 low trim: absent features described by denial (:590-593, 1273-1280, 1331, 1569); keep the Previews 308 at :1495.
- G18 low write · :2258-2259, 2455: relationship moves delete group copies without acknowledgement (B34 ruling).
- G19 low spec: the invitation row's email (:1889); one per-template switch (:984); plain chrome links (:1574); Observers round-trip too (:2170).

**H — deployment and operations docs**

- H-retire (above), and H14 low-med: `deployment_nus.md:15-19` and `docs/README.md:28` still present the superseded runbooks as live.
- `security_posture.md`:
  - H1 med doc · :222: no `activate_confirm`; Activate takes `acknowledge_warnings`, Revert `confirm`.
  - H4 med doc · :441-447: scope the deferred-hardening table to the dev slot; NUS has private endpoints and App Insights.
  - H5 low-med doc/author · :185-210: the §5.6 audit omits `/about`, `/guide` and `/templates/*.zip`.
  - H6 low · :177-180: state the not-identity marker rule, not a tally of 14.
  - H7 low · :11: seven gates under "three layers".
  - H8 low · :6: trim the lineage note.
- `docs/architecture.md`:
  - H9 med-low doc · :105-107: the app logs JSON to stdout; nothing streams to Azure Monitor yet.
  - H10 author: the storage account's purpose.
  - H11 low doc · :92-94: `audit_events` rows are deleted on session delete and purge.
- `deployment_nus.md`:
  - H12 med-low doc · :87-90, 180-196, 273-283: the whole `deploy_nus.yml` moves in-VNet per v7.
  - H13 low-med consolidate · :116-134: reduce §3 to a pointer to v7.
- `cli_setup.md`: H15 low-med doc: reframe around `deployment_nus.md`, `NUS_*` secrets and no NPRD names. (#2796 repointed its companion line and closing pointer when its parent retired; the body's "Phase N" references to the retired runbook remain.)
- `azure_github_setup.md` / `azure_provision.md`: H16 author (two contradictory banners), H17 and H18 moot once retired.
- `local_setup.md`: H2 low-med (drop the ~35s figure), H3 low (`node` in the tool tables), H19 low (without fake auth every route 401s).
- `deployment_dev.md`: H20 low (repoint the env-var rules to `lifecycle.md` §2), H22 low (no Oryx build).
- `database.md`: H21 low (drop "all 21 tables").
- H23 author (above).

**I — root and process documents**

- `docs/status.md`, the weakest file:
  - I1 med doc · :775-808: describes the retired Assignments UI.
  - I2 med doc · :711-726, 1021-1025: the default instrument seeds Name and Email only; nine display-field sources.
  - I3 med doc · :594-684: segment-era UI bullets, including the dead `operator/partials/_placeholder_card.html`.
  - I4 med doc · :736-748: Rehydrate ships off.
  - I5 (above).
  - I6 low · :1031: `+Instrument`.
  - I8 low · :690, 943: drop the tallies.
- `README.md`: I9 low (308, not 301), I10 low (`{code}_setup.zip`), I11 low (the Assignments table and bulk actions), I12 author (above).
- `CLAUDE.md` / `AGENTS.md`: I13 low (`get_current_user` is defined in `app/auth/identity.py`), I14 low (nothing enforces the inline-button migration; narrow the sentence or list it in `docs/unenforced_conventions.md`).
- `CONTRIBUTING.md`: I15 low (CI takes about 2 min 42 s).
- `docs/unenforced_conventions.md`: I16 low (drop "three times").
- `rrw_sdd_in_practice.md`: I17 low (undated tree measurements read as present; spec-writer is read-only by charter, not by construction). I18 author (above).
- `docs/known_limitations.md`: I7 (above).
- `azure_ask.md`: I19 low (Session Home GET writes); its retirement stays queued in `guide/post_azure_todo_checklist.md`.
- Clean: `new_project_practices_setup.md`, `rrw_design_rationale.md`, `constitution.md` (I18 wording aside), `docs/README.md`, and the dated records.
