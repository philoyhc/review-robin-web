# Master todo sequence

Prioritized order for working through the
`guide/unfinished_business.md` catalog. **Two files, two
purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. Which item next, and why that
  order. Read it for the roadmap.

When you ship an item, tick it off in **both** files.

The sequence is shaped by three forces: (a) user-facing
correctness comes first (data-loss-by-illusion in the Display
Fields card is the headline), (b) some items must land in a
specific order because they touch the same code (item 11 has to
follow items 13–14, item 4 has to follow item 17, item 12 has to
follow item 8), and (c) items that defend against regressions
during big refactors (CI lint, Postgres tests, missing 10C tests)
should land before the big refactors themselves.

---

## P0 — Stop the bleeding (Instruments UI ↔ data drift)

The round-3 audit (2026-05-01) found that the operator's per-
instrument **Display Fields** card and the underlying schema have
drifted apart in ways that silently lose user input and silently
hide imported reviewee data. Land these before anything else,
including the CI hardening items, because they're the only items
that affect what reviewers actually see today.

| Order | Item | Why this position |
|---|---|---|
| 1 | ~~**#13 — Fix Display Fields placeholder**~~ ✅ shipped 2026-05-01 (option 2: wired to existing routes). |
| 2 | ~~**#14 — Drop `pair_context_*` default seed; seed from import data**~~ ✅ shipped 2026-05-01 (lazy-seed + Alembic data migration). |
| 3 | ~~**#18 — Decide "Add an instrument" button vs route**~~ ✅ decided 2026-05-02 — **enable the button**. Implementation is Slice 5 of Segment 10D (the segment-closing slice; ~1 hr). |

P0 in this catalog is now functionally closed. The Slice-4 ladder
of Segment 10D (#242 → #257 + banner-convention follow-ups #258 /
#259) reshaped the per-instrument card and the Response Type
Definitions card around a single editing state machine, mutual-
exclusion edit lock, save-time RF / RTD guards, and a banner
auto-scroll convention. After Slice 5 ships, reviewers see the
right columns, operators don't get gaslit, and the Instruments
page surface area matches the backing routes end-to-end.

---

## P1 — Defend against regressions before refactoring

These don't fix bugs themselves, but they catch the regressions
the upcoming arch refactors (P2) would otherwise ship silently.

| Order | Item | Why this position |
|---|---|---|
| 4 | **#15 — Backfill 10C integration tests** | `delete_instrument`, `bulk_set_visibility`, `add-row`, last-instrument-guard all shipped without tests. Land before item 3 / item 11 ripple through the same code. |
| 5 | **#1 — Wire `ruff check` into CI** | 5-minute change. Catches lint regressions in the arch churn that's about to start. Easy bundle: fix any pre-existing ruff findings as a precursor PR. |
| 6 | **#2 — Run pytest against Postgres in CI** | The seed-from-import-data work in item 14 will exercise JSON / context handling that's most likely to diverge between SQLite and Postgres. This is the cheapest place to catch dialect drift before deploy. |

---

## P2 — Architectural debt before Segment 11

Segment 11 (export / audit retention) will read `Assignment.context`
and write a stable `audit_events.detail` schema, so settle the
arch story first.

| Order | Item | Why this position |
|---|---|---|
| 7 | **#17 — Investigate `Assignment.include` filter divergence** | Sequenced before item 4 because consolidating the helpers (item 4) requires knowing which filter is right. Trace one reviewer through both paths and pick one. |
| 8 | **#4 — Extract a single reviewer-session-state helper** | Now safe to do — the right semantics are decided in #17. Two functions in `responses.py:435` + `monitoring.py:67` collapse to one private helper + two thin projections. |
| 9 | **#3 — Move `_invalidate_if_validated` into the service layer** | 17 caller sites across `routes_operator.py`. Naturally bundles with **#16** (decide bulk_visibility invalidation policy) since both touch the invalidation surface. |
| 10 | **#16 — Decide bulk_visibility_when_closed invalidation policy** | Bundle with #9. Either align with `bulk_set_accepting` or document why exempt. |
| 11 | **#11 — Extract instruments-index template context to `views.py`** | Lands *after* P0 (#13–14) so the extracted helper builds the right shape. Update line numbers (now `routes_operator.py:956–1056`). |
| 12 | **#8 — Fix CSV email-validation drift** | Sets up #12 (cross-table identity check) cleanly — same code path. |
| 13 | **#12 — Reviewer/Reviewee CSV cross-table identity check** | Builds on #8's shared `_parse_email` helper. Tightens the rule that email is the unique person-identifier across reviewer + reviewee tables in the same session. |

---

## P3 — Pre-Segment-15 + small cleanups

Items that aren't blocking the next feature segment but should
land before they age into harder problems.

| Order | Item | Why this position |
|---|---|---|
| 14 | **#5 — Define audit-event `detail` schema convention** | Document in `spec/architecture.md`. Migrate emitters incrementally — one PR per emitter family. Segment 11 will export these, so the convention needs to settle first. |
| 15 | **#6 — Decouple `invitations.py` from `Request`** | Only matters when Segment 15 (real SMTP) lands and sends from a background worker. Worth fixing now while the surface is small. |
| 16 | **#7 — CSRF decision write-up** | One paragraph in `docs/authentication.md`. Decide between Easy Auth + SameSite cookies vs. CSRF tokens. If "tokens", that becomes its own segment. |
| 17 | **#10 — Thread `correlation_id` into deadline lazy-close** | Cheap. Bundle with whichever route refactor next touches `observe_deadline`. |
| 18 | **#9 — Refresh `get_or_create_default_instrument` docstring** | Tiny. (Pointer corrected to `app/services/assignments.py:402`.) |
| 19 | **#19 — Roll session-status top card onto Reviewers / Reviewees / Assignments / Instruments** | Pure chrome cleanup. Partial shipped in #252 (used by Session detail + Email Invites today); the four other session-scoped pages still hand-roll their top cards. Land per-page so each PR stays small. |

---

## Notes on the order

- **Why P0 jumps the CI items.** Item 1 (ruff in CI) and item 2
  (Postgres pytest) are normally first by priority, but the
  Instruments mess is actively misleading users *today* — every
  day that ships is a day of operators thinking they configured
  display fields they didn't. CI gaps don't have that
  active-cost-per-day shape.
- **Why item 17 jumps item 4.** Item 4 wants to consolidate
  `responses.session_pill_for_reviewer` and
  `monitoring._reviewer_completion` into one helper. They use
  different `Assignment.include` filters today; if you
  consolidate without first deciding which filter is right, you
  ship the wrong unified rule.
- **Why item 11 waits for P0.** The instruments-index handler
  builds context (`merged_rows_by_instrument`,
  `available_sources_by_instrument`) that the new template
  doesn't currently consume, and items 13–14 will reshape both.
  Extracting the helper before that change is throwaway work.
- **Why item 18 sits inside P0 instead of P3.** It's a tiny
  decision but it directly gates item 11's scope. Rolling it
  forward would mean re-doing item 11.

---

## What's not on this list

Anything in `docs/status.md` "What's deliberately not yet there"
— those are owned by their assigned future segments. The
"Display Fields persistence" entry there *was* one of those
deferred items, but the round-3 audit promoted the user-facing
correctness slice to item 13 because the placeholder is
silently destructive. Persistence proper still lives in a future
slice (Segment 11 or a 10x patch).
