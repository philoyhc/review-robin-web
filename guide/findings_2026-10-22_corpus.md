# Findings — corpus sweep (2026-10-22)

**Found by:** `guide/sweep_2026-10-22_corpus.md` · **Read at:** `00501f2e`
(#3225) · **Open:** 21 of 59 rows (F2, D1, D2, D10, B7 and E8 done in #3239; B1–B6 in #3240; A1–A3, D3–D9 in #3241; E1–E7 in #3244; F1, F3–F9 in #3245; F11 in #3247); every author row ruled 2026-10-22, as
recommended in §2.

Every spec, `docs/` file and root document, and the two `cordware/spec/`
files, was read against the code it describes, in six verify-mode reads
split by area, plus a seventh that read the four long documents the
first six only spot-checked (H12–H21). **Nothing in scope was edited.** A sweeper may not
re-align a spec to the code (`rrw_sdd_in_practice.md` §4), so each
divergence is listed here and the fixes ship afterwards as ordinary PRs.
A row is struck when it is done, with the PR that did it, or marked
declined with the reason. Code defects found by reading the code for
bugs, rather than the specs for drift, are in the sibling register
`guide/findings_2026-10-22_bugs.md`.

**Ids** carry the area of the read: **A** instruments, the reviewer and
participant surfaces · **B** lifecycle, Session Home, the lobby,
assignments, Validate · **D** data in and out · **E** UI and visual style
· **F** architecture, permissions, identity, the functional spec and the
Cordware specs · **H** `docs/` and root documents. They restart at 1 in
this file. **Severity** is the reader's. **Decides:** *spec* means the
spec is wrong and an update in place fixes it; *code* means the code is
wrong against a spec that is right; *author* means a choice between
fixing the code and changing the contract; *trim* means provenance or a
tally to strip, keeping the reason it carried. In `docs/` and root rows,
*doc* plays the part of *spec*. Line numbers are at `00501f2e`.

## 1. Code defects

- ~~**F2**~~ — **Done in #3239**: production logs a `WARNING` record (`audit.detail_schema_violation`) that names no value (`tests/unit/test_audit_detail_schema.py`). (low–medium, code) — `spec/architecture.md` says a schema
  violation in production "logs and writes through"; the code calls
  `warnings.warn` (`app/services/audit.py:207`, `:1108`) and nothing
  captures warnings, so the JSON log never sees one.
- ~~**D1**~~ — **Done in #3239**: a shared short label falls back to the positional key (`tests/integration/test_responses_import.py`). (medium, author) — **Ruled 2026-10-22: fall back to the positional key when two short labels collide; no uniqueness rule.** Rehydrate matches instruments by
  `InstrumentShortLabel`, which `spec/rehydrate.md` §6.4 calls unique per
  session; nothing enforces it (`spec/settings_inventory.md` §10 says
  labels need not be unique), and `{short_label: instrument}` lets the
  last of two shared labels win, loading responses onto the wrong
  instrument. Rehydrate is gated off. Enforce uniqueness, or fall back to
  the positional key on ambiguity.
- ~~**F9**~~ — **Done in #3245**: (low, author) — **Ruled 2026-10-22: loosen the spec to what the code does.** `cordware/spec/identity.md` reads the
  `X-MS-CLIENT-PRINCIPAL-NAME` header as the name's last fallback; the
  code reads it only when no email was found. Fix the code or loosen the
  spec.
- ~~**E8**~~ — **Done in #3239**: both comments, and a third above them; the theme customizer regenerated. (low, code) — two stale `base.html` comments: `.rs-help-card`
  cites a §"Reviewer help cards" `spec/ui_elements.md` no longer has, and
  `.tab-strip-page` claims to match a tint the spec says it differs from.
- ~~**B7**~~ — **Done in #3239**: `app/web/spec_registry.py`. (low, author) — **Ruled 2026-10-22: map it to the `_session_home` routing module.** `spec/session_owners.md` maps to no routing
  module in `app/web/spec_registry.py`, so `close_check` never flags an
  owners-route change against it. Add it to the `_session_home` tuple.

## 2. For the author

All ruled 2026-10-22, each as its row records.

- **H1, H2** — the docs that describe the dormant dev slot as live (H1),
  and `CONTRIBUTING.md`'s reason for waiting on CI (H2), whose premise —
  every push to `main` migrates Azure Postgres — is false while the slot
  is disabled. Restate as conditional, or leave until the slot resumes.
- **H4, H5** — `docs/deployment_nus.md` §3's start command, and whether
  `docs/cordware_stage0_baseline.md` stays as a dated record (retitle its
  "Command today" column) or archives.
- **H10, H11** — dated measurements and "serves today" in
  `rrw_sdd_in_practice.md` and `rrw_design_rationale.md`: re-take, or
  drop the tally.
- **F11** — the functional-spec trim (below), proposed by the 5 and 16
  October assessments and not yet done.
- ~~**E5**~~ — **Done in #3244**: — **Ruled 2026-10-22: retire the section.** `spec/visual_style_rrw.md` "Sign-in surface" describes an
  in-app sign-in page and magic links that do not exist: mark deferred,
  or retire the section.
- ~~**D10**~~ — **Done in #3239**: `portable_band2_state` drops the ids on export, Duplicate and import (`tests/integration/test_session_clone.py`). — **Ruled 2026-10-22: strip the sample-group ids on export and clone.** `band2_state` carries source-session reviewee ids through the
  Settings CSV and clone, marked ✅ in `spec/roundtrip_coverage.md`
  (unverified harm; likely preview only).

## 3. Per-file findings

**`spec/` — participant (A)**

- ~~**A1**~~ — **Done in #3241**: `spec/sort_by_reviewee.md`. (low, spec) — `spec/sort_by_reviewee.md` "Locked / unlocked":
  the Group header on a group-scoped Band 2 preview shows no `↕` when
  locked and unsorted; the rule needs that exception.
- ~~**A2**~~ — **Done in #3241**: `spec/timezone_display.md`. (low, spec) — `spec/timezone_display.md` "Rendering format"
  omits the summary caption, the pre-open lines and the refused-write
  notice; state the rule rather than the list.
- ~~**A3**~~ — **Done in #3241**: five specs trimmed; revision ids naming a column kept. (low, trim) — provenance (participant-audit ids, finding ids,
  dated rulings, "19V Item 2") in `spec/reviewer-surface.md` (most),
  `spec/role_landing_and_visibility.md` §4, `spec/participant_model.md`
  §4–§5, `spec/instruments.md`, and a migration-history paragraph in
  `spec/visibility_policy.md` §3.1. Keep revision ids that name a column.

**`spec/` — sessions (B)**

- ~~**B1**~~ — **Done in #3240**: `spec/lifecycle.md` §3.1 and §5 drop the tally. (medium, spec) — `spec/lifecycle.md` §3.1 and §5 say eight
  Observers routes take `_require_not_archived`; there are nine
  (`self-fields`). Drop the tally.
- ~~**B2**~~ — **Done in #3240**: `spec/session_home.md`. (low, spec) — `spec/session_home.md` lifecycle table: Release
  responses is never live in `ready`.
- ~~**B3**~~ — **Done in #3240**: `spec/validate_page.md` §1, §5.3 and §9.6. (medium, spec) — `spec/validate_page.md` §1, §5.3 and §9.6 say
  the GET writes nothing; it runs the scheduled-event pass
  `spec/lifecycle.md` §8.3 requires. Add the exception, no wider.
- ~~**B4**~~ — **Done in #3240**: `spec/workflow_card.md`. (low, spec) — `spec/workflow_card.md` cites a nonexistent
  `is_prepared`; the check is inline in `_fire_invite_entry`.
- ~~**B5**~~ — **Done in #3240**: `spec/sessions_overview.md`. (low, spec) — `spec/sessions_overview.md`: `validated` counts as
  draft in the lobby pills.
- ~~**B6**~~ — **Done in #3240**: `spec/lifecycle.md` §3.1: the email-template editor is now the sixth. (low, spec) — `spec/lifecycle.md` "six exceptions" lists five.

**`spec/` — data (D)**

- ~~**D2**~~ — **Done in #3239**: `spec/rehydrate.md` §6.4, with D1. (low, spec) — `spec/rehydrate.md` §6.4: `instrument_{n}` is the
  n-th by (order, id), not `order = n`.
- ~~**D3**~~ — **Done in #3241**: `spec/settings_inventory.md` §7. (low, spec) — `spec/settings_inventory.md` §7 omits
  `sessionHomeScrollY:{pathname}`.
- ~~**D4**~~ — **Done in #3241**: `spec/settings_inventory.md` §2, §4 and §10, `spec/roundtrip_coverage.md`. (low, spec) — `spec/settings_inventory.md` §2 and
  `spec/roundtrip_coverage.md` omit `sessions.public_id`,
  `sessions.form_key`, the instrument reconcile-cache columns and
  `uq_instruments_session_seq`.
- ~~**D5**~~ — **Done in #3241**: `spec/rehydrate.md` §6.2. (low, spec) — `spec/rehydrate.md` §6.2 omits the rule-set
  refusals an older extract meets at the settings apply.
- ~~**D6**~~ — **Done in #3241**: `spec/email_infra_options.md`. (low, spec) — `spec/email_infra_options.md` Option A: port 587
  is a placeholder, not a default.
- ~~**D7**~~ — **Done in #3241**: `spec/extract_data.md`. (low, spec) — `spec/extract_data.md`: the chip state is keyed to
  the session's `public_id`.
- ~~**D8**~~ — **Done in #3241**: `spec/csv_contracts.md` §3.2. (low, spec) — `spec/csv_contracts.md` §3.2 omits Save's
  `acknowledged_loss`.
- ~~**D9**~~ — **Done in #3241**: five specs trimmed. (low, trim) — provenance in `spec/csv_contracts.md`,
  `spec/settings_inventory.md`, `spec/roundtrip_coverage.md`,
  `spec/rehydrate.md` and `spec/setup_pages.md`.

**`spec/` — UI (E)**

- ~~**E1**~~ — **Done in #3244**: (low–medium, spec) — `spec/operator_button_audit.md` has no row
  for the date-time field's 📅 and ✕ buttons (and perhaps the pager
  steps).
- ~~**E2**~~ — **Done in #3244**: (low, spec) — `spec/visual_style_rrw.md` cites a Rule Based
  Assignment card that does not exist.
- ~~**E3**~~ — **Done in #3244**: (low, spec) — `spec/visual_style_rrw.md`: the Responses summary
  card's pills are wrong.
- ~~**E4**~~ — **Done in #3244**: (low–medium, spec) — `spec/visual_style_rrw.md` "Page header"
  (response surface) predates the shipped header; point at
  `spec/reviewer-surface.md` and mark the institution name deferred.
- ~~**E6**~~ — **Done in #3244**: (low, trim) — provenance in `spec/ui_elements.md`,
  `spec/operator_button_audit.md`, `spec/visual_style_rrw.md` and
  `spec/operator_ui_concept.md`.
- ~~**E7**~~ — **Done in #3244**: (low, trim) — tallies in `spec/ui_elements.md` and
  `spec/operator_ui_concept.md` (not `spec/color_tokens.md`'s, which a
  test parses).

**`spec/` and `cordware/spec/` — architecture (F)**

- ~~**F1**~~ — **Done in #3245**: (low, spec) — `spec/architecture.md` "Three-layer split" names
  `Instrument.session_seq` as the only querying column default;
  `ReviewSession.public_id` is a second.
- ~~**F3**~~ — **Done in #3245**: (low, write) — `spec/architecture.md` is silent on the app-wide
  `refuse_oversized_ids` dependency.
- ~~**F4**~~ — **Done in #3245**: (low, spec) — `spec/permissions.md` attributes identity to
  `app/auth/identity.py` (Cordware resolves it) and never says
  `{session_id}` is the `public_id`.
- ~~**F5**~~ — **Done in #3245**: (low–medium, spec) — `spec/audience_and_identity_model.md` §4:
  Accounts is multi-select with an all-or-nothing batch, not one user at
  a time.
- ~~**F6**~~ — **Done in #3245**: (low, spec) — `spec/audience_and_identity_model.md` `/guide`
  audiences: an archived session discloses no role.
- ~~**F7**~~ — **Done in #3245**: (low–medium, spec) — `spec/README.md` does not index the two
  Cordware specs, and its `architecture.md` row omits URL emission and
  the mount.
- ~~**F8**~~ — **Done in #3245**: (low, spec / author) — **Ruled 2026-10-22: fix §4.3, and add a row for the Cordware specs to §19.** `spec/rrw_functional_spec.md` §4.3 says
  the invitation link signs a reviewer in (it never does); §19 omits the
  Cordware specs (author: add a row or soften "every live spec").
- ~~**F11**~~ — **Done in #3247**: (low, author) — **Ruled 2026-10-22: trim it, carried by the spec-update PRs.** `spec/rrw_functional_spec.md` sections that
  restate a narrower spec: §9.1, §9.3–9.7, §9.9–9.15, §10.3–10.10,
  §11.2–11.5, §12.2–12.4, §6.1–6.3 and §16, §4.1, §7.3 and §17. Keep §1–3,
  §5, §8, §13, §14, §18, §19. Do not cut the §6 table a doc-convention
  test reads, nor renumber the sections other files cite (§9.5, §10.3,
  §11, §11.6).

**`docs/` and root (H)**

- **H1** (medium, author) — **Ruled 2026-10-22: restate as "when the slot is live".** `docs/operations_runbook.md`,
  `docs/known_limitations.md`, `docs/deployment_nus.md` §0,
  `docs/database.md`, `docs/troubleshooting.md` and
  `docs/backup_restore.md` describe the dev deploy as live; it is
  disabled (`docs/deployment_dev.md` is right).
- **H2** (medium, author) — **Ruled 2026-10-22: restate the reason as conditional; keep the policy.** `CONTRIBUTING.md` "When to wait for CI":
  the migration premise (above); also its checklist says `pytest` where
  `CLAUDE.md` requires `-n auto` and `ruff`.
- **H3** (medium, doc) — "Segment 21, on hold" is stale in
  `docs/README.md`, `docs/architecture.md`, `docs/known_limitations.md`
  and `docs/deployment_nus.md`'s banner.
- **H4** (medium, author) — **Ruled 2026-10-22: fix the command.** `docs/deployment_nus.md` §3 starts
  `app.main:app`, which does not exist; it is `cordware.main:app`.
- **H5** (low–medium, author) — **Ruled 2026-10-22: keep it as a dated record; retitle the column "at `b03fd1be`".** `docs/cordware_stage0_baseline.md`
  "Command today" and its line citations have moved (above).
- **H6** (low, doc) — `docs/local_setup.md` §2 omits `cordware/`; §3 and
  §8 name `/docs`, now `/reviewrobin/docs`.
- **H7** (low–medium, doc) — `docs/security_posture.md`,
  `docs/deployment_nus.md` §4 and `docs/architecture.md` attribute the
  Easy Auth parser to `app/auth/identity.py`; it is `cordware/identity.py`.
- **H8** (low, doc) — the deployed environment tables omit
  `CORDWARE_APPS`.
- **H9** (low, doc) — `docs/deployment_dev.md` "Resuming the dev slot":
  every "once 21x lands" has landed.
- **H10** (low, author) — **Ruled 2026-10-22: date each figure rather than re-take it.** `rrw_sdd_in_practice.md` appendix "4,800 tests"
  and `CLAUDE.md`'s 172 s are dated measurements.
- **H11** (low, author) — **Ruled 2026-10-22: date it, with H18.** `rrw_design_rationale.md` §6.6: the dev slot
  "serves today"; §7 also calls it "the only live environment" (H18).
- **H12** (medium, doc) — `docs/cordware_repository_strategy_v0.8.md` §3
  still says, in decision-time "today" sentences, that nothing enforces
  the fake-auth guard and that RRW writes root-path links; both shipped
  (`cordware/main.py`, `app/web/urls.py`). Its §8 ledger is right.
- **H13** (low, author) — **Ruled 2026-10-22: label the tree as the target layout.** the strategy's §2 tree lists `cordware/AGENTS.md`,
  `docs/`, `guide/`, `tools/` and `deployment/` (none exist) and omits
  `cordware/settings.py` and `cordware/logging.py`; it says the root
  `AGENTS.md` routes work by owner, which it does not. Label the tree as
  the target, or add the routing.
- **H14** (low, doc) — the strategy's §5: the NUS workflow also packages
  `pyproject.toml`.
- **H15** (low–medium, doc) — `docs/cordware_nus_azure_status_2026-10-16_v8.md`
  §4.3 says the landing page shows only eligible applications; it lists
  every mounted one (`cordware/web/landing.py`), as the strategy says.
- **H16** (low, author) — **Ruled 2026-10-22: extend the banner.** the status record's banner misses §1, §18.5,
  §21 and §22 step 4 (a Cordware repo and federated credential the
  strategy dropped), and §21's "RRW Cordware retrofit: Not started"
  (Segment 21 shipped it). Extend the banner.
- **H17** (medium, doc) — `docs/deployment_nus.md` §1, §3, §5 and §13
  cite headings of the v7 status record that v8 does not have; the v8
  equivalents are §8.1, §12.1, §16.1 and §18.1–18.2.
- **H18** (low, doc) — `rrw_design_rationale.md` §7: "the only live
  environment" (with H11).
- **H19** (low, doc) — `rrw_design_rationale.md` §6.3 and its appendix
  spell the visibility modes as prose; `CLAUDE.md` asks for the shipped
  `Anonymized` / `Summarized`.
- **H20** (low, doc) — **Ruled 2026-10-22: date each figure.** `rrw_sdd_in_practice.md` §1 ("two thousand six
  hundred pull requests", undated) and §6.7 (`CLAUDE.md` "297" lines, now
  309): date or drop.
- **H21** (low, author) — **Ruled 2026-10-22: one pointer to the strategy in each.** neither narrative document says RRW now runs
  under the Cordware host, which parses identity; one pointer to the
  strategy would do.
