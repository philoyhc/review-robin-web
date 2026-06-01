# Participant-model remainder — outstanding items only

The short list of items still to ship (or still blocked) for
the participant-model upgrade. The design surface is
`guide/participant_model_upgrade.md` (see Appendix A for the
full S / P / W identifier glossary); the historical ship trail
is in `guide/todo_master.md`'s Done section.

Refresh whenever an item ships by deleting its row from this
file and adding a matching entry to `todo_master.md`.

Last refreshed 2026-06-01 after the Observers round-trip + W11
in-scope + W8 stream.

---

## Wiring & logic — still to ship

| # | Item | Ref | Marker | Notes |
|---|---|---|---|---|
| W11 | Reviewer `profile_link` — out-of-scope touchpoints | §3.9 | ⚠ partial | Setup mirror shipped (#1680 + #1756). **Remaining (different design call):** display-fields `ALLOWED_SOURCES` / seeding (the display-fields system is reviewer-form-facing and shows reviewee data; reviewer `profile_link` doesn't naturally fit), reviewer-summary cell styling on the operator's reviewer detail surface. Pull from the remainder when either surface is in scope. |
| W17 + W5 | Observer collation surface + supporting service | §5 + §7 | ✘ | Wires P6: resolves visibility policy via `visibility_policies.resolve_mode` (W7, shipped), filters by observer `tag_1`. W5 (`app/services/collation.py`) is the supporting service module and lands alongside — no useful pre-positioning since W17 is its sole consumer. Most of the visibility plumbing is now done so W17 can ride on it. |
| W20 | Reviewee / observer email notifications | §6 | ✘ blocked | Gated on Segment 14B email infrastructure. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ blocked | Blocked on the `invitations`-extensibility design call (polymorphic FK vs sibling tables vs discriminator). |

## Active blockers

| Block | What it needs |
|---|---|
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). Blocks W21 entirely. |
