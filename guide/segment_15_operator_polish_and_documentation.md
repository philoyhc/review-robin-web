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
- **Queue-based batch invitation sending** — `guide/segment_10E_*.md`
  §2 originally floated this as 10E scope; out-of-request send only
  becomes load-bearing when real SMTP lands, so it bundles here.
- **Inline-editable rows for reviewers / reviewees / assignments
  Manage pages** — officially deferred from 10E §2.5; tracked at
  `guide/unfinished_business.md` #25. Needs a design pass before
  code; the polish segment is the right home.
- **Local Postgres docker-compose for dev** — officially deferred
  from 10E §2.7; tracked at `guide/unfinished_business.md` #26. The
  developer-setup-guide work item above is the natural place for the
  Postgres-vs-SQLite local-dev story to settle.

---

## Deliberately out of scope

- Anything from Segments 11–14 that hasn't shipped yet. This segment
  comes after them.
- New feature work not in the workplan §18 list.
