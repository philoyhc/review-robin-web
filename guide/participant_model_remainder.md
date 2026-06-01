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

Last refreshed 2026-06-01 after the Observers round-trip stream
(PRs #1737–#1756) closed out W7 + W12 + W13 + W16 + W19 + W11
(in-scope) + L1 + L2; W5 collapsed into W17.

---

## Wiring & logic — still to ship

| # | Item | Ref | Marker | Notes |
|---|---|---|---|---|
| W8 | Reviewee-reachability warning on Validate page | §3.3 | ✘ | Cross-cutting soft warning; calls `is_email_identified()` (W1, shipped). Surface the warning on the Validate page for reviewees with no recoverable email. |
| W11 | Reviewer `profile_link` — out-of-scope touchpoints | §3.9 | ⚠ partial | Quick Setup CSV import + Extract Settings shipped (#1680); services/reviewers + Setup-Reviewers + field labels + preview-table column shipped (#1756). **Remaining (different design call):** display-fields `ALLOWED_SOURCES` / seeding (the display-fields system is reviewer-form-facing and shows reviewee data; reviewer `profile_link` doesn't naturally fit), reviewer-summary cell styling on the operator's reviewer detail surface. Pull from the remainder when either surface is in scope. |
| W17 + W5 | Observer collation surface + supporting service | §5 + §7 | ✘ | Wires P6: resolves visibility policy via `visibility_policies.resolve_mode` (W7, shipped), filters by observer `tag_1`. W5 (`app/services/collation.py`) is the supporting service module and lands alongside — no useful pre-positioning since W17 is its sole consumer. Most of the visibility plumbing is now done so W17 can ride on it. |
| W20 | Reviewee / observer email notifications | §6 | ✘ blocked | Gated on Segment 14B email infrastructure. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ blocked | Blocked on the `invitations`-extensibility design call (polymorphic FK vs sibling tables vs discriminator). |

## Active blockers

| Block | What it needs |
|---|---|
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). Blocks W21 entirely. |

## Recently shipped (no longer here, but worth noting for orientation)

- **W7** Visibility-policy resolver — shipped alongside W15 in PR #1730; `resolve_mode()` is the entry point.
- **W12** Quick Setup Observers slot — shipped in PR #1754. Right column reads Relationships → Observers → Session settings when `observers_enabled` is on.
- **W13** Extract Setup Observers row + bundle inclusion — shipped in PR #1755. `observers.csv` round-trips with the Quick Setup slot; setup bundle picks it up.
- **W16** Reviewee results surface — full body shipped across PRs #1737–#1749, covering the three modes (raw, anonymized, summarized) with per-data-type aggregates (mean / median / min / max for numerical, frequency + percentage for List, total + average character length for String) and zero-response label scaffolding.
- **W19** `Acknowledge` flow — shipped in PR #1750. Bottom Acknowledge card on /results with checkbox-gated button + header pill + idempotent POST + `reviewee.results_acknowledged` audit event.
- **W11 (in-scope)** Reviewer `profile_link` Setup mirror — shipped in PR #1756. Services / Setup route + template / friendly label / preview-column visibility all align with the reviewee treatment; out-of-scope items folded back into the W11 row above.

## Loose-end log

- **L1** Retire `participants.sessions_for_user` + `ParticipantSession` — closed 2026-06-01. Deleted as dead code; `_dashboard.py` keeps its inline cross-role union (the W18 implementation choice). Two unit tests retired with the stub.
- **L2** Observers round-trip for Extract + Quick Setup — closed 2026-06-01 with W12 (#1754) + W13 (#1755). Roster CSV round-trips end-to-end.
