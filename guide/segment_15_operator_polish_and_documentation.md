# Segment 15 — Operator polish and documentation

**Status:** Stub. Picks up the operator polish + documentation scope
named in the master workplan
(`guide/low_intensity_workplan_review_robin_web.md` §18) so the
intent isn't lost. Forward-looking detail (slice ladder, design
notes, cross-cuts) lands in a follow-up plan once Segments 11–14 land
and the operator surface is ready to receive its first real pilot.

This segment is the "make the system understandable to someone who
did not build it" pass. It runs after Segment 14 (production
hardening) so the system is operationally credible before the
documentation is written for it.

---

## Goal

Make the app understandable to someone who did not build it.

A new operator can run a test session using only the documentation. A
future developer can set up the app locally. Known limitations are
documented honestly.

---

## Main learning focus

- onboarding;
- explanatory UI;
- documentation;
- handover materials.

---

## Build outcome

A new operator can understand the system, set up a test session, and
run through the workflow end-to-end without prior context.

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

These were originally tracked elsewhere but belong with the polish /
documentation pass:

- **Real SMTP email backend** — `docs/status.md` "What's deliberately
  not yet there." The dev outbox stays the only mail sink until this
  segment lights up the production path.
- **Queue-based batch invitation sending** — decided 2026-05-03 from
  Segment 11 Tier 2 §2.3; tracked at
  `guide/unfinished_business.md` #34. Out-of-request send only
  becomes load-bearing when real SMTP lands, so it bundles with
  the SMTP work above. Depends on #6 (decouple `invitations.py`
  from `Request`) shipping first — currently scheduled in
  Segment 11 Tier 3.
- **Inline-editable rows for reviewers / reviewees / assignments
  Manage pages** — officially deferred from Segment 11 (originally
  10E §2.5); tracked at `guide/unfinished_business.md` #25. Needs a
  design pass before code; the polish segment is the right home.
- **Sessions-list Delete button fix** — officially deferred from
  Segment 11 Tier 1 (2026-05-03); tracked at
  `guide/unfinished_business.md` #23. Small fix (`<a>` → POST form
  with confirm); bundles naturally with whatever other
  `/operator/sessions` UI work this segment touches.
- **Further refinement of the reviewer surface** — catch-all for
  reviewer-surface polish beyond the Segment 11 Tier 1 batch
  (PRs #319 → #324). Tracked at `guide/unfinished_business.md`
  #32. Known sub-item: multi-instrument preview (the
  `build_preview_context` extension explicitly deferred from
  Segment 11). Pilot-feedback-driven polish lands here too.
- **AG Grid replacement of the reviewer-surface table** — second
  half of workplan §11 / archived Segment 8 plan that never
  landed. Decided 2026-05-03 from Segment 11 Tier 2 §2.1; tracked
  at `guide/unfinished_business.md` #33. Naturally bundles with
  vanilla-JS autosave (Segment 11 Tier 4 #2.2) and absorbs the
  multi-instrument preview sub-item of #32 if AG Grid grouping
  handles it natively.
- **Technical-support contact (global)** — distinct from the
  operational help contact tracked at `#24` (which lives on
  `ReviewSession`). Address a reviewer reaches when something
  looks broken (auth fail, 500, invalid link). Filed 2026-05-03
  from the Segment 11 Tier 2 §24 reframe; tracked at
  `guide/unfinished_business.md` #35. Small `[chrome]` item:
  new env var + footer + error-page surfaces.
- **Local Postgres docker-compose for dev** — officially deferred
  from Segment 11 (originally 10E §2.7); tracked at
  `guide/unfinished_business.md` #26. The developer-setup-guide
  work item above is the natural place for the Postgres-vs-SQLite
  local-dev story to settle.

---

## Deliberately out of scope

- Anything from Segments 11–14 that hasn't shipped yet. This segment
  comes after them.
- New feature work not in the workplan §18 list.
