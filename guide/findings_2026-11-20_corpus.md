# Findings — corpus sweep (2026-11-20)

**Found by:** `guide/sweep_2026-11-20_corpus.md` · **Read at:** `6003c8084`
(#4063) · **Open:** all rows.

The register lists every divergence found when each live file in `spec/`,
`docs/` and the root, the two `cordware/spec/` files, and each application
package's `spec/` and `docs/` were read against the code they describe.
- **The reads:** seven verify-mode `spec-writer` reads, split by area.
- **The packages:** this is the first sweep to read them; segment 23H made
  their prose live.
- **No edits:** nothing in scope was edited. A sweeper may not re-align a
  spec to the code (`rrw_sdd_in_practice.md` §4), so each divergence is
  listed here and the fixes ship afterwards as ordinary PRs.
- **Striking rows:** a row is struck when it is done, with its PR, or
  marked declined with the reason.
- **Code defects:** those found by reading the code for bugs, rather than
  the specs for drift, are in the sibling register
  `guide/findings_2026-11-20_assessment.md`. Two rows here and there
  are the same defect, seen from each side, and say so.
- **The packages' findings** are in each package's own guide folder:
  `applydesk/guide/findings_2026-11-20_sweep.md` (7),
  `residentialapps/guide/findings_2026-11-20_sweep.md` (10) and
  `utilityapps/guide/findings_2026-11-20_sweep.md` (3).

**Ids** carry the area of the read, and restart at 1 in this file:

| Id | Area |
|---|---|
| **A** | the reviewer and participant surfaces |
| **B** | lifecycle, the Workflow card, assignments, Operations |
| **D** | data in and out |
| **E** | UI and visual style |
| **F** | architecture, permissions, identity, the functional spec and the Cordware specs |
| **H** | `docs/` and the root documents |

**Severity** is the reader's.

**Decides:**
- *spec*: the spec is wrong and an update in place fixes it;
- *code*: the code is wrong against a spec that is right;
- *author*: a choice between fixing the code and changing the contract;
- *trim*: provenance or a tally to strip, keeping the reason it carried.

In `docs/` and root rows, *doc* plays the part of *spec*. Line numbers
are at `6003c8084`.

## 1. Code defects

- **B1** (medium, code) — **the lobby's Due pill lights on a linked session whose card shows nothing due.**
  - `spec/workflow_card.md:766-769` and `spec/linked_sessions.md` hide the due prompts when the linked application takes `email`.
  - `build_due_lines` honours the lock (`app/web/views/_workflow_card.py:252-256`). `due_actions` and `sessions_with_something_due` do not (`app/services/due_actions.py:84-114`, `:192-199`), so `lobby_due_session_ids` (`app/web/views/_sessions_table.py:193-199`) still lights the pill.
  - A handoff's create-time Settings file may carry `session.scheduled_activate_at` and the offsets. The operator cannot clear the pill: details 409, a re-send 422 `not_owned`.
  - Reproduced by the assessment's defect read: the same defect is its **D1**.
- **B2** (low, code) — **a draft or validated session past End can be "closed" without expiring.**
  - The orchestrator guards on `is_ready` (`app/services/scheduled_events/__init__.py:342`). `observe_deadline`'s main branch does not (`app/services/session_lifecycle.py:1282`; `_expire_at_end` skips at `:1132`).
  - It is reached by the reviewer GET (`app/web/routes_reviewer/_surface/_context.py:153`) and the operator Instruments GET (`app/web/routes_operator/_instruments.py:76`). A settings import can leave an instrument `accepting_responses` on an editable session (`app/services/session_config_io/_apply_instrument.py:274`).
  - The result is `instrument.closed` and `session.deadline_reached` with no `session.expired`, against `spec/lifecycle.md:505-526`, `:975-979`.
  - Read, not run.
- **B3** (low, code; latent while `RRW_SCHEDULED_SEND` is off) — **the auto-send captions ignore the linked email lock.**
  - `build_auto_send_invites_caption`, `build_auto_send_reminders_caption` and `build_manual_activate_cancellation` (`app/web/views/_workflow_card.py:551-770`) never check `Lock.EMAIL`.
  - A linked session would read "System will dispatch automatically" while the trigger skips every entry. `spec/workflow_card.md:950-1010` needs the linked row too.
- **E1** (medium, author) — **Session Home's Email Template pill never reads *Set up*.**
  - `app/web/views/_setup.py:247` hard-codes `email_invites_set_up=False` under a stale "editor lands in Segment 15" comment. `session_setup_status_row.html:89` therefore always shows amber *Not set up*, however the template stands.
  - `spec/visual_style_rrw.md:210` promises both states.
  - Fix the predicate, or retire the pill.

## 2. For the author

- **B4** (medium) — **"Every transition is idempotent" holds for two of seven.**
  - `spec/lifecycle.md:794-796` says every state-machine function no-ops when the target state is current.
  - Only `mark_validated` (`app/services/session_lifecycle.py:351`) and `invalidate_session` (`:462`) do. `activate_session`, `expire_session`, `revert_session_to_draft`, `archive_session` and `unarchive_session` raise, and the Workflow routes guard them.
  - Narrow the principle to the two, or make the five idempotent.
- **B5** (low) — **Release can be stamped on a `ready` session by a direct POST.**
  - The predicate requires `expired`. `release_responses_now` and `stop_responses_release` (`app/services/session_lifecycle.py:339-454`) and their routes refuse only archived and linked sessions.
  - With no End, Release-from is then the review's end, and the next observation closes the session.
  - The service docstring (`:361-366`) admits it, and `spec/lifecycle.md:841` overclaims.
  - Gate on `expired`, or say so.
- **B6** (low) — **the Responses drill-in promises a per-reviewer breakdown it does not show.**
  - The promise is `spec/operations_pages.md:645`. The page shows aggregate coverage, and its help line says the breakdown "will land in a future segment" (`session_responses_reviewee_detail.html:36-47`).
  - Build it, or retire the promise.
- **E2** (medium) — **an operator who is also a reviewer sees operator links on reviewer pages.**
  - `spec/visual_style_rrw.md:523` forbids it, but `:341`, `:362` and `:535` say the bar's entries follow roles. `_partials/top_bar.html` keys on `_operator`, so `/me/sessions/...` shows Operator Lobby, Settings and Admin.
  - Choose which rule stands.
- **E3** (medium) — **"one page per instrument" is no longer the reviewer surface's principle.**
  - `spec/visual_style_rrw.md:476`, `:545-547`, `:562` and `:678-686` speak of page buttons, tabs and one instrument per page.
  - Pages are operator-defined (`starts_new_page`, `_pages_for_session`) and navigate by Prev, Next and `Page N of M`, as the same file says at `:459` and `:470`.
  - Rewrite the principle.
- **F1** (low) — **the functional spec does not mention linked sessions, handoffs, Unlink or owner report emails.**
  - All are user-visible capabilities.
  - A short section at intent altitude, or a deliberate omission.
- **F2** (low) — **§9.13 Settings misdescribes the page.**
  - `spec/rrw_functional_spec.md:1202-1207` describes "three per-operator toggles". The Email settings card also holds three report-email toggles (`app/services/operator_settings.py:335-340`), and a read-only Unit card follows (`operator_settings.html:134`).
- **H1** (low) — **`docs/header_chrome.md` is a built contract still in `docs/`.**
  - `docs/README.md:26` calls it "proposed, not built". The file itself says built and "retires into `spec/`".
  - Its §1 describes the replaced chrome in the present tense, `:24` cites the removed `reviewer/_top_bar.html`, and `:4` says "envisioned ApplyDesk".
  - Move it into `spec/visual_style_rrw.md` "Top bar", or retire it, and fix the index row.
- **H2** (low) — **`rrw_design_rationale.md:171`, `:197` read as if the institutional cutover were still ahead.**
  - The sentences are dated 2026-10-16, but nothing says production has served since 2026-10-31.
  - `docs/security_posture.md:556-567` keeps dev-slot rows in a current-looking table.
- **H3** (low) — **`cordware/spec/host.md:53-55` makes a claim this repository cannot check.**
  - It says production "carries no `residentialapps/` for now (2026-10-30)".
  - That is about the private deployment, so confirm it or retire it.

## 3. Per-file findings

**A** — the reviewer and participant surfaces:
- **A1** `spec/reviewer-surface.md:909-950`: the view-shape dict omits `intro_layout`, `response_layout`, `display_layout`, `constraint_by_field_id` and the `stack_*` keys (`app/web/routes_reviewer/_surface/_context.py:597-643`), and names `InstrumentGroup` and `GroupCompletion` where the code passes dicts. Spec.
- **A2** `spec/reviewer-surface.md:1136-1139`: the preview "shows" the closed state; `:1281-1283` and `_context.py:216-229` force `accepting` on. Spec.
- **A3** `spec/reviewer-surface.md:214-215`, `:270`: the Errors card is not only "numeric". It also takes String over `max_length`, List non-members, and the held-back "Kept until {parent} is fixed." rows. Spec.
- **A4** `spec/reviewer-surface.md:530`: the heading card renders on `heading.title or _help_in_heading`, as `:608-611` says. Spec.
- **A5** `spec/reviewer-surface.md:690-702`: the status icon shows only when `row.submitted_at or show_incomplete_marks` (`review_surface.html:549`). Spec.
- **A6** `spec/reviewer-surface.md:1337-1342`: the dropped-fields notice renders on the real surface too (`review_surface.html:56-72`), and Page anatomy does not list it. Write.
- **A7** `spec/reviewer-surface.md:2054-2057`: "no keydown handler" is false. `base.html` blocks Enter in one-line fit boxes, as `:813-815` says. Spec.
- **A8** `spec/reviewer-surface.md:1549-1556`: the Summary page uses a `Group` header, display-field columns, and tag-then-members order (`summary.html`). Spec.
- **A9** `spec/participant_model.md:72`: it cites `reviewer/_top_bar.html`, which no longer exists. The bar is `_partials/top_bar.html`; the path escaped the guard because it is unanchored. Spec.
- **A10** `spec/README.md:68`: the `/me` dashboard is six columns, not eight. Trim.
- **A11** `spec/audience_and_identity_model.md:349-350`: the welcome message is plain, autoescaped `pre-line` text, not "limited markdown"; `:356-358` already says so. Spec.
- **A12** `spec/audience_and_identity_model.md:520-521`: there is no tab strip; progress is the per-page pills. Spec.
- **A13** `spec/audience_and_identity_model.md:124`: the super-admin self-heal runs on every authenticated request (`deps._reassert_super_admin`), not just on sign-in. Spec, optional.

**B** — lifecycle, the Workflow card, assignments, Operations:
- **B7** `spec/lifecycle.md:890-894`: on a linked session Release from and until are not shown, rather than shown as *Off* (`session_detail.html:362-367`, `:430-433`). `spec/session_home.md` is right. Spec.
- **B8** `spec/lifecycle.md:563-604` (§5, and §3.1's 409 gates): the roster pages gate on `rosters_editable`, which is `is_editable and not Lock.ROSTERS`, narrower than the lifecycle's. The lock card has a fourth, linked branch; `spec/setup_pages.md:295` owns it. Spec.
- **B9** `spec/lifecycle.md:82-98`: `mark_validated` also raises `not_draft`, and the release services raise `archived` and `linked`. Spec.
- **B10** `spec/workflow_card.md:34-63`: `views/_handoffs.py:96` builds the card's context with `return_to="handoff"`, which is in neither allowlist. One line. Write.
- **B11** `spec/assignments.md:414-416`: `exclude_self_reviews` is reset on a Band-1 save (`resolve_exclude_self_reviews`). `spec/instruments.md:607-640` is right. Spec.
- **B12** `spec/assignments.md:1047`, `:1106`: the count line never shows `M` (`views/_preview_counts.py:68-100`). Spec.
- **B13** `spec/assignments.md:1473`: `assignments.no_included_pairs` also fires with no rows and before the first Generate (`validation/_assignments.py:41`). Spec.
- **B14** `spec/assignments.md:807`: Activate counts a skip only when the row's `include` is currently False (`assignments/_generate.py:54-114`). Spec.
- **B15** `spec/assignments.md:909`: an unloadable rule set keeps its generated and included counts (`views/_assignments.py:200-250`). Spec.
- **B16** `spec/assignments.md:624`: the `"both"` sentinel groups every pair, inactive reviewees included (`_group_reconciliation.py:221-250`). Spec.
- **B17** `spec/operations_pages.md:170-180`: the Send note is omitted under the linked `invitation_send` lock (`session_invitations.html:77-83`). Spec.
- **B18** `spec/operations_pages.md`, Invitations columns 7–8: Progress and Required Fields render `—` at a zero total, and an incomplete Required Fields is `pill-empty`. Spec.
- **B19** `spec/permissions.md:143-144`: the handoff rows miss `POST /operator/handoffs/{transfer_id}/update` (`routes_operator/_quick_setup.py:1739`); `spec/handoffs.md:37` lists it. Spec.
- **B20**: segment, rung and dated-ruling provenance in the new linked-session text of `spec/instruments.md`, `spec/operations_pages.md`, `spec/workflow_card.md`, `spec/lifecycle.md:954`, `spec/session_home.md` and `spec/setup_pages.md`. Grep `tests/` before cutting. Trim.

**D** — data in and out:
- **D1** `spec/csv_contracts.md:993-994`: the `instruments[n].order` cell is parsed, so a non-integer is a phase-1 error (`_apply_instrument.py:272-273`); only the stored value is ignored. Spec.
- **D2**: provenance in `spec/csv_contracts.md:388`, `:396`, `:706`, `:712`; `spec/handoffs.md:3-5`, `:109`, `:119-134`, `:173`, `:194`; `spec/rehydrate.md:406`; and the `spec/README.md` handoffs row. Trim.

**E** — UI and visual style:
- **E4** `spec/visual_style_rrw.md:210-213`: the status strip hides the Email Template pill under the linked `email` lock, and adds a *Linked: {name}* pill. Spec.
- **E5** `spec/visual_style_rrw.md:271`, `:391`: the lobby H1 is `Operator Lobby`, as `spec/sessions_overview.md` says. Spec.
- **E6** `spec/visual_style_rrw.md:441-445`: the review list is the six-column table, not "cards". Point at `spec/reviewer-surface.md`. Spec.
- **E7** `spec/visual_style_rrw.md:477`: "Dirty-state" names no heading; the heading is "Save button state". Spec.
- **E8** `spec/visual_style_rrw.md:504-521`: the error wording has drifted from `pre_open.html` and the invite 404. Spec.
- **E9**: provenance in `spec/ui_elements.md:881`, `spec/visibility_policy.md:201`, `spec/audience_and_identity_model.md:362`, `:506` and `spec/email_infra_options.md:193`, `:393`. Trim.

**F** — architecture, permissions, identity, the functional spec and the Cordware specs:
- **F3** `spec/architecture.md:1025-1032`: the `counts` envelope list omits `session.handoff_updated` (`app/services/audit.py:443`). Spec.
- **F4**: provenance in `spec/architecture.md:947` and `spec/rrw_functional_spec.md:979`. Trim.
- **F5** `cordware/spec/host.md:306-307`: the import check exempts the `tests/` folders of all three packages (`cordware/tests/test_import_boundary.py:113-123`), not only Residential's. Spec.

**H** — `docs/` and the root documents:
- **H4** `docs/deployment.md:14-16`: the host mounts Apply Desk too (`cordware/main.py:74-100`). Doc.
- **H5** `docs/local_setup.md:93-95`: Residential serves pages, not only health. Doc.
- **H6** `docs/local_setup.md:177-183`: an unset `CORDWARE_APPS` mounts all five applications, and `/` lists them. Medium-low. Doc.
- **H7** `README.md:137-141`: the same staleness as H5 and H6. Doc.
- **H8** `README.md:176-179`: pyright checks five test roots (`pyproject.toml`), not four. Doc.
- **H9** `README.md:195-200`: the residential lane runs all five Residential browser files, not three. Doc.
- **H10** `docs/unenforced_conventions.md:513`: §2 has four entries, not three. Doc.
- **H11** `docs/security_posture.md:384-388`: only the host `/health` is excluded, and "(below)" points nowhere. `docs/deployment.md:38` says each mount's `/health`. Doc.
- **H12** `rrw_sdd_in_practice.md:152`: `SPEC_COVERAGE` maps 31 feature modules, not 30. Date the figure, or re-take it. Doc.
- **H13** `new_project_practices_setup.md`, Step 7 and the kit table: the contrast-audit group is 17 tests (15 + 2), not 16. Doc.
- **H14** `docs/operations_runbook.md:63-65`: some foreign keys to `users.id` do cascade or set null (`rehydrate_stash`, `directory_lookup`, `held_upload`, `data_shape`). The warning stands; the generalization does not. Doc.
- **H15** `docs/performance.md:634-638`: R1 calls `instruments.cached_group_pair_count` a working precedent, but `docs/database.md:239` says it has no reader or writer. Mark R1 as history. Doc.

