# Segment 18R — UX refinement

**Status:** Planning. A holding segment for **small, self-contained UX /
identity polish** on already-shipped operator surfaces — clarifying what each
card / control *is*, tightening labels, and strengthening visual identity —
without changing behaviour. Items land as independent slices; the segment
stays open as a home for further small UX refinements.

> Consequential-UI note: per `CLAUDE.md` → "Working approach", anything that
> adds a card / nav / affordance lands **scaffold-first**. The items here are
> mostly *re-labelling and identity* on existing cards, so most are a single
> reviewable template slice; call out scaffold-first only where an item adds a
> genuinely new surface.

---

## Item 1 — Instrument card identity (retire "Band 1" → "Assignment rule")

**The problem.** On the per-instrument card (Instruments page,
`app/web/templates/operator/instruments_index.html`), the **top band** — the
three assignment-rule **Links** (Pool of reviewers / Pool of those reviewed /
Unit of review) — renders directly under the editable **Instrument Name**
with **no card title of its own**. It's referred to informally as "**Band 1**"
(an internal build-era name), which leaks into operator-facing docs. The cards
*below* it (Preview review instrument, Visibility, Response Fields) each read
as a clearly identified card; the top band does not, so operators have no
name for the single most important control on the page.

**The fix.**

1. **Give the top band a card title** — **"Assignment rule"** (alternative
   considered: "Response assignment rule"; go with the shorter unless review
   prefers the longer). It should read as a peer of the Response Fields /
   Visibility / Preview cards: same heading treatment, sitting between the
   Instrument Name (above) and the Preview review instrument card (below).
2. **Strengthen every section's identity in the same pass** — make the card
   set on the instrument card self-describing and visually consistent
   (Instrument Name → Assignment rule → Preview review instrument →
   Visibility → Response Fields). Titles / headings only; no behaviour or
   layout-logic change.
3. **Rename the operator-facing "Band 1" wording** in `spec/instruments.md`
   and `spec/assignments.md` to "Assignment rule". The **internal** `band1`
   code identifiers (`_band1.py`, `set_band1_assignment_rules`,
   `new_model_band1_state`, CSS/data attributes, the `band1_touched_links`
   column) **stay** — renaming those is churn with no user benefit; this item
   is about the *operator-facing* name only.

**Scope / size.** A **small** template slice on `instruments_index.html`
(add the heading, tidy the section identities) + the two spec wording
updates. No route, service, model, or migration change. No test change
expected beyond any template-string assertion that greps for the old label
(check `tests/` for "Band 1" before pushing).

**Definition of done.**

- The instrument card's top band shows a clear **"Assignment rule"** title;
  the five sections read as consistently-identified cards.
- `spec/instruments.md` / `spec/assignments.md` say "Assignment rule" for the
  operator-facing name (internal `band1` identifiers unchanged, with a
  one-line note that the code name is retained).
- `docs/quickstart.md` §4c already says "Assignment rule" / "top band" — keep
  it consistent (its `08-band1-rule.png` screenshot slot can be recaptioned
  to `08-assignment-rule.png` when screenshots are produced).
- Full suite green; `ruff` clean.

---

## Future items (add as they come up)

This segment is the landing place for further small operator-UX identity /
label refinements. Log new ones here as `Item N` with the same
problem / fix / scope / done-when shape, and keep each a self-contained slice.

---

## Doc impact

- `spec/instruments.md`, `spec/assignments.md` — "Band 1" → "Assignment rule"
  (operator-facing name), per Item 1.
- `docs/status.md` — note the rename when Item 1 ships (Segments-shipped +
  any operator-UI capability line that names "Band 1").
- `docs/quickstart.md` — keep §4c wording + the screenshot slot consistent.
