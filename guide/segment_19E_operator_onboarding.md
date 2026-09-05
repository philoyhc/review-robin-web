# Segment 19E — Operator onboarding surfaces

**Status: stub — not started.** Carved out of Segment 20 on 2026-09-05
when that segment was reserved for after the institutional Azure
deployment concludes. These two items are in-app explanatory UI; they
need the app, not the host, so there is no reason to hold them.

Sibling of 19A (docs hygiene), 19B (code consistency) and 19C
(behaviour / contract polish). This one is **explanatory UI** — the
theme is new, which is why it is its own segment rather than a 19C
item.

---

## Opportunity

A first-time operator arrives at the app with no orientation. The
setup pages tell them *how to operate the form* (`.form-help`: "Fill
in the new row below, then Save.") but never *what the page is for* or
*where they are in the workflow*. There is no entry point that says
what a session is, what the five setup pages do, or what order to do
them in — `docs/quickstart.md` says all of it, but it lives outside
the app and a first-time operator does not know it exists.

Evidence (2026-09-05, tree at `9f3b31b3`): no route, template or nav
entry matching "Start Here" anywhere in `app/`. `.form-help` appears
on the reviewers / reviewees / relationships / validate pages and
carries only per-form mechanics.

---

## Scope — two items

1. **Start Here page.** The in-app orientation entry point: what a
   review session is, the five setup pages in order, what the operator
   needs before they begin (a reviewer list, a reviewee list, a
   relationship rule), and where the workflow goes after Validate.
   Reachable from operator chrome.
2. **Inline guidance on the setup screens.** One short, page-level
   explanation per setup page, saying what the page is for and what a
   good result looks like — distinct from the existing per-form
   mechanics, and consistent across the five pages.

---

## Known constraints

- **Scaffold-first is mandatory here.** Per `CLAUDE.md` → "Working
  approach", the Start Here page adds both a page and a navigation
  affordance, so the first slice is the nav entry plus the page with
  every card as a static placeholder — real copy and layout, inert
  controls — and the wiring follows in later slices.
- **No new visual primitive without a role.** Page-level guidance
  needs a class in `base.html`, and it must map to a role in
  `spec/ui_elements.md` or the question goes to the user first.
- Item 3 of the old §18 list (validation explanations) is **already
  shipped** — `ValidationRule.why` renders as a "Why this check?"
  disclosure. Do not rebuild it; the Validate page's guidance slice is
  about the page, not the rules.

---

## Open questions

- Does Start Here live under `/operator/` chrome, or is it also the
  landing page for an operator with no sessions yet? — the user
  decides when the segment starts.
- Whether page-level guidance is always-visible prose or a
  dismissible / collapsible band. Affects whether any browser-local UI
  state is needed (`spec/settings_inventory.md`).

---

## Out of scope

- The operator guide itself — `docs/quickstart.md`, already shipped.
- Anything needing the deployed host; that is Segment 20.
- Sample CSVs and the demo session — Segment 19F.
