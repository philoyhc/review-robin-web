# Segment 20 — Operator polish and documentation

**Status:** Stub. Picks up the operator polish + documentation
scope named in the master workplan
(`guide/archive/low_intensity_workplan_review_robin_web.md` §18,
preserved in archive). Forward-looking detail (slice ladder,
design notes, cross-cuts) lands in a follow-up plan once
Segments 11–17 ship and the operator surface is ready to
receive its first real pilot.

> **Renumbered 2026-05-10** from the original
> `guide/archive/segment_15_operator_polish_and_documentation.md` once
> 15A / 15B / 15C / 15D / 15E / 15F carved out their own
> homes. What remained — the documentation pass + technical
> support contact — bundles cleanly under a later number that
> reads as "the last operator-polish segment before pilot".

This segment is the "make the system understandable to
someone who did not build it" pass. It runs after Segment 14
(production hardening) so the system is operationally
credible before the documentation is written for it.

---

## Goal

Make the app understandable to someone who did not build it.

A new operator can run a test session using only the
documentation. A future developer can set up the app locally.
Known limitations are documented honestly.

---

## Main learning focus

- onboarding;
- explanatory UI;
- documentation;
- handover materials.

---

## Build outcome

A new operator can understand the system, set up a test
session, and run through the workflow end-to-end without
prior context.

---

## Work items (from workplan §18)

1. Add Start Here page.
2. Add inline guidance to setup screens.
3. Add validation explanations.
4. Add sample CSV templates.
5. Add sample session fixture.
6. Add operator guide.
7. Add administrator guide.
8. Add developer setup guide.
9. Add troubleshooting guide.
10. Add known limitations page.

---

## Done when

- A new operator can run a test session using documentation.
- A future developer can set up the app locally.
- Known limitations are documented honestly.

---

## Items also slated for this segment

- **Technical-support contact (global)** — distinct from the
  operational help contact (which lives on `ReviewSession`).
  Address a reviewer reaches when something looks broken
  (auth fail, 500, invalid link). Filed 2026-05-03 from the
  Segment 11 Tier 2 §24 reframe. Small `[chrome]` item: new
  env var + footer + error-page surfaces. Naturally bundles
  with the documentation pass since it adds a
  user-visible
  "where to get help" surface alongside the operator /
  admin guides.

---

## Deliberately out of scope

- Anything from Segments 11–17 that hasn't shipped yet. This
  segment comes after them.
- New feature work not in the workplan §18 list.
