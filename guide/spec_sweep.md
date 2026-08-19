# Spec sweep — drift audit (2026-08-18)

A whole-`spec/` sweep comparing every surface spec against the shipped code.
Ran as 8 parallel audit passes over the 34 files in `spec/`. Two outcomes:

- **Code went beyond spec** (spec stale / behind reality) → the spec files were
  **updated in place** in the same sweep (see the accompanying diff across
  `spec/`). Not re-listed here except the two cross-cutting cases in §B that
  were too large for surgical edits.
- **Code falls short of what the spec intended** (unfinished / never-wired
  work) → recorded below in **§A**. These are the actionable follow-ups.

§C collects minor / cosmetic non-drift notes for completeness.

---

## A. Unfinished work — code falls short of spec

Each was a place where the spec described a behaviour that wasn't fully wired.
**All three resolved in 18R Item 3 (2026-08-18)** — see resolution notes.

1. **`.btn.primary-outline` style documented but not implemented.**
   ✅ **RESOLVED (18R Item 3).** `spec/operator_button_audit.md` (entry #56)
   documented **+Instrument** as **"Primary Outline"** via `btn primary-outline`,
   and `instruments_index.html` used that class — but `base.html` defined **no
   `.btn.primary-outline` rule**, so `+Instrument` *and* its sibling **+Page
   break** fell back to solid Primary blue. Fixed by reclassifying both buttons
   to plain **`btn secondary`** in the template, and updating the button audit
   (entry #56 → Secondary; added #56b for +Page break). No new CSS rule needed.

2. **Instruments "Open / close all" bulk button unwired.**
   ✅ **RESOLVED (18R Item 3) — deprecated.** `spec/instruments.md` documented an
   **"Open / close all"** bulk control (flip `accepting_responses` across
   instruments) whose routes `/instruments/accepting/all-{on,off}` +
   `bulk_set_accepting` service existed, but **no template control drove them**.
   Dropped from the spec and removed: the two routes, the `bulk_set_accepting`
   service + export, the `instruments.bulk_accepting_responses` audit schema, and
   the dead `bulk_accepting_state` view field. Per-instrument Open/Close remains
   the accepting control. *(The sibling session-level "Show / hide all when
   closed" bulk visibility toggle was removed in the same slice — visibility when
   closed is now governed by the per-instrument visibility policy; the
   `bulk_set_visibility` route/service/audit-schema and the `bulk_visibility_state`
   view field went with it, and the `responses_visible_when_closed` column
   persists only for config round-trip.)*

3. **Reviewer-surface progressive-enhancement JS never wired.**
   ✅ **RESOLVED (18R Item 3) — spec updated to reality.** `spec/reviewer-surface.md`
   described three unbuilt client-side behaviours: (a) per-page **dirty-tracking**
   disabling Save until input; (b) an **in-place JS Discard**; (c) **JS page
   navigation** via `type="button"` + `history.pushState`. The templates carry the
   `data-rs-save` / `data-rs-discard` / `data-rs-saved-value` hooks but **no JS
   handler for any of them**. Updated the spec (§5, the button table, "How the
   surface works", "Save button state", and the beforeunload extensibility note)
   to the shipped **server-navigation** reality: Prev / "Page N of M" / Next
   `<a href>` links, a Discard `<a href>` GET reload, and an always-enabled Save
   submit — with the `data-rs-*` attributes documented as hooks reserved for a
   future dirty-tracking enhancement. *(`beforeunload` remains correctly out of
   scope.)*

---

## B. Spec currency debt — code beyond spec, too cross-cutting to fix surgically

Real "code moved ahead" drift, but woven across many interlocking sections;
the sweep left these for a coordinated section-level refresh rather than risk
piecemeal edits that leave the doc internally inconsistent.

**Both resolved 2026-08-18** by a thorough section-level revision of the two
docs (`rrw_functional_spec.md` currency → 2026-08-18; `architecture.md`
conceptual hierarchy rewritten). See the "Thorough revision" work landed
alongside this sweep.

1. ✅ **RESOLVED.** **`spec/rrw_functional_spec.md` needs a currency refresh** (its stated
   currency is 2026-05-22, ~3 months stale). Concretely:
   - **Response Type Definitions (RTDs) retired 2026-05-26** but still
     documented as a live core concept (§§4.2, 5.6, 5.7, 8.7, 9.6, 9.13, 12.2,
     Glossary). The `response_type_definitions` table + `_rtds.py` are gone;
     response fields now carry a plain `data_type` + quick-fill list presets
     (`instruments/_field_presets.py`), and Settings.csv emits no RTD section.
   - **Operator RuleSet *library* tier retired** (Wave 5) but still documented
     (§§4.2, 5.11, 8.7, 9.13 "Library RuleSets card"). Session-scoped seeded
     RuleSets + per-instrument pinning (`Instrument.rule_set_id`) still exist —
     only the operator-library tier is gone.
   - **Observer role + reviewee results surface + cross-role dashboard**
     (shipped 2026-05-30 → 06-03) are absent: §4 "four roles" is reviewer-only;
     §10 has no `/me/.../results`, `/me/.../collation`, or acknowledge gesture.
   - **Per-instrument rule engine** (Segment 13A/15B) shipped (`app/services/
     rules/`, per-instrument generation) but still framed as future.
   *(§§4.2 / 9.14 were freshly patched for 18S and read current.)*

2. ✅ **RESOLVED.** **`spec/architecture.md` — Conceptual-hierarchy section** still frames
   per-instrument rules / RuleBased as "the last remaining multi-instrument item
   (Segment 15B)" and assignments as "FullMatrix today, RuleBased in Segment
   13A", though the rule engine + per-instrument assignment generation shipped.
   (The observer-collation part of this file was corrected in the sweep.)

---

## C. Minor / cosmetic notes (non-actionable)

Left unedited — historical framing, single-shade colour near-misses, or
non-load-bearing path strings that resolve via package re-exports.

- **`preview_hub.md`** — segment/date attribution anachronism: the iframe-card
  retirement + `/preview` 308 → `/preview-surface/1` repoint are dated
  "2026-05-28 (PRs #1530/#1531)", but the code attributes the operator
  `/preview-surface` route + iframe retirement to **Segment 18Q**. The route
  can't have been a redirect target before it existed.
- **`lifecycle.md`** — the §1 ASCII state diagram still shows only
  draft ⇄ validated ⇄ ready (omits `ready → expired → draft`). The state table
  + new §2.7 now document `expired`; the art was left intact to avoid mangling.
- **`assignments.md`** — three literal `app/services/assignments.py` path
  strings are cosmetically stale (the service is now the package
  `app/services/assignments/`, 18O split); every function reference still
  resolves via the package `__init__` re-exports.
- **`visual_style_general.md`** — `accent-green-marker` labelled green-300
  `#6EE7B7` but `base.html` uses green-200 `#a7f3d0` (single-shade difference in
  a portable design-system doc).
- **`operator_ui_concept.md`** — the "Signed in as {name}" user card omits the
  `(super admin)` / `(sys admin)` suffix that `audience_and_identity_model.md`
  §4 documents.
- **`domain_assumptions.md`** — "1–6 Instruments" implies a hard cap; there is
  no instrument-count cap in code (the functional spec says "any number").

---

## D. Post-sweep spec additions (18R Item 3, 2026-08-18)

Drift found *after* the sweep while doing 18R Item 3 work, and resolved in the
same slice — recorded here so the sweep stays a living record.

1. **Chrome status-strip Responses pill was undocumented.** The pill's behaviour
   lived only in the 18R plan log, not in any `spec/` file — the sweep's
   status-strip coverage in `visual_style_rrw.md` had an **Invitations state
   values** table but no **Responses** equivalent. The pill also gained new
   behaviour in 18R Item 3: a **data-driven "Awaiting" gate** (numbers show on any
   response activity, independent of lifecycle, and persist through a revert to
   draft) and a **`<n> drafts / <m> submitted / <reviewees>` breakdown** (each
   zero term omitted). Documented by adding a **"Responses state values"**
   subsection to `spec/visual_style_rrw.md` (beside the Invitations table).

---

## Spec files updated in this sweep

`README.md`, `architecture.md`, `assignments.md`, `audience_and_identity_model.md`,
`csv_contracts.md`, `instruments.md`, `lifecycle.md`, `operator_ui_concept.md`,
`quick_setup_card_spec.md`, `reconciling_regeneration.md`, `reviewer-surface.md`,
`session_home.md`, `settings_inventory.md`, `setup_pages.md`, `sort_by_reviewee.md`,
`ui_elements.md`, `validate_page.md`, `visual_style_rrw.md`.

No material drift found in: `blob_storage.md` (correctly deferred),
`domain_assumptions.md`, `email_infra_options.md`, `extract_data.md`,
`operations_pages.md`, `participant_model.md`, `preview_hub.md`,
`role_navigator.md`, `roundtrip_coverage.md`, `sessions_overview.md`,
`timezone_display.md`, `visibility_policy.md`, `visual_style_general.md`,
`workflow_card.md`. (`rrw_functional_spec.md` + the `architecture.md` hierarchy
section have the §B currency debt.)
