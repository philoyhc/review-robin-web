# Segment 20 — Operator polish and documentation

**Status: RESERVED — does not start until the institutional Azure
deployment has successfully concluded** (decision 2026-09-05). The
runbook for that deployment is `docs/deployment_nus.md`; "concluded"
means the NUS host is provisioned, deployed, serving, and verified,
with the personal Azure web app retired. Same gate, same reason as
Segment 14B: this segment's remaining scope is *documentation of a
real deployment*, and writing it against a host that does not yet
exist produces a guide that has to be rewritten the day it does.

Everything in the original §18 list that does **not** need the host is
now out of this segment — either already shipped (four items, audited
below) or moved to **19E** / **19C Item 8**. What is left is
the part that only the deployment can settle.

> **Renumbered 2026-05-10** from the original
> `guide/archive/segment_15_operator_polish_and_documentation.md` once
> 15A / 15B / 15C / 15D / 15E / 15F carved out their own
> homes. What remained — the documentation pass + technical
> support contact — bundles cleanly under a later number that
> reads as "the last operator-polish segment before pilot".

---

## Goal

Make the app understandable to someone who did not build it, **on the
host they will actually use**.

A new operator can run a test session using only the documentation. An
administrator can stand the service up and keep it running. Known
limitations are documented honestly against the deployed reality.

---

## Audit of the original workplan §18 list (2026-09-05)

Checked item by item against the tree at `9f3b31b3`. Four of the ten
had already shipped under other segments; three move out; three stay.

| §18 item | State | Where it goes |
|---|---|---|
| 1. Start Here page | **not built** — no such page, route or template | **19E** |
| 2. Inline guidance on setup screens | **not built** as guidance. The `.form-help` primitive exists but carries mechanical instruction ("Fill in the new row below, then Save."), not "what is this page for" | **19E** |
| 3. Validation explanations | **✅ shipped.** `ValidationRule.why` is populated for all 18 registered rules and renders as a "Why this check?" `<details>` disclosure per issue (`app/web/templates/operator/partials/validation_results.html`, `spec/validate_page.md` §3.1) | done |
| 4. Sample CSV templates | **not built** — nothing downloadable, no blank-template route | **19E** |
| 5. Sample session fixture | **not built** — no seed / demo / fixture session | **19E** |
| 6. Operator guide | **✅ shipped** as `docs/quickstart.md` (324 lines, one session end-to-end: create, set up, launch, watch, share) | currency pass stays here |
| 7. Administrator guide | **partial, and host-dependent.** The material exists scattered across `docs/operations_runbook.md`, `docs/deployment_dev.md`, `docs/azure_provision.md`, `docs/backup_restore.md`, `docs/security_posture.md`; there is no single administrator guide, and the one that matters describes the *institutional* host | **stays — the gated item** |
| 8. Developer setup guide | **✅ shipped** as `docs/local_setup.md` (322 lines) | done |
| 9. Troubleshooting guide | **✅ shipped for the dev slot** as `docs/troubleshooting.md`. Its failure modes are the personal-Azure ones; the institutional host will have its own (tenant, Easy Auth, NUS network policy) | institutional half stays here |
| 10. Known limitations page | **✅ shipped** as `docs/known_limitations.md` | currency pass stays here |
| + Technical-support contact (global) | **not built.** Mechanism is an env var + footer + error-page surfaces and needs no host; only the *address* is a deploy-time decision, and an unset var renders nothing | **19C Item 8** (mechanism now, value at deploy) |

---

## What remains in this segment

1. **Administrator guide** for the institutional host — the single
   document an administrator who is not the author reads to stand the
   service up, grant access, and keep it running. Consolidates and
   supersedes what is currently scattered; written against the real
   tenant, not against `docs/deployment_dev.md`'s personal-Azure
   topology.
2. **Troubleshooting, institutional half** — the failure modes the NUS
   host actually produces (Easy Auth / tenant, network policy, the
   NUS deploy workflow), appended to `docs/troubleshooting.md`.
3. **Currency pass on the operator-facing docs** — `docs/quickstart.md`
   and `docs/known_limitations.md` re-read against the deployed
   reality: real URLs, real sign-in flow, and limitations that are
   still limitations once the host exists.
4. **The technical-support address itself** — set the env var 19C
   Item 8 introduces to the real contact for the deployment.

---

## Deliberately out of scope

- Anything that can be written or built without the host. That is the
  whole point of the 2026-09-05 split: if it does not need the
  deployment, it belongs in 19E / 19C, not here.
- Re-doing the four items the audit found already shipped. A currency
  pass over `quickstart` / `known_limitations` is not a rewrite.
- New feature work not in the workplan §18 list.

---

## Superseded plan

The pre-2026-09-05 stub follows, unedited, as the record of what this
segment was before the Azure gate and the audit narrowed it.

> **Status:** Stub. Picks up the operator polish + documentation
> scope named in the master workplan
> (`guide/archive/low_intensity_workplan_review_robin_web.md` §18,
> preserved in archive). Forward-looking detail (slice ladder,
> design notes, cross-cuts) lands in a follow-up plan once
> Segments 11–17 ship and the operator surface is ready to
> receive its first real pilot.
>
> This segment is the "make the system understandable to
> someone who did not build it" pass. It runs after Segment 14
> (production hardening) so the system is operationally
> credible before the documentation is written for it.
>
> **Main learning focus:** onboarding; explanatory UI;
> documentation; handover materials.
>
> **Build outcome:** A new operator can understand the system, set up
> a test session, and run through the workflow end-to-end without
> prior context.
>
> **Work items (from workplan §18):** 1. Add Start Here page.
> 2. Add inline guidance to setup screens. 3. Add validation
> explanations. 4. Add sample CSV templates. 5. Add sample session
> fixture. 6. Add operator guide. 7. Add administrator guide.
> 8. Add developer setup guide. 9. Add troubleshooting guide.
> 10. Add known limitations page.
>
> **Also slated:** Technical-support contact (global) — distinct from
> the operational help contact (which lives on `ReviewSession`).
> Address a reviewer reaches when something looks broken (auth fail,
> 500, invalid link). Filed 2026-05-03 from the Segment 11 Tier 2 §24
> reframe. Small `[chrome]` item: new env var + footer + error-page
> surfaces.
>
> **Done when:** A new operator can run a test session using
> documentation. A future developer can set up the app locally. Known
> limitations are documented honestly.
