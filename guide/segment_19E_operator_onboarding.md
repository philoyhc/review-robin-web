# Segment 19E — Operator onboarding

**Status: stub — not started.** Carved out of Segment 20 on 2026-09-05
when that segment was reserved for after the institutional Azure
deployment concludes. Everything here needs the app, not the host, so
there is no reason to hold it.

Sibling of 19A (docs hygiene), 19B (code consistency) and 19C
(behaviour / contract polish). This one is **operator onboarding** —
the theme is new, which is why it is its own segment rather than a 19C
item.

> **Absorbed Segment 19F 2026-09-05, hours after both stubs were
> written.** 19F ("starter artefacts" — Items 3 and 4 below) was split
> out on the grounds that it is service/data work while Items 1 and 2
> are view work. That is a distinction of **implementation layer, not
> of theme**, and the rule is thematic (`CLAUDE.md` → "Working
> approach": prefer an item on a live segment over a new segment when
> the work shares a theme). All four items serve one first-time
> operator getting oriented, which is how the original workplan §18
> grouped them. The layer difference is real and survives as the
> per-item notes below; it was never a reason for a second plan, a
> second close sequence, and a second archive row.

---

## Opportunity

A first-time operator arrives at the app with no orientation, and every
gap compounds the next.

There is no entry point that says what a session is, what the five
setup pages do, or what order to do them in. The setup pages themselves
tell them *how to operate the form* (`.form-help`: "Fill in the new row
below, then Save.") but never what the page is for. When they reach the
first upload they must author three roster CSVs from a written
description of the header grammar, with nothing correctly-shaped to
start from — so the first upload is also the first time they find out
whether they understood the format. And nothing lets them look at a
populated session before they have successfully built one.

`docs/quickstart.md` answers all of this, and a first-time operator does
not know it exists.

Evidence (2026-09-05, tree at `9f3b31b3`): no route, template or nav
entry matching "Start Here" anywhere in `app/`; `.form-help` appears on
the reviewers / reviewees / relationships / validate pages and carries
only per-form mechanics; no downloadable template or blank-CSV route;
no seed, demo or fixture session in `app/`, `tools/` or the docs.

---

## Scope — four items

Workplan §18 items 1, 2, 4 and 5. Item 3 of that list (validation
explanations) is **already shipped** — `ValidationRule.why` is
populated for all 18 registered rules and renders as a "Why this
check?" disclosure. Do not rebuild it.

1. **Start Here page.** The in-app orientation entry point: what a
   review session is, the five setup pages in order, what the operator
   needs before they begin (a reviewer list, a reviewee list, a
   relationship rule), and where the workflow goes after Validate.
   Reachable from operator chrome.
2. **Inline guidance on the setup screens.** One short, page-level
   explanation per setup page, saying what the page is for and what a
   good result looks like — distinct from the existing per-form
   mechanics, and consistent across the five pages.
3. **Sample CSV templates.** A correctly-shaped file per roster type —
   reviewers, reviewees, relationships — plus session settings,
   downloadable from the page that consumes it.
4. **Sample session fixture.** A loadable example session an operator
   can inspect end-to-end before building their own: roster, an
   instrument, relationships, and enough responses to make the
   Responses and Results surfaces show something.

Items 1 and 2 are view-layer work. Items 3 and 4 reach into
`app/services/` and create rows, which is why their constraints below
are heavier — but they close the same gap and belong to the same
reader.

---

## Known constraints

**Items 1–2 (view layer)**

- **Scaffold-first is mandatory.** Per `CLAUDE.md` → "Working
  approach", the Start Here page adds both a page and a navigation
  affordance, so the first slice is the nav entry plus the page with
  every card as a static placeholder — real copy and layout, inert
  controls — and the wiring follows in later slices.
- **No new visual primitive without a role.** Page-level guidance
  needs a class in `base.html`, and it must map to a role in
  `spec/ui_elements.md` or the question goes to the user first.

**Items 3–4 (service / data layer)**

- **Derive, don't duplicate.** The templates must come from the
  parsers / serializers in `app/services/` (the round-trip extract side
  already emits exactly these shapes) — a hand-maintained CSV in the
  repo is a second source of truth for `spec/csv_contracts.md` and will
  drift. This is the central design decision of Item 3 and belongs in
  its `## Decision`.
- The fixture must not be creatable in a deployed environment by
  accident, and must be clearly marked as sample data wherever it
  appears.
- A download affordance on an existing page is still a new affordance:
  scaffold-first applies to Item 3 as well.

---

## Open questions

- Does Start Here live under `/operator/` chrome, or is it also the
  landing page for an operator with no sessions yet? — the user
  decides when the segment starts.
- Whether page-level guidance is always-visible prose or a
  dismissible / collapsible band. Affects whether any browser-local UI
  state is needed (`spec/settings_inventory.md`).
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

- The operator guide itself — `docs/quickstart.md`, already shipped.
- The CSV contract — `spec/csv_contracts.md` governs it and this
  segment demonstrates it, never changes it.
- Validation explanations — already shipped; see above.
- Anything needing the deployed host; that is Segment 20.
