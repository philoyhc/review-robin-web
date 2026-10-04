# Sweep — corpus (2026-10-03)

**Swept:** 2026-10-03 at `17986214` · **Scope:** `spec/` + `docs/` + root
practice docs (68 files) · **Previous sweep:**
`guide/archive/sweep_2026-10-01_corpus.md` · **Trigger:** asked for by the author;
not due by the cadence (2 of 56 days, 68 of 500 merges).

<!-- sweep-scope: corpus -->

**Read in full, all 68.** Nine `spec-writer` reads ran in verify mode, split
by area, each reading every file in its area against the code it describes.
None edited a file. **This sweep changed no file in scope.** Every
divergence is in `guide/archive/findings_2026-10-03_corpus.md` with who decides it;
act from the register. This record says what was read and what was found,
file by file.

## 0. Carried forward

All 242 findings of the 2026-10-01 register are closed: done, carried to a
named checklist, deferred with Rehydrate, or declined. Re-reading them found
nine whose fix was partial or has drifted back, now re-opened in the new
register:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| H21, H24: retire the two superseded Azure runbooks | 2026-10-01 | 2 d | re-opened | Bannered, not retired; "Done in #2738" overstated it. |
| F5, F10, F11, F20, F22 | 2026-10-01 | 2 d | re-opened | Fixed in some files, not all (F3, F11, F2, F22, F26). |
| E9, E35 | 2026-10-01 | 2 d | re-opened | Provenance and tallies remain in `ui_elements.md` and the button audit. |
| D12, D27 | 2026-10-01 | 2 d | re-opened | A helper name and a test tally. |
| B19 = G6 | 2026-10-01 | 2 d | carried | Scheduled sends only on Session Home; awaits Azure. |
| D16, D18 | 2026-10-01 | 2 d | carried | Deferred with Rehydrate. |
| Tier 2 #6, #8; Tier 3 #10–12 | 2026-05-11 | 145 d | declined | Unchanged; their triggers have not happened. |

## 1. Write or deepen

- `sessions_overview.md`: the archived-sessions page (C20).
- `operator_button_audit.md`: about 20 controls with no row (E30).
- `ui_elements.md`: `.card-columns`, `.pill-role-*`, the skip link.
- `rrw_functional_spec.md`: dashboard columns (G12), Create's Quick Setup card (G13), relationship moves (G18).
- `setup_pages.md`: the Relationships gate and the Observers `CohortRule` column (C21, C22).
- `reviewer-surface.md`: the help-contact header and `observe_deadline` (A23, A24).
- `instruments.md`: the expanded card's top button row (A21).
- `lifecycle.md`: the selected-response loss acknowledgement (B25).
- `validate_page.md`: two checks' preconditions (B32).
- `settings_inventory.md`: operator flags, the clear-all card, `activated_at` (D25).
- `email_template_editor.md`: the composer's From and To rows (D29).
- `visual_style_general.md`: two override rows (E22).

## 2. Update in place

Ids are in the findings register. A **bold** count means a medium-or-higher
finding is among them.

- `spec/instruments.md`: 3, plus provenance (A20–A22).
- `spec/reviewer-surface.md`: **13**, plus provenance (A7–A16, A23–A25).
- `spec/participant_model.md`: 2 (A17, A18).
- `spec/visibility_policy.md`: 2, plus provenance (A18, A19).
- `spec/sort_by_reviewee.md`: provenance only.
- `spec/assignments.md`: **9** (B5–B13).
- `spec/workflow_card.md`: 4 (B14–B17).
- `spec/lifecycle.md`: **11** (B18–B28).
- `spec/validate_page.md`: **5** (B29–B33).
- `spec/reconciling_regeneration.md`: 1 (B34).
- `spec/setup_pages.md`: **5**, plus heavy provenance (C6, C7, C16, C21, C22).
- `spec/quick_setup_card_spec.md`: 3 (C8–C10).
- `spec/session_home.md`: 3 (C11, C15, C18).
- `spec/sessions_overview.md`: **4**, and the code defect C1 (C12, C13, C20, C23).
- `spec/timezone_display.md`: 1, and the code defect C3 (C14).
- `spec/session_owners.md`: 1 (C17).
- `spec/csv_contracts.md`: **6**, the two code defects D1 and D2, and the heaviest provenance (D7–D12).
- `spec/extract_data.md`: **4** (D13–D16).
- `spec/roundtrip_coverage.md`: 1 (D17).
- `spec/rehydrate.md`: **4** (D18–D21).
- `spec/settings_inventory.md`: **6** (D22–D27).
- `spec/email_template_editor.md`: 3 (D28–D30).
- `spec/ui_elements.md`: **13** (E1–E13).
- `spec/color_tokens.md`: 3 (E14–E16). All 80 primitives, 106 semantic rows, 16 scale tokens and every cited ratio match.
- `spec/visual_style_rrw.md`: **5** (E17–E21).
- `spec/visual_style_general.md`: 3 (E22–E24).
- `spec/operator_ui_concept.md`: **5** (E25–E29).
- `spec/operator_button_audit.md`: **5** (E30–E34).
- `spec/architecture.md`: **7** (F1–F7).
- `spec/permissions.md`: 5 (F8–F12).
- `spec/audience_and_identity_model.md`: **3** (F13–F15).
- `spec/role_navigator.md`: 3 (F16–F18).
- `spec/domain_assumptions.md`: 2 (F19, F20).
- `spec/operations_pages.md`: 4 (F21–F24).
- `spec/email_infra_options.md`: **3** (F26–F28).
- `spec/README.md`: 2 (C19, F29).
- `spec/rrw_functional_spec.md`: **19** (G1–G19).
- `docs/security_posture.md`: **6** (H1, H4–H8).
- `docs/architecture.md`: **3** (H9–H11).
- `docs/deployment_nus.md`: **3** (H12–H14).
- `docs/cli_setup.md`: 1 (H15).
- `docs/local_setup.md`: 3 (H2, H3, H19).
- `docs/deployment_dev.md`: 2 (H20, H22).
- `docs/database.md`: 1 (H21).
- `docs/status.md`: **7** (I1–I6, I8). Its live sections, not the timeline.
- `docs/known_limitations.md`: 1 (I7).
- `docs/unenforced_conventions.md`: 1 (I16).
- `README.md`: 4 (I9–I12).
- `CLAUDE.md` / `AGENTS.md`: 2 (I13, I14).
- `CONTRIBUTING.md`: 1 (I15).
- `rrw_sdd_in_practice.md`: 2 (I17, I18).
- `constitution.md`: 1, wording (I18).
- `azure_ask.md`: 1 (I19).

## 3. Consolidate

- `preview_hub.md` into `operations_pages.md`, keeping a stub (`app/web/spec_registry.py` maps it).
- The Extract Setup card contract: `extract_data.md` or `session_home.md`, not both (D15).
- `settings_inventory.md`'s precedence block becomes a pointer to `csv_contracts.md` (D26).
- `ui_elements.md`'s "Cross-cutting rules" section (E12).
- `deployment_nus.md` §3 becomes a pointer to `docs/nus_azure_status_v7.md` (H13).

## 4. Retire

- `docs/azure_provision.md` (re-opened H21); repoint its inbound references, listed in the register, first.
- `docs/azure_github_setup.md` (re-opened H24); likewise.
- `rrw_functional_spec.md` §12.4 and §12.5 stubs (G15), and the "Pause" sentences (G3).
- `setup_pages.md`'s stale cap paragraph (C7).
- `ui_elements.md`'s entries with no markup (E1), with their dead CSS.

## 5. Move

- `operations_pages.md`'s measurements to `guide/app_responsiveness.md` (F22, re-opened).

## 6. Read, no action

- `spec/role_landing_and_visibility.md`.
- `spec/blob_storage.md`: `app/services/blob_store.py` is a planned path, escaped and correct.
- `spec/sort_by_reviewee.md`: matches the code; provenance only.
- `docs/backup_restore.md`: current for the dev slot (H23 is the cutover gap).
- `docs/operations_runbook.md`: current for the dev slot.
- `docs/troubleshooting.md`: current for the dev slot.
- `docs/nus_azure_status_v7.md`.
- `docs/README.md`.
- `new_project_practices_setup.md`.
- `rrw_design_rationale.md`.
- `docs/archive/practice-audit-2026-09-04.md`: a dated record, read as history.
- `docs/status_history.md`: a dated record, read as history.

## 7. Not read

None. Read but **not verified**:

- Browser-only behavior: layout, widths, hover and focus, the builder, data
  shaper and reviewer-surface scripts, and the 6px rail.
- Azure-side state, secrets, branch protection and CI timings.
- Rehydrate end to end (gated off) and Postgres-only behavior.
- `docs/status.md`'s timeline rows, line by line.

## Mechanical entry points

- **Staleness.** 5 of 68 files untouched since 2026-10-01; 33 were edited
  this week, most by the previous register's fixes.
- **Dropped commitments.** 707 of 719 committed paths honored; 9 of the 12
  misses no longer exist. Unchanged since the last sweep.
- **Orphan specs.** The same 17 as last time; none surprised.
- **Dead references.** Two live candidates: `spec/blob_storage.md` →
  `app/services/blob_store.py`, a planned file, and
  `docs/security_posture.md` → `docs/authentication.md`, a lineage note
  (H8). The rest are dated history in `docs/status.md`.
- **App diff since 2026-10-01.** 85 files, 205 commits since `68f28224`.

## Headline numbers

| | |
|---|---|
| In scope | 68 (40 `spec/`, 19 `docs/`, 9 root) |
| Read | 68 |
| Findings | about 236 (write 25 / update ~190 / consolidate 5 / retire 6 / move 1), many of them provenance strips |
| Code defects | 13, plus stale comments and dead CSS (register §1) |
| Rulings needed | about 40 (register §2) |
| Carried in / closed / still open | 242 / 242 / 9 re-opened, 3 carried, 3 declined |

**What this sweep says.** Two days after a sweep that found 242 findings
and fixed them all, a full re-read found about as many again. They are a
different kind. Few are new drift: most are provenance, tallies and
measurements that the specs' own rule forbids, or the far side of a fix
that reached one file and not the next (nine re-opened). The code defects
are fewer and sharper. One loses data on an ordinary action: saving a
draft in the lobby expander resets its schedule, invite and reminder
offsets, release window and roster toggles (C1). Two answer a malformed
Settings CSV with a 500 or a silently mistyped field (D1, D2). The weakest
document is again `docs/status.md`, whose live sections describe UI that
has been retired and whose timeline stops at #2718.
