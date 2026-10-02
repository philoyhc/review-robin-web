# Findings — corpus sweep (2026-10-01)

**Found by:** `guide/sweep_2026-10-01_corpus.md` (`guide/post_assessment_1oct.md`
E3) · **Read at:** `68f28224` · **Open:** every row below that is not struck.

Every spec, `docs/` file and root document was read against the code it
describes, in nine verify-mode reads split by area. **Nothing in `spec/`
was edited.** A sweeper may not re-align a spec to the code
(`rrw_sdd_in_practice.md` §4), so each divergence is listed here and the
fixes ship afterwards as ordinary PRs. A row is struck when it is done,
with the PR that did it, or marked declined with the reason.

**Ids** carry the area of the read that found them: **A** instruments and
the reviewer surface · **B** assignments, workflow, lifecycle, Validate ·
**C** Setup, Session Home and the lobby · **D** data in and out · **E** UI
and visual style · **F** architecture, roles and operations · **G** the
functional spec · **H** deployment and operations docs · **I** root and
process documents. **Severity** is the reader's, re-checked here for the
code defects. **Decides:** *spec* means the spec is wrong and an
update-in-place fixes it; *code* means the code is wrong against a spec
that is right; *author* means it is a choice between fixing the code and
changing the contract deliberately.

## 1. Rulings needed

These are the author's calls. Where the spec is stricter than the code it
is left stricter until ruled on. Grouped by what the ruling is about.

**The code may be wrong, and the effect reaches people.**

- ~~**C18 = D25**~~ — **Ruled 2026-10-01: follow the session zone. Done
  in #2720.** Email `$deadline` and `$submitted_at` rendered in UTC
  (`format_datetime` with no zone), so a Singapore session's 17:00
  deadline was sent as 09:00. They now resolve the session's zone, and
  `spec/email_template_editor.md` says so.
- **B19** — **Ruled 2026-10-01: incomplete work awaiting Azure**, carried
  as `guide/post_azure_todo_checklist.md` item 7. Scheduled activation, invites and reminders fire only when
  someone opens Session Home. `observe_scheduled_events` has one caller.
  `spec/lifecycle.md` §8.3 says Session Home, the Operations pages and the
  lobby, and the function's own docstring repeats that.
- ~~**A6**~~ — **Ruled 2026-10-01: remove per-instrument Open / Close.
  Done in #2722.** Accepting is session-wide, so the session-wide write
  gate is right and the spec now says so. It was: closing one instrument
  403'd Save, Submit and Clear on the instruments still open.
- ~~**A5**~~ — **Ruled 2026-10-01: fix the code. Done in #2723.** When no instrument accepts, Prev and Next disappear with the
  action row, so a reviewer can't page through a closed multi-page
  surface. The spec keeps them.
- ~~**G10**~~ — **Ruled 2026-10-01: the visibility policy decides, and nothing
  is visible once the session is archived. Done in #2723**, on the surface, the
  summary and its CSV. `responses_visible_when_closed` has no operator control and
  defaults to False, so after close a reviewer cannot see their own saved
  answers. The specs say a visibility policy governs it, and nothing
  reads one there.
- **C7 = G7** — On Session Home, Delete data and Delete session render as
  live in `expired` and `archived`, but the route answers 409.
  `spec/setup_pages.md` names exactly this predicate error.
- ~~**D14**~~ — **Ruled 2026-10-02: follow the spec. Done in #2744.**
  `clone_session` (the lobby's Duplicate) copied
  `Reviewee.results_acknowledged_at` into the new draft session; the
  specs say it is not cloned, and now it is not.
- ~~**C3**~~ — **Ruled 2026-10-02: gate it on the server and name the
  loss.** A Quick Setup settings replace deleted instruments, assignments
  and responses behind a UI-only checkbox, and the spec said it had no
  cascade.
- ~~**B16**~~ — **Ruled 2026-10-02: the Delete Data tick is the
  acknowledgement.** `POST /delete-data` took `confirm` only, not the
  response-loss acknowledgement `spec/lifecycle.md` listed for it.

**A contract the code never built.** Is it deferred or dropped? Either way
the spec should say so.

- ~~**A18 = G11**~~ — **Ruled 2026-10-02: the reviewer's cells are Raw or
  off.** `summarized` retired; #2723 made Raw read and off hide.
- ~~**A19**~~ — **Ruled 2026-10-02: retire `observer_tag`.** Nothing read
  it; an observer's cohort rule decides who they see. Instrument scoping
  inside the cohort rule is deferred (`guide/deferred_consolidated.md`).
- **F11** — The configurable welcome message, institution name and magic
  links (`spec/audience_and_identity_model.md`).
- **F15** — The Draft/Receiving/Closed instrument statuses and the
  reviewer notification on edit (`spec/domain_assumptions.md`). The A6
  ruling (#2722, accepting is session-wide) rules out a per-instrument
  Closed/Paused state, so this now reads as "won't do" unless the author
  says otherwise.
- **G4** — The Responses-received switch has no consumer at submit time.
- **G13** — Export validation at row-write time
  (`spec/rrw_functional_spec.md` §13.4).
- **D16, D18** — **Ruled 2026-10-01: Rehydrate is incomplete and not
  exposed to operators** (`rehydrate_enabled` ships false), carried in
  `guide/deferred_consolidated.md` with D17's rest. The Rehydrate analyzer
  checks, and a streaming, bounded responses parser.
- **C2** — Quick Setup's count indicators, success messages and per-row
  errors were removed deliberately in `40bc2549`. Confirm the removal
  stands.
- **B20** — Retry and `failed_persistent` exist for scheduled activation
  only. Should invites and reminders get them too?
- **B18** — `spec/lifecycle.md` §8.2.2 names one call site, `resolve_offset`,
  which has no callers. Should the code be consolidated onto it, or the
  contract restated?

**Shipped behavior differs from the spec. Which is the contract?**

- **A1** — Replicate does not share `rule_set_id` and does not copy the
  labels or Band 1 state. A replica starts closed and "Not set up". Tests
  pin the code.
- **A22, A23** — Sorting. The spec has a Sort column on the display-field
  table, a per-column click cycle and a Reset link. What ships is header
  badges, a replace-cascade on click, and no Reset.
- ~~**A24**~~ — **Ruled 2026-10-01: follow the spec. Done in #2724.** A
  stale sort id was not compacted on save: it failed the save with
  `cross_instrument` until a sort click rebuilt the inputs. The save now
  drops it.
- ~~**A7**~~ — **Ruled 2026-10-01: reopen the page submitted from. Done in
  #2724.** A
  blocked Submit re-rendered page 1. It now re-renders the page Submit
  was pressed on.
- ~~**B2**~~ — **Ruled 2026-10-02: an inactive side keeps its pairs,
  `include=False`.** Prepare wrote them `include=True`; the spec said
  active only. Keeping the rows keeps their responses through a
  deactivate → reactivate round trip.
- ~~**B4**~~ — **Ruled 2026-10-02: warn an active reviewer with no active
  assignments.** `reviewer_missing` tested whether a row existed, so a
  reviewer whose rows were all excluded was not flagged.
- **B7** — Group self-review: `include` follows the roster, while the
  `is_self_review` column follows the materialised rows.
- ~~**B17 = F3, with F17**~~ — **Ruled 2026-10-02: `ready` only. Done in
  #2745.** Reminders and per-row invitation actions: routes accepted
  `validated`, and the Invitations template allowed them only in
  `ready`. The routes now refuse outside `ready`; bulk Send invites
  keeps `validated`.
- **B21** — ~~`close_instrument`~~ (removed in #2722, with A6) and the
  visibility-when-closed route have no lifecycle gate.
- **B15, B27** — `GET /assignments?validated=1` and the Validate page's
  `verdict_*` / `lifecycle_copy` fields are reachable from no template.
  Retire them, or wire them?
- **A13** — `build_reviewee_results_context` still carries pre-release
  scaffolding that the route-level gate makes unreachable.
- **D7, D13** — The responses bundle does not carry the by-instrument and
  metadata files the spec promises. The `Instrument_{N}` CSV fallback uses
  position, and the screen uses `session_seq`.
- **G16 = E22** — Session codes are unique across the workspace. The spec says
  per operator.
- ~~**G21**~~ — **Ruled 2026-10-02: keep the behavior, correct the
  spec.** The raw invitation token was stored in the outbox body and
  reusable until the next send, while the spec said it was never stored
  and one-shot. The link is not a credential (sign-in plus a matching
  email), so the spec now says what is true. `docs/security_posture.md`
  made no such claim.
- **F23** — The Graph stub docstring says delegated `/me/sendMail`, and
  `spec/email_infra_options.md` says Option B is an app permission.
- ~~**C1**~~ — **Ruled 2026-10-02: follow the code. Done in #2739.**
  Quick Setup's Lock/Unlock prose said the toggle renders in
  `validated` and `ready`; the code and tests say draft only.

**Visual treatment: the specs disagree with each other or with `base.html`.**

- **E5** — The Setup row's active underline is `--marker-neutral` (grey),
  not `--nav-marker-setup` as three specs say. Is the token stale, or is
  the CSS a bug against the blue Setup identity?
- **E4, E13** — The tab hover foreground is `--text-body`, not
  `--nav-tab-active-fg`, which no page shows. The status strip's surface
  is `--surface-page`, not `--surface-card`.
- **E7, E8** — The Workflow card body has a 7.5em minimum (in
  `workflow_card.md`), and `ui_elements.md` and `session_home.md` say
  there is none. The grid gap is 16px, against a 20px stack; measure that
  in a browser.
- **E14** — Session Home has no H1, and `visual_style_rrw.md` says the
  session name is its H1. Add one, or drop the clause?
- **E25–E29** — Where `visual_style_general.md` (said to win on
  treatment) contradicts what ships: the 2px focus ring, link underlines,
  row borders and heading gap, example hexes below the AA floor,
  confirmations, loading indicators, font and line-height. The likely
  ruling is app-override notes in `visual_style_rrw.md`, as the status
  strip already has.
- **E2** — Four §10 primitives have CSS and no markup. Retire the
  entries, the CSS, and the `.btn-row` test references?

**New from the fix batches (2026-10-02).** Each was found while
fixing a no-ruling row (#2731–#2738). **All eight ruled 2026-10-02.**

- ~~**E36**~~ — **Ruled: a delete-confirmation checkbox and warning below
  the Data shaper's button row, flush right. Done in #2741.**
- ~~**C1**~~ — **Ruled: follow the code. Done in #2739.** The Lock /
  Unlock toggle renders only while the card is available (`draft`,
  no responses); `quick_setup_card_spec.md` and `session_home.md` now
  say so.
- ~~**A27**~~ — **Ruled: fix; the rows should sort. Done in #2743**: a
  stored spec with a `response:N` key renders the operator default and
  the on-load script re-sorts it through the click path.
- ~~**Invite landing ignores `Reviewer.status`**~~ — **Ruled: an inactive
  reviewer is treated as not a reviewer at all. Done in #2740**: their
  token resolves as not found (404), and per-row Remind refuses them
  with Send's 409.
- ~~**Observer per-instrument CSV**~~ — **Ruled: add the archive guard.
  Done in #2740.**
- ~~**Auto-send caption treats `expired` / `archived` as prepared**~~ —
  **Ruled: scheduled send is work in progress awaiting Azure. Recorded
  in #2739** as `guide/post_azure_todo_checklist.md` item 7.
- ~~**Outbox status wording**~~ — **Ruled: the code should say `queued`
  until a message is actually sent, awaiting Azure. Recorded in #2739**
  as `guide/post_azure_todo_checklist.md` item 8; `README.md` and
  `docs/status.md` describe today's `queued` → `sent` flip.
- ~~**R / ≡ toggle role**~~ — **Ruled: add a Toggle role. Done in
  #2739**: `spec/ui_elements.md` §6 gains **Toggle**, and it covers R,
  ≡ and ⑂ (audit rows 223, 224 and 230).

## 2. Code defects

The spec is right and the code is wrong; each ships as its own code PR.
All of these were confirmed by reading the code at `68f28224`.

**The six defects are done in #2719** (`guide/post_assessment_1oct.md`
E6), one commit and test each. The stale comments below stay open: each
is fixed with the next edit to its file. The spec halves of C4 and E32
stay in §3.

- **D17** — `app/services/session_rehydrate.py` joins `apply_result.errors`,
  which are `ApplyError` dataclasses, with `"; ".join`. The `TypeError`
  replaces the operator's message, though the rollback still happens. It
  is untested, and Rehydrate is off by default.
- **B29** — `assignments.reviewer_missing` sets
  `fix_anchor="#reviewer-row-{id}"`, but its `fix_url` is `/assignments`.
  The anchor exists only on the Reviewers page, so the deep link is dead.
- ~~**A19** — An editor save wipes `observer_tag` (see §1).~~ The column is retired (§1).
- **E32** — The Extract data page's **Purge and archive** is `btn alert`
  (the lock-card role), while the lobby uses `danger-solid` for the same
  action. Three buttons there carry inline `style="display: none;"`
  (`spec/ui_elements.md` §6 calls an inline style a defect).
- **E6** — `body.ui-v2 a.btn[aria-disabled="true"]` sets opacity 0.55,
  which beats the single 0.5 rule `ui_elements.md` specifies.
- **C4** — The `needs_confirm` banner says the checkbox is "at the top of
  Quick Setup", but it sits below the grid.
- **D17, the rest (deferred with Rehydrate, §1 D16).** #2719 catches `RehydrateError`, so a settings
  failure reaches the operator. Any other failure inside
  `rehydrate_session` (an `IntegrityError` from a roster save, a
  `ResponsesFormatError`) still answers 500 after the rollback, and
  `spec/rehydrate.md` §7 says every failing step is reported. Rehydrate
  is off by default.
- **Stale code comments.** Fix these with the next edit to each file:
  - `instrument_field.py:70-74` says "one level"; branching has two.
  - The `scheduled_events/__init__.py` docstring names three trigger pages.
  - `session_lifecycle.py:692` says "pre-filters to `draft`".
  - The `responses/_core.py:826` docstring says "any status".
  - The `_reviewee_results.py` docstring (see A13).
  - The `test_assignments_status_filter.py:142` docstring names
    `col_data_sample`.
  - `.env.example` cites `guide/segment_05A.md`, which is now under <!-- path-ref-ok -->
    `guide/archive/`.

## 3. Findings by file

One line each: id · severity · where · finding · decides. A line with no
`Decides` field means *spec*.

### `spec/`

- `instruments.md`
  - A1 med · `:1500-1519` · Replicate contract (§1) · author.
  - ~~A2 med · `:1417,1476` · "+Instrument is empty": it seeds Rating, Comments and the locked Name/Email rows.~~ Done in #2732.
  - ~~A3 med · `:722` · "sole surface" for self-review contradicts `:571-577` (the Link 3 checkbox owns the rule).~~ Done in #2732.
  - ~~A4 low · `:662` · `_new_model_usable_tags` → `new_model_usable_tags` (also B5, C17).~~ Done in #2732.
  - Also G10 `:144-149,345-360`.
- `reviewer-surface.md`
  - ~~A5 high · `:831` · Prev/Next hidden when closed · author.~~ Done in #2723.
  - ~~A6 high · `:799-810` · write gate session-wide · author.~~ Ruled: per-instrument Open / Close removed; done in #2722.
  - ~~A7 med · `:780-793` · blocked Submit → page 1 · author.~~ Ruled: the page submitted from; done in #2724.
  - ~~A8 med · `:62,1557` · the dashboard links `/summary` once submitted, built in `_dashboard.py`.~~ Done in #2732.
  - ~~A9 low · `:230` · Submit redirects to the bare URL; only the current page posts.~~ Done in #2724.
  - ~~A10 low · `:119` · pill reads `{label}: {state}`.~~ Done in #2732.
  - ~~A11 low · `:281,566,1339` · no acknowledge path; fraction 0.5, not 75%; invite lands on the bare URL.~~ Done in #2732.
  - ~~A12 med · `:874,1334` · identity is `normalize_email` (strip + lower), not casefold.~~ Done in #2732.
- `participant_model.md`
  - A13 med · `:84` vs `:97` · scaffolding contradiction · author (builder code).
  - ~~A14 med · `:25-29` · casefold → `normalize_email`.~~ Done in #2732.
  - ~~A15 low · `:41-44,150` · the "Session Edit Details" page is retired (also `visibility_policy.md:94,149`).~~ Done in #2732.
  - ~~A16 low · `:157` · Stop-release exists.~~ Done in #2732.
  - ~~A17 low · `:59` · the observer events omit `cohort_rule_assigned` and `bulk_deleted`.~~ Done in #2732.
- `visibility_policy.md`
  - ~~A18 high · `:73-78,116` · peer grant has no reader · author.~~ Ruled: Raw or off.
  - ~~A19 high · `:35,180-190` · `observer_tag` is unenforced and wiped · author + code.~~ Ruled: retired.
  - ~~A20 med · `:117` · the reviewee cell "Default `after_release`" contradicts §4.1. Read `test_doc_conventions.py` before editing the tokens.~~ Done in #2732.
  - ~~A21 low · `:217` · `resolve_mode` applies no scope; the views do.~~ Done in #2732.
- `sort_by_reviewee.md`
  - A22 high · `:39-90` · operator sort UI · author (also `operator_ui_concept.md:94`).
  - A23 med-high · `:94-100` · click semantics and Reset · author.
  - ~~A24 med · `:162-169` · no auto-compact · author.~~ Ruled: follow the spec; done in #2724.
  - ~~A25 med · write/deepen · the group `-1` key and group-surface sorting are unspecced.~~ Done in #2732.
  - ~~A26 low · `:268-274` · the lobby and Archived pages adopt it too, with other cookie names.~~ Done in #2732.
  - ~~A27 low-med · `:104-116` · the server drops `response:N` keys, so a response-only cookie flickers · author: there is no flicker. The cookie decodes to `[]` and the rows keep insertion order while the badge shows a sort; fix by sorting response keys on the server, or by reordering on load.~~ Done in #2743.
- `assignments.md`
  - ~~B1 high · `:87-90,500-511,682` · there is no `Assignment.group_key` column; it is derived by `responses.group_keys`.~~ Done in #2733.
  - ~~B2 high · `:68-70,566` · inactive rows are generated · author.~~ Ruled: kept, excluded.
  - ~~B3 med · `:891-894` · `col_data_sample` is gone.~~ Done in #2733.
  - ~~B4 med · `:1151-1167` · Validation-surfaces rules: scope, never-generated and links are *spec*; `include` is *author*.~~ Ruled: active work only.
  - ~~B5 low · `:159` · helper name.~~ Done in #2733.
  - ~~B6 low · `:1019,1084` · no UI posts to `/assignments/generate`.~~ Done in #2733.
  - B7 low · `:426-461` · group self-review · author.
- `reconciling_regeneration.md` — current.
- `workflow_card.md`
  - ~~B8 high · `:500-525` · the banner posts to `/activate`, not `/workflow/activate` (contradicts its own `:925`).~~ Done in #2733.
  - ~~B9 med · `:107,754` · the checklist renders in every draft state.~~ Done in #2733.
  - ~~B10 med · `:132-139,890-903` · `manual_activate_cancellation` shape, condition and copy.~~ Done in #2733.
  - ~~B11 med · `:74-82` · `is_configured` has one rule, not a legacy split.~~ Done in #2733.
  - ~~B12 med · `:830-888` · skip-notice and auto-send copy.~~ Done in #2733.
  - ~~B13 low · `:44,597,681` · Close in States 7–9; State 1 renders no Prepare; slug list.~~ Done in #2733.
  - ~~B14 low · `:918,923` · generate invalidates `validated`; the remind gate is B17.~~ Done in #2733.
- `lifecycle.md`
  - B15 med · `:76-78` · `mark_validated` callers; `?validated=1` · spec + author.
  - ~~B16 med · `:260-269` · response-loss ack callers · author.~~ Ruled: the tick is the ack.
  - ~~B17 med · `:271-291` · `_require_validated_or_ready` lives in `_operations.py`; reminders gate.~~ Done in #2745.
  - B18 med · `:663-668` · `resolve_offset` has no callers · author.
  - B19 med · `:759-770` · sweep trigger · ruled: awaits Azure (`post_azure_todo_checklist.md` item 7).
  - B20 low · `:786-799` · retry is activation-only · author.
  - B21 med · `:306-313,552` · ~~close reason is `manual`, not `operator` (spec)~~ already right after #2722; the ungated routes are *author*.
  - ~~B22 low · `:165,542` · `session.activated` context adds `trigger`, and activation clears `scheduled_activate_at`.~~ Done in #2733.
  - ~~B23 low · `:111-133` · state the `invalidate_if_validated` rule, not a partial call-site list.~~ Done in #2733.
  - ~~B24 low · `:51` · `lifecycle_display_label`; `lifecycle_label` is the filter.~~ Done in #2733.
  - ~~B25 low · `:237` · Quick Setup and settings import test `is_editable` inline.~~ Done in #2733.
  - ~~B26 low · `:318-324` · `observe_deadline` callers.~~ Done in #2733.
  - ~~Also G6 `:47` "pre-filters to `draft`".~~ Done in #2733.
- `validate_page.md`
  - B27 med · `:137-141` · dead verdict and lifecycle fields; the copy branches on `closed` · spec + author.
  - ~~B28 low · `:390` · grouped by `(gate, source)`.~~ Done in #2733.
  - ~~B29 med · `:270-273,425-430` · dead deep link · code (§2); `reviewer_missing` scope.~~ Done in #2733.
  - B30 med · `:409` · the §5.3 table: Prepare is the live gate (= B15).
- `setup_pages.md`
  - ~~C11 med · `:243-245` · the Reviewees label editor is one row of three tag cells.~~ Done in #2731.
  - ~~C12 low · `:58-62,93` · all four roster guidance cards are full width.~~ Done in #2731.
  - ~~C13 low · `:599` · empty tag columns don't render (contradicts `:606`).~~ Done in #2731.
  - ~~C14 low · `:1347,1354,696` · "Photo" → "Profile".~~ Done in #2731.
  - ~~C15 low · `:1521` · Observers preview is Name then Email.~~ Done in #2731.
  - ~~C16 low · `:1413` · the relationships extract has six columns.~~ Done in #2731.
  - ~~C17 low · `:28,182` · Edit page retired; helper name.~~ Done in #2731.
- `quick_setup_card_spec.md`
  - ~~C1 high · `:23-25` · lock-toggle prose · author (likely spec).~~ Ruled: follow the code. Done in #2739.
  - C2 med · `:34-49,87-91` · counts and messages removed · author.
  - ~~C3 med · `:77` · settings replace cascades · author.~~ Ruled: gated on the server; the spec names the cascade.
  - ~~C4 low · `:67,79,131` · checkbox below the grid; copy (+ code banner, §2).~~ Done in #2731.
  - ~~C5 low · `:25,121` · `closed` → `expired`.~~ Done in #2731.
  - ~~C6 low · `:83` · the settings per-slot route isn't allowlisted (no UI calls it).~~ Done in #2731.
- `session_home.md`
  - ~~C1 also `:460-481,506-512`.~~ Done in #2739.
  - C7 med · `:275-322,518-524` · Danger Zone in `expired`/`archived` · author.
  - ~~C8 low · `:155,306` · Activated "inline section"; copy reads "Revert to draft first".~~ Done in #2731.
- `sessions_overview.md`
  - ~~C9 low · `:217` · Tags is not sortable.~~ Done in #2731.
  - ~~C10 low · write/deepen · `:241-247` · the expander's Name/Code/Deadline are draft-only.~~ Done in #2731.
- `session_owners.md` — current.
- `timezone_display.md`
  - ~~C18 med · `:65-66` · email zone · author (= D25).~~ Ruled session zone; done in #2720.
  - ~~C19 low · `:67-70` · carve out the UTC audit extract.~~ Done in #2731.
  - ~~C20 low · `:56,94-98` · the dashboard uses the compact offset; `/edit` is only a redirect.~~ Done in #2731.
- `preview_hub.md`
  - ~~C21 low · `:15-18` · the `GET …/preview` 308 is unlisted.~~ Done in #2731.
- `ui_elements.md`
  - ~~E1 med · retire · `:439` · `.btn-cta` has no rule (also `operator_button_audit.md:47`; drop it from `test_cascade_ties.py` CANONICAL); `.btn.danger` row.~~ Done in #2737.
  - E2 low-med · `:690` · dead §10 primitives · author.
  - ~~E3 med · `:140` · status-strip slots: no Assignments pill; point at `visual_style_rrw.md`.~~ Done in #2737.
  - E4 med · `:125` · hover foreground · author.
  - E5 med · `:111` · Setup underline token · author.
  - E6 low · `:457` · anchor opacity 0.55 · code (§2).
  - E7 low-med · `:275` · Workflow body min-height · author.
  - E8 low-med · §4 · grid gap 16px · author (measure first).
  - ~~E9 low · tallies and provenance; keep the 6px rail and the specificity tuples, which tests read.~~ Done in #2737.
- `color_tokens.md`
  - ~~E10 low · `:308` · 4.14 / 3.55, not 3.96 / 3.41 (also in `status_history.md`, which is dated).~~ Done in #2737.
  - ~~E11 low · `:182` · `--slate-deep` is shared with the dark help-card border.~~ Done in #2737.
- `visual_style_rrw.md`
  - ~~E12 med · `:44` · five live states.~~ Done in #2737.
  - E13 low-med · `:56` · status-strip surface · author.
  - E14 med · `:161-233` · ~~Edit Session is retired (spec)~~ done in #2737; Home H1 · author (also `operator_ui_concept.md:195`).
  - ~~E15 med · `:339` · lobby columns; point at `sessions_overview.md` (also `operator_ui_concept.md:230`).~~ Done in #2737.
  - ~~E16 low-med · `:466` · there is no thank-you page.~~ Done in #2737.
  - ~~E17 med · `:686` · the description renders below the H2.~~ Done in #2737.
  - ~~E18 low · `:155,174,296,332` · label weight, the Email pill copy, lobby lifecycle pills, breadcrumbs.~~ Done in #2737.
  - ~~E19 low · retire · `:794-838` · the "Doc impact" section is plan residue.~~ Done in #2737.
- `visual_style_general.md`
  - E25–E29 med · treatments contradicted by the app · author.
  - E28 also write/deepen: a contrast-floor paragraph.
- `operator_ui_concept.md`
  - ~~E20 low-med · `:208` · the app identity is a `<span>` (contradicts `:399`).~~ Done in #2737.
  - ~~E21 med · `:71,82,175` · Relationships is feature-gated too.~~ Done in #2737.
  - E22 med-low · `:240` · code uniqueness (= G16).
  - ~~E23 med · consolidate · `:352` · reduce the Validate page description to a pointer at `validate_page.md`.~~ Done in #2737.
  - ~~E24 low · `:459` · nine operator Guide sections.~~ Done in #2737.
  - Also A22 `:94`.
- `operator_button_audit.md`
  - ~~E30 med-low · rows #11–13 and #123–125 each appear twice; give the later rows the next free ids.~~ Done in #2737.
  - E31 med · write/deepen · ~~unaudited: the lobby expander, Extract data, the Instruments toggles, the chrome Guide/Admin links~~ done in #2737 (Rehydrate stays unaudited while it is gated off) · ~~the R/≡ toggle role is *author*~~ ruled Toggle, done in #2739.
  - ~~E36 med · new · the Data shaper's Delete (audit row 217) is `btn destructive` with no confirm step, against the audit's cross-page convention 6 · author.~~ Done in #2741.
  - E32 med · code (§2).
  - ~~E33 low-med · `:808` · `.tab-strip-page` uses tokens, not those literals.~~ Done in #2737.
  - ~~E34 low · rows 119, 121.~~ Done in #2737.
  - ~~E35 low · provenance in cells; the repeated Inactivate note.~~ Done in #2737.
- `csv_contracts.md`
  - ~~D1 med · `:451,470,686` · `session_rule_sets` keys are ordinal only, every row is emitted, and types are lowercase.~~ Done in #2735.
  - ~~D2 low · `:184` · responses are ordered by email.~~ Done in #2735.
  - ~~D3 med · `:218` · stats files are not the roster shape.~~ Done in #2735.
  - ~~D4 med · `:900` · bundle members: `observers.csv`, data shapes, `participant_tokens.csv`.~~ Done in #2735.
  - ~~D5 med · write/deepen · `:44-50,744` · the 1 MiB / 5,000-row caps; the `_read_dict_rows` shape.~~ Done in #2735.
  - ~~D6 low · bundled: 14 extract modules, "Pair context N", compact `DetailJson`, keyword-only signatures, the `visible=False` drop.~~ Done in #2735.
- `extract_data.md`
  - D7 high · `:202-207` · bundle contents · author.
  - ~~D8 med · write/deepen · `:21-27,987` · the Archive session (purge) card and the Extract Setup card are unspecced.~~ Done in #2735.
  - ~~D9 med · `:151-166` · the self-review chip copy and its own storage key.~~ Done in #2735.
  - ~~D10 med · `:868` · the `_self`/`_noself`/`_both` suffix.~~ Done in #2735.
  - ~~D11 med · `:978` · clone does copy DataShapes.~~ Done in #2735.
  - ~~D12 low · bundled labels, helper name, slug, identity rows.~~ Done in #2735.
  - D13 low · `:129` · `Instrument_{N}` fallback · author.
- `roundtrip_coverage.md`
  - ~~D14 med · `:127` · `results_acknowledged_at` is cloned.~~ Done in #2744.
  - ~~D15 low · `session_seq` is absent from the matrix.~~ Done in #2735.
- `rehydrate.md`
  - D16 med · analyzer · author.
  - D17 med · code (§2).
  - D18 med · parser · author.
  - ~~D19 low · `:377` · closed-branch drops.~~ Done in #2735.
  - ~~D20 low · `:7` · four routes 404, not three.~~ Done in #2735.
- `settings_inventory.md`
  - ~~D21 med · §7 · missing browser keys and cookies (`rrw-extract-data-chips-*`, `rrw-self-review-handling-*`, both tag filters, `rrw_instruments_pending_open`, both sort cookies); "Photo".~~ Done in #2735.
  - ~~D22 med · §4/§5 · missing columns: five instrument ones, `profile_link`, `cohort_rule`, the observer unique constraint.~~ Done in #2735.
  - ~~D23 low · `:111` · `archive_offset` has no editor.~~ Done in #2735.
  - ~~D24 low · §8 · five env vars missing (= H12).~~ Done in #2735.
- `email_template_editor.md`
  - ~~D25 high · `:195,198` · email zone · author (= C18).~~ Done in #2720.
  - ~~D26 med · `:87-89` · fields are empty with a placeholder (contradicts `:57`).~~ Done in #2735.
  - ~~D27 low · `:289-299` · test counts; label punctuation.~~ Done in #2735.
- `architecture.md`
  - ~~F1 high · `:528,542,352` · locked Name/Email rows *are* seeded (conflicts with `instruments.md:875`).~~ Done in #2734.
  - ~~F2 med · `:320,361` · headings use `short_label`.~~ Done in #2734.
  - ~~F3 med · `:435` · invitations: validated or ready.~~ Done in #2734.
  - ~~F4 med · `:477` · the `reminders.sent` envelope.~~ Done in #2734.
  - ~~F5 med · `:724,755` · the canonical audit examples.~~ Done in #2734.
  - ~~F6 low · `:623` · `reviewer.bulk_deleted`.~~ Done in #2734.
  - ~~F7 low · `:281` · `rules/preview.py` is gone.~~ Done in #2734.
  - ~~F8 low · `:236` · drop line numbers.~~ Done in #2734.
- `permissions.md`
  - ~~F9 med · `:119` · `/about` creates a user row; §3 omits `/guide`, `/templates/*.zip` and the `/me/sessions/{id}` 303.~~ Done in #2734.
  - ~~F10 low · `:276` · test counts.~~ Done in #2734.
- `audience_and_identity_model.md`
  - F11 med · unbuilt contract · author.
- `role_landing_and_visibility.md`
  - ~~F12 low · `:112` · a reviewer's `ready` can still be closed.~~ Done in #2732.
- `role_navigator.md`
  - ~~F13 high · `:86-88` · casefold → `.lower()` (= A12, A14).~~ Done in #2732.
  - ~~F14 low · `:64` · pre-open renders 200.~~ Done in #2732.
- `domain_assumptions.md`
  - F15 med · statuses · author.
  - ~~F16 low · `:29` · purge-and-archive can delete.~~ Done in #2734.
- `operations_pages.md`
  - ~~F17 high · `:359` vs `:144` · per-row invitation buttons in `validated`.~~ Done in #2745.
  - ~~F18 med · `:526` · at-risk is coverage only.~~ Done in #2734.
  - ~~F19 low · the classifier lives in `services/monitoring.py`.~~ Done in #2734.
  - ~~F20 low · move the measurement figures (see the sweep record, §5).~~ Done in #2734.
- `email_infra_options.md`
  - ~~F21 low · the audit scaffolding has landed.~~ Done in #2734.
  - ~~F22 low · Reply-To is not built.~~ Done in #2734.
  - F23 low · Graph docstring · author.
  - ~~F24 low · `sent_at`; retire the stale "Doc impact" section.~~ Done in #2734.
- `blob_storage.md`
  - ~~F25 low · `:33` misquote; `:171` time-bound claim.~~ Done in #2734.
- `spec/README.md`
  - ~~F26 low · the `domain_assumptions` row sits in the Visual/UI table.~~ Done in #2734.
  - ~~Also: the Peer reviewer audience is described as "own + peers" (`:25`), which conflicts with `visibility_policy.md` §1.1.~~ Done in #2734.
- `rrw_functional_spec.md`
  - ~~G1 low · `:1770` · invitation status `pending`.~~ Done in #2736.
  - ~~G2 med · `:2187-2204` · names audit events that don't exist.~~ Done in #2736.
  - ~~G3 low · `:914` · the reminder carries `$invite_url` (contradicts `:1788`).~~ Done in #2736.
  - G4 low-med · `:921` · Responses-received switch · author.
  - ~~G5 med · `:686,2149,106` · the Activate super-button survives; activation is from `validated` only.~~ Done in #2736.
  - ~~G6 med · `:676,704-712,2231` · Archive and Release are `expired`-only on the card; lobby purge-and-archive; the Extract Archive card.~~ Done in #2736.
  - G7 med · `:1075,2244` · Delete Data is draft/validated only (= C7).
  - ~~G8 med-high · `:1586-1670` · pages, dirty state and Save; `reviewer-surface.md` wins.~~ Done in #2736.
  - ~~G9 low-med · `:714,1565` · non-open states render pre-open.~~ Done in #2736.
  - ~~G10 med-high · `:418,1210,1568` · visibility-when-closed · author.~~ Ruled: policy decides; done in #2723.
  - ~~G11 low-med · peer grant (= A18).~~ Ruled: Raw or off (A18).
  - ~~G12 med · `:2088-2102` · readiness checklist overstated; consolidate with `validate_page.md`.~~ Done in #2736.
  - G13 low-med · `:2123` · export validation · author.
  - ~~G14 low-med · `:1835-1851` · invites fire from `validated`; the captions are on the Workflow card.~~ Done in #2736.
  - ~~G15 med · `:1012` · clone never copies responses or assignments.~~ Done in #2736.
  - G16 low-med · `:349,853` · code uniqueness · author (also `operator_ui_concept.md:240`).
  - ~~G17 low-med · `:774,813` · non-allowlisted users get a 303 to `/me`.~~ Done in #2736.
  - ~~G18 low-med · `:829,1516` · there is no sys-admin owner management.~~ Done in #2736.
  - ~~G19 low · `:1479` · Rehydrate is gated off.~~ Done in #2736.
  - ~~G20 low · `:1490` · SMTP modes are `starttls`/`ssl`.~~ Done in #2736.
  - ~~G21 med-low · `:592,796,1767` · token storage and reuse · author.~~ Ruled: the spec is corrected.
  - ~~G22 low · write/deepen · branching: ranges, any/none, the anchor rule, hidden parents.~~ Done in #2736.
  - ~~G23 low · `:721` · Observers lock only when `archived` (contradicts §9.5).~~ Done in #2736.
  - ~~G24 low · provenance and segment history in the spec, at about ten sites.~~ Done in #2736.
  - ~~G25 low · write/deepen · tags, owners, the who-can-see card, `/guide` and `/about`, theme.~~ Done in #2736.

### `docs/`

- `architecture.md`
  - ~~H1 med · `:17-44,96` · topology lacks the gateway, VNet, private endpoints and runner.~~ Done in #2738.
  - ~~H2 med · `:100` · not every state change is a form POST; scheduled events fire on GETs (also `security_posture.md`, `azure_provision.md`).~~ Done in #2738.
  - ~~H3 low · correlation ids are in audit only.~~ Done in #2738.
  - ~~H4 low · prebuilt `antenv`, not Oryx.~~ Done in #2738.
  - ~~H5 med · `:81` · Key Vault + managed identity stated as fact (contradicts `security_posture.md`).~~ Done in #2738.
- `database.md`
  - ~~H6 low · `:5,11` · "this segment".~~ Done in #2738.
- `local_setup.md`
  - ~~H7 med · `:210,299` · `/` 302-redirects; it doesn't return 200 JSON (also `deployment_dev.md:211`).~~ Done in #2738.
- `security_posture.md`
  - ~~H8 low · `:195` · retired `/operator/settings/library/*`.~~ Done in #2738.
  - ~~H9 low · `:224` · table split; `_require_editable` location.~~ Done in #2738.
  - ~~H10 low · `:400` · fake auth reads no headers.~~ Done in #2738.
  - ~~Also G21.~~ It makes no token-storage claim; nothing to correct.
- `deployment_dev.md`
  - ~~H11 **high** · `:314-318,379` · "`DELETE FROM users` cascades" is false; the FK has no `ON DELETE`, so raw SQL fails.~~ Done in #2738.
  - ~~H12 med · the env table is missing three vars.~~ Done in #2738.
  - ~~H13 med · `:117` · SMTP is live, so `SMTP_ENCRYPTION_KEY` is needed now.~~ Done in #2738, on a corrected premise: SMTP does not send, but the Settings page encrypts operator SMTP passwords, so the key is needed now.
  - ~~H14 low · `:50` · the artefact includes `antenv/`.~~ Done in #2738.
  - ~~H15 low · `:322` · that audit is shipped.~~ Done in #2738.
- `deployment_nus.md`
  - ~~H11 `:337`.~~ Done in #2738.
  - ~~H16 med · statuses settled by v7; consolidate.~~ Done in #2738.
  - ~~H17 med · database `rrw` vs v7's `reviewrobin`.~~ Done in #2738.
  - ~~H18 **high** · `:372` · Rehydrate as the data-carry path is off by default.~~ Done in #2738.
  - ~~H19 low · `:386` · §6.3 → §6.4.~~ Done in #2738.
- `azure_provision.md`
  - H20 med · email is wired · **premise wrong:** nothing calls the SMTP transport. `app/services/invitations.py` stamps outbox rows `sent` without sending, and real sending is Segment 14B. Item 8 stays "not yet wired"; nothing to fix.
  - ~~H21 med · overtaken; retire.~~ Done in #2738.
  - ~~H22 low · SMTP credentials are per user, encrypted in the DB.~~ Done in #2738.
- `azure_github_setup.md`
  - ~~H23 med · `:64-73` · a DML-only role can't run migrations.~~ Done in #2738.
  - ~~H24 med · retire or consolidate into `deployment_nus.md`.~~ Done in #2738.
  - ~~H25, H26, H27 low · a duplicate pointer; `deploy_nus.yml`/`NUS_*`; local Docker Postgres is deferred.~~ Done in #2738.
- `cli_setup.md`
  - ~~H28 med · `:229,240` · Python ≥3.12.~~ Done in #2738.
  - ~~H29 low · node is needed.~~ Done in #2738.
  - ~~H30 low · section name.~~ Done in #2738.
  - ~~Also H27.~~ Done in #2738.
- `backup_restore.md`
  - ~~H31 low · rehydrate stashes uploads.~~ Done in #2738.
  - ~~H32 low · the storage deferred row.~~ Done in #2738.
- ~~`operations_runbook.md` — H13 `:69-71`.~~ Done in #2738.
- `troubleshooting.md` — current.
- `README.md` (docs)
  - ~~I11 med · no row for `unenforced_conventions.md`.~~ Done in #2738.
- `known_limitations.md`
  - ~~I3 med · `:10-23` · infra posture is silent on the provisioned NUS environment (at cutover).~~ Done in #2738.
  - ~~I10 low · no `beforeunload` guard; no autosave.~~ Done in #2738.
- `unenforced_conventions.md`
  - ~~I20 med · `:403-407` · "no browser in CI" is false; leans on the dev slot.~~ Done in #2738.
- `status.md`
  - ~~I1 **high** · `:910,1063,1082,1084` · autosave claimed as shipped.~~ Done in #2738.
  - ~~I2 med · `:897` · one page per instrument.~~ Done in #2738.
  - ~~I7 med · route table `:681-843`.~~ Done in #2738.
  - ~~I8 med · audit table `:1005-1050`.~~ Done in #2738.
  - ~~I9 med · `:541,547,588` · infra bullets.~~ Done in #2738.
  - ~~Also README `:941,964` Band 3 → Band 2.~~ Done in #2738.
- `nus_azure_status_v7.md`, `practice-audit-2026-09-04.md`, `status_history.md` — current or dated.

### Root

- `README.md`
  - ~~I1 · I2 `:93` · I5 low `:42,81` · I6 low `:65,94` (`setup-invite`; Band 2; the node skip).~~ Done in #2738.
- `rrw_design_rationale.md`
  - ~~I1 high `:133,219` · I2 `:133` · I3 `:171,195` · I5 `:177`.~~ Done in #2738.
- `azure_ask.md`
  - ~~I12 med · answered differently; retire or annotate.~~ Done in #2738.
  - ~~I13 low · `:38,182`.~~ Done in #2738.
- `rrw_sdd_in_practice.md`
  - ~~I14 med · `:5` · "no local dev loop" (contradicts `:220`).~~ Done in #2738.
- `CLAUDE.md` / `AGENTS.md`
  - ~~I15 med · `/results` gates on `require_reviewee_with_current_grant`.~~ Done in #2738.
  - ~~I16 low · six Setup pages.~~ Done in #2738.
  - ~~I17 low · ~35 s (134 s measured); `ci-postgres` ignores `tests/browser/`.~~ Done in #2738.
  - ~~I18 low · name `docs/unenforced_conventions.md`.~~ Done in #2738.
- `new_project_practices_setup.md`
  - ~~I19 low · `:139` · the dev-slot mention, via `tools/practice_kit.py`.~~ Done in #2738.
- `CONTRIBUTING.md`, `constitution.md` — current.
