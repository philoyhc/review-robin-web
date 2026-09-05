# Segment 19F — Starter artefacts

**Status: stub — not started.** Carved out of Segment 20 on 2026-09-05
when that segment was reserved for after the institutional Azure
deployment concludes. Both items are artefacts the app produces or
seeds; they need the app, not the host.

---

## Opportunity

An operator setting up their first session has to author three roster
CSVs from a written description of the header grammar. Nothing in the
app hands them a correctly-shaped file to start from, and nothing lets
them see a populated session before they have built one. The two gaps
compound: the first upload is also the first time they learn whether
they understood the format.

Evidence (2026-09-05, tree at `9f3b31b3`): no downloadable template,
blank-CSV route or sample file anywhere in `app/`; no seed, demo or
fixture session in `app/`, `tools/` or the docs.

---

## Scope — two items

1. **Sample CSV templates.** A correctly-shaped, header-only (or
   minimally-populated) file per roster type — reviewers, reviewees,
   relationships — plus session settings, downloadable from the page
   that consumes it. Generated from the same code that parses them, so
   a template can never drift from the contract it demonstrates.
2. **Sample session fixture.** A loadable example session an operator
   can inspect end-to-end before building their own: roster, an
   instrument, relationships, and enough responses to make the
   Responses and Results surfaces show something.

---

## Known constraints

- **Derive, don't duplicate.** The templates must come from the
  parsers / serializers in `app/services/` (the round-trip extract
  side already emits exactly these shapes) — a hand-maintained CSV in
  the repo is a second source of truth for `spec/csv_contracts.md` and
  will drift. This is the item's central design decision and it is
  worth stating in the plan's `## Decision`.
- The fixture must not be creatable in a deployed environment by
  accident, and must be clearly marked as sample data wherever it
  appears.
- If either item adds a card or a download affordance to an existing
  page, scaffold-first applies (`CLAUDE.md` → "Working approach").

---

## Open questions

- Header-only templates, or templates carrying two or three example
  rows? Example rows teach the format better and are also the thing an
  operator most often forgets to delete.
- Is the fixture seeded by a `tools/` script (operator runs it), or by
  an in-app action gated to sys-admins? The second is more discoverable
  and more dangerous.
- Whether the fixture's responses are generated or fixed. Fixed is
  reproducible; generated exercises more of the shape.

---

## Out of scope

- The CSV contract itself — `spec/csv_contracts.md` governs it and
  this segment demonstrates it, never changes it.
- Anything needing the deployed host; that is Segment 20.
- Start Here and inline setup guidance — Segment 19E.
