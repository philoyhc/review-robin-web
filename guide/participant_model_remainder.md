# Participant-model remainder — outstanding items only

A focused filter on `guide/participant_model_prep.md` listing **only the
items still to ship** (or still blocked) for the participant-model
upgrade. `_prep.md` stays the canonical historical audit including the
full done-list, ship trail, and inline implementation notes — read it
for context, refer here when you want to see *what's left*.

Reset whenever an item ships: move the row out of this file and into
`_prep.md`'s "What's shipped" section.

Cross-references stay shared with `_prep.md` — see its tail for the
full list (most relevant here: `guide/participant_model_upgrade.md`
for design rationale, `guide/segment_14B_email_infrastructure.md`
for the W20 dependency, `spec/audience_and_identity_model.md`).

Last refreshed 2026-06-01 after the reviewee `/results` stream
(PRs #1737–#1750) closed out W16 (raw / anonymized / summarized) and
W19 (Acknowledge).

---

## Wiring & logic — still to ship

| # | Item | Ref | Marker | Notes |
|---|---|---|---|---|
| W5 | `app/services/collation.py` service | §7 | ⚠ | Pure code can pre-position; rendering needs `instrument_view_policies` rows from W15 (now shipped). Land alongside W17. |
| W8 | Reviewee-reachability warning on Validate page | §3.3 | ✘ | Cross-cutting soft warning; calls `is_email_identified()` (W1, shipped). Surface the warning on the Validate page for reviewees with no recoverable email. |
| W11 | Reviewer `profile_link` surface mirror — remaining touchpoints | §3.9 | ⚠ partial | Quick Setup (CSV import) and Extract Settings shipped (#1680). **Remaining:** services/reviewers create+update normalisation, Setup-Reviewers template + route, field labels default entry, display fields (label / CSV name / `ALLOWED_SOURCES` / seeding), view adapter, reviewer-summary cell styling. |
| W12 | Quick Setup Observer slot submission | §3.8 | ✘ | Wired Quick Setup card surface; persists to `observers`. Pair with W13 per L2. |
| W13 | Extract Setup observer shapes | §3.8 | ✘ | Observer roster CSV (and any later observer-specific extracts) become selectable when `observers_enabled = TRUE`. Pair with W12 per L2. |
| W17 | Observer collation surface | §5 | ✘ | Wires P6: resolves visibility policy via `visibility_policies.resolve_mode` (W7, shipped), filters by observer `tag_1`. Most of the visibility plumbing is now done — W17 can ride on it. |
| W20 | Reviewee / observer email notifications | §6 | ✘ blocked | Gated on Segment 14B email infrastructure. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ blocked | Blocked on the `invitations`-extensibility design call (polymorphic FK vs sibling tables vs discriminator). |

## Loose ends

| # | Item | Notes |
|---|---|---|
| L1 | Retire or back-fill `app/services/participants.py::sessions_for_user` | Body still returns `[]`; the real cross-role union landed inline in `_dashboard.py` (W18 / PR #1709). Pick: (a) delete `sessions_for_user` + `ParticipantSession` and treat W4 as cleanup-done; (b) move the dashboard's inline union into `sessions_for_user` and reroute. Either way, the `spec/reviewer-surface.md` drift note retires. |
| L2 | Observers round-trip for Extract + Quick Setup | The Observer roster is a first-class Setup page (W10 / PR #1706) but neither the Extract Setup nor the Quick Setup card covers it. Folded into W12 + W13 above; the round-trip closure is a thin extra over both. |

## Active blockers

| Block | What it needs |
|---|---|
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). Blocks W21 entirely. |

## Recently shipped (no longer here, but worth noting for orientation)

- **W7** Visibility-policy resolver — shipped alongside W15 in PR #1730; `resolve_mode()` is the entry point.
- **W16** Reviewee results surface — full body shipped across PRs #1737–#1749, covering the three modes (raw, anonymized, summarized) with per-data-type aggregates (mean / median / min / max for numerical, frequency + percentage for List, total + average character length for String) and zero-response label scaffolding.
- **W19** `Acknowledge` flow — shipped in PR #1750. Bottom Acknowledge card on /results with checkbox-gated button + header pill + idempotent POST + `reviewee.results_acknowledged` audit event.
