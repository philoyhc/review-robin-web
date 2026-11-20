# Sweep — corpus (2026-11-20)

**Swept:** 2026-11-20 at `6003c8084` (#4063) · **Scope:** `spec/`, `docs/`, the root
practice docs, `cordware/spec/`, and, for the first time, each application
package's `spec/` and `docs/` (83 files) · **Previous sweep:**
`guide/archive/sweep_2026-11-06_window.md` (partial); last corpus sweep
`guide/archive/sweep_2026-10-22_corpus.md` · **Trigger:** due by the cadence, 681
merges of 500 since 2026-10-22 (29 of 56 days).

<!-- sweep-scope: corpus -->

Seven `spec-writer` reads ran in verify mode, split by area. None edited a file;
**this sweep changed no file in scope.** The four area reads were:

- S1, the operator and setup specs;
- S2, data, participants, interop and style;
- S3, `docs/`, the root and `cordware/spec/`;
- S4, the packages.

S1 and S2 checked their files' claims mechanically: routes, gates, events,
Validate rules, schema, columns, labels and tokens. They read only the changed
prose in full, so three more reads finished the prose a corpus marker needs:

- S1b: `lifecycle.md` and `workflow_card.md`;
- S1c: `assignments.md`, `instruments.md` Bands 2–3 and `operations_pages.md`;
- S2b: `reviewer-surface.md`, `audience_and_identity_model.md`, `csv_contracts.md`
  §3.3 and the two visual-style specs.

Every divergence is a row of `guide/findings_2026-11-20_corpus.md` (64 rows), or,
for a package, of that package's own `guide/findings_2026-11-20.md` (Apply
Desk 7, Residential 10, Utilities 3). The codebase assessment ran beside it at the
same commit, `guide/codebase_assessment_20nov.md`; its defect read reproduced B1.

The mechanical passes found:

- no dead cross-reference in `spec/`;
- no surprising orphan, since every unmapped spec is cross-cutting or a model, and
  `linked_sessions.md` is pinned by `tests/unit/test_linked_sessions_spec.py`;
- package registries that map every routing module to a live spec;
- 2,195 unit tests passing at the pin.

## 0. Carried forward

The 2026-11-06 window sweep's register was archived with nothing open. The prose
it did not reach is read here.

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| old D4: `responses_import._stage` overwrites duplicate rows | 2026-10-03 | 48 d | carried | Rehydrate, `guide/deferred_consolidated.md`. |
| old D19: Rehydrate is incomplete | 2026-10-01 | 50 d | carried | Same entry. |
| 2026-11-06 "not reached": the functional spec, `security_posture.md`, `local_setup.md`, `identity.md`, `architecture.md`, `extract_data.md` from line 1084 | 2026-11-06 | 14 d | done | Read here: F1, F2, H5, H6, H11, F3. |

## 1. Write or deepen

- `spec/reviewer-surface.md`: the dropped-fields notice on the real surface (A6).
- `spec/workflow_card.md`: the handoff's `return_to` (B10).
- `spec/rrw_functional_spec.md`: linked sessions, handoffs, Unlink and owner reports (author F1).
- `spec/operations_pages.md`: the per-reviewer drill-in, or its retirement (author B6).

## 2. Update in place

Ids are in the register; a **bold** count includes a medium finding.

- `spec/lifecycle.md`: **6** (B2, B4, B5, B7, B8, B9), plus trim B20.
- `spec/workflow_card.md`: **2** (B1, B3), plus trim B20.
- `spec/assignments.md`: 6 (B11–B16).
- `spec/operations_pages.md`: 2 (B17, B18), plus trim B20.
- `spec/permissions.md`: 1 (B19).
- `spec/instruments.md`, `spec/session_home.md`, `spec/setup_pages.md`: trim B20.
- `spec/reviewer-surface.md`: 7 (A1–A5, A7, A8).
- `spec/participant_model.md`: 1 (A9).
- `spec/audience_and_identity_model.md`: 3 (A11–A13), plus trim E9.
- `spec/README.md`: 1 (A10), plus trim D2.
- `spec/csv_contracts.md`: 1 (D1), plus trim D2.
- `spec/handoffs.md`, `spec/rehydrate.md`: trim D2.
- `spec/visual_style_rrw.md`: **8** (E1–E8; E1–E3 are for the author).
- `spec/ui_elements.md`, `spec/visibility_policy.md`, `spec/email_infra_options.md`: trim E9.
- `spec/architecture.md`: 1 (F3), plus trim F4.
- `spec/rrw_functional_spec.md`: 1 (F2), plus trim F4.
- `cordware/spec/host.md`: 1 (F5), plus author H3.
- `docs/README.md`: 1 (H1).
- `docs/deployment.md`: 1 (H4).
- `docs/local_setup.md`: 2 (H5, H6).
- `docs/security_posture.md`: 2 (H2, H11).
- `docs/unenforced_conventions.md`: 1 (H10).
- `docs/operations_runbook.md`: 1 (H14).
- `docs/performance.md`: 1 (H15).
- `README.md`: 3 (H7–H9).
- `rrw_design_rationale.md`: 1 (H2).
- `rrw_sdd_in_practice.md`: 1 (H12).
- `new_project_practices_setup.md`: 1 (H13).
- The packages: Apply Desk's `spec/applications.md`, `spec/architecture.md` and
  `docs/photo_field_design.md`; five Residential specs and docs and its README;
  Utilities' two specs and its README. See each package's register.

## 3. Consolidate

- `docs/header_chrome.md` into `spec/visual_style_rrw.md` "Top bar", or retire it (author H1).

## 4. Retire

- History in Residential's identity docs (Residential S3) and its pre-units roster
  doc's vocabulary (Residential S2), by author decision.

## 5. Move

- `docs/header_chrome.md`, as §3.

## 6. Read, no action

- **`spec/`:** `quick_setup_card_spec.md`, `sessions_overview.md`,
  `validate_page.md` (29 rules, key and severity, match), `session_owners.md`,
  `settings_inventory.md`, `extract_data.md`, `email_template_editor.md`,
  `sort_by_reviewee.md`, `operator_button_audit.md` (262 rows resolve),
  `operator_ui_concept.md`, `roundtrip_coverage.md`,
  `role_landing_and_visibility.md`, `linked_sessions.md`, `timezone_display.md`,
  `visual_style_general.md`, `color_tokens.md` (the 80 · 101 · 14 tally a test
  reads).
- **`docs/`:** `sample_data/basic_cohort/README.md`, `setup_codespaces.md`,
  `database.md`, `interoperability_example.md`.
- **Root:** `constitution.md`, `CONTRIBUTING.md`, `CLAUDE.md` / `AGENTS.md`
  (twins identical).
- **`cordware/spec/`:** `identity.md`.
- **The packages:** Residential's `docs/residentialapps_roles.md` and
  `docs/support_logs_confidentiality.md`; Apply Desk's v0.6b baseline and
  Utilities' four frozen documents, all correctly treated as frozen.

## 7. Not read

- **Instruments page script:** the browser-side behavior in `instruments_index.html`
  (chips, the `newModel*` and `rf*` functions, previews, width staging, branch
  rows), checked to the hooks only.
- **Other client-only behavior:** the top bar's menu keyboard and focus, the
  under-640 px breadcrumb collapse, the navigation busy indicator.
- **`spec/csv_contracts.md` §3.3**, spot-traced rather than read rule by rule:
  the offsets rules, `rules_json` and `unrepresented_rule` refusals,
  `_branch_errors`, Quick Setup's 422 rendering, the held-file cap and the
  formula guard.
- **Spot-checked only:**
  - `spec/ui_elements.md`'s element catalogue CSS values (sampled);
  - the participant `/results` and `/collation` renders;
  - the 21-column summary CSV;
  - the Accounts badge.
- **Unbuilt:** `spec/email_infra_options.md` Options B–D.
- **Not checkable from this repository:** the private deployment's facts
  (Easy Auth, Key Vault, Application Insights, what production mounts).

## Headline numbers

| | |
|---|---|
| In scope | 83 (58 RRW `spec/`, `docs/` and root; 2 `cordware/spec/`; 23 package) |
| Read | 83 (with §7's parts spot-checked) |
| Findings | 84: RRW 64 (code 3, author 11, write 2, update 42, trim 6), packages 20 (author 4, the rest per file) |
| Medium | 5: B1, B4, E1, E2, E3; medium-low: H6, and Residential S2, S8, S9 |
| Carried in / closed / still open | 3 / 1 / 2 |

## Entry-point commands

- **Staleness and the trigger:** `python3 tools/close_check.py --stale` (due: 681
  of 500).
- **Dropped commitments:** `python3 tools/close_check.py --archived`.
- **The window:** `git diff --stat 00501f2e..6003c8084 -- spec docs cordware/spec '*.md'`.
