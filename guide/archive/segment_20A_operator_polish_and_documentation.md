# Segment 20A — Operator polish and documentation

**Status: CLOSED 2026-11-01.** It was reserved until the institutional
Azure deployment had successfully concluded (decision 2026-09-05). The
runbook for that deployment is kept privately with the deployment, not
in this repository (since 2026-10-24); "concluded"
means the NUS host is provisioned, deployed, serving, and verified,
with the personal Azure web app retired. Same gate, same reason as
Segment 14B: this segment's remaining scope is *documentation of a
real deployment*, and writing it against a host that does not yet
exist produces a guide that has to be rewritten the day it does.

*State, 2026-11-01:* the host is provisioned, deployed and serving
Review Robin since 2026-10-31. Retiring the personal web app no longer
belongs in the gate: the author left that environment dormant, not
retired (2026-10-24, `guide/post_azure_todo_checklist.md` item 2). What
remains of "concluded" is verification, the author's call. **The gate
passed 2026-11-01** (author): the web app is verified to work in Azure.

*Renamed and trimmed 2026-11-01 (author):* `segment_20_…` became
`segment_20A_…`, and the items the private Cordware repository
documents left this plan (see "What remains").

Everything in the original §18 list that does **not** need the host is
now out of this segment — either already shipped (four items, audited
below) or moved out — three to **19E**, and the technical-support contact to a stub in
`guide/todo_master.md` *(it was recorded here as "19C Item 8" until 2026-09-08; that
was never true — Item 8 is 19C's input-boundaries work, and the contact sat unnumbered
in 19C's Future items, which closed with the segment)*. What is left is
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
| 6. Operator guide | **✅ shipped**, and **relocated 2026-09-06**: was `docs/quickstart.md`, now the in-app Guide at `/guide` (Segment 19E rung 2), with the file retired to `docs/archive/quickstart.md` | currency pass stays here, against the Guide |
| 7. Administrator guide | **partial, and host-dependent.** The material exists scattered across `docs/operations_runbook.md`, `docs/deployment_dev.md`, the NUS runbook (kept privately with the deployment), `docs/backup_restore.md`, `docs/security_posture.md`; there is no single administrator guide, and the one that matters describes the *institutional* host | **stays — the gated item** |
| 8. Developer setup guide | **✅ shipped** as `docs/local_setup.md` (322 lines) | done |
| 9. Troubleshooting guide | **✅ shipped for the dev slot** as `docs/troubleshooting.md`. Its failure modes are the personal-Azure ones; the institutional host will have its own (tenant, Easy Auth, NUS network policy) | institutional half stays here |
| 10. Known limitations page | **✅ shipped** as `docs/known_limitations.md` | currency pass stays here |
| + Technical-support contact (global) | **not built.** Mechanism is an env var + footer + error-page surfaces and needs no host; only the *address* is a deploy-time decision, and an unset var renders nothing | **`guide/todo_master.md` stub** (mechanism now, value at deploy) *(was "19C Item 8", corrected 2026-09-08)* |

---

## What remains in this segment

1. ~~**Administrator guide** for the institutional host~~ — removed
   2026-11-01: Cordware documents it. Standing the host up, its
   settings, releases, rollback and the runner are Cordware's
   `spec/cordware_setup.md` and `spec/release.md`, and what is asked of
   IT is its `docs/it_ask.md`. RRW is public and cannot name those
   resources. What an administrator does *in the app* (the allowlists,
   Accounts Management) is `docs/operations_runbook.md`, which item 3
   re-reads.
2. ~~**Troubleshooting, institutional half**~~ — moved 2026-11-01 to
   Cordware's `docs/troubleshooting.md`: Easy Auth behind the gateway,
   the Graph token, the database NSG, the gateway timeout, and the
   release and Azure-write failures. RRW's `docs/troubleshooting.md`
   keeps the application's own failure modes.
3. **Currency pass on the operator-facing docs** — the in-app Guide
   (`app/web/templates/guide.html`, canonical since 19E rung 2),
   `docs/known_limitations.md` and `docs/operations_runbook.md`, re-read
   against the deployed reality: the real sign-in flow, the Graph
   directory features, and limitations that are still limitations once
   the host exists. Host-neutral wording only. Re-scoping the deployment
   documents themselves (`docs/deployment_dev.md`, the dev-slot framing
   in `docs/troubleshooting.md`) is `guide/post_azure_todo_checklist.md`
   item 2's, not this item's.
4. ~~**Technical-support contact**~~ — deferred 2026-11-01 (author):
   the users are a whitelisted group in a citizen project, and they know
   whom to call. Recorded in `guide/deferred_consolidated.md`, "Contact
   and support". Absorbed from its
   `guide/todo_master.md` stub: a deployment-wide "something looks
   broken" address, distinct from the per-session help contact. It
   reuses `OPERATOR_CONTACT_EMAIL` (open question 2), shown on the chrome
   footer, the error pages and the invalid-link landing; **unset renders
   nothing**.
   The mechanism needs no host and can be built before the gate. Only
   the address waits for it, and is set in Cordware's App Settings
   (its `spec/release.md`, "Release settings").

## Status

Closed 2026-11-01 in one PR. Intended versus done:

- **Items 1 and 2** were removed or moved to Cordware before the build (above).
- **Item 4** was deferred (above).
- **Item 3**, the currency pass, was done against the deployed host:
  - `docs/known_limitations.md`: the deployment section was rewritten to the institutional host, and the dev slot's F1, public-database, plain-secret and no-log-workspace entries were struck. Its email entry now waits on the choice of sender, not on Azure.
  - `docs/operations_runbook.md`: re-scoped. The host's procedures belong to the private repository; the in-app administration and a host-neutral health check stay. `guide/post_azure_todo_checklist.md` item 2's row for it is done.
  - `app/web/templates/guide.html`: three passages said people are matched by "the address they sign in with". They now describe what happens: the upload binds a row to its directory account, by mail or sign-in name, and only an unbound row matches by sign-in mail (`spec/audience_and_identity_model.md`, "Identity match").
- **Reads:** one `diff-reviewer` read. It found no blocking defect and nine smaller findings, all acted on:
  - softened claims the public repository cannot check (the log workspace, the host's health-path exclusions, "a push deploys nothing");
  - a Guide note that a sign-in name needs the directory at save time;
  - the runbook's allowlist rule and Accounts Management guards stated exactly;
  - the SMTP-key rotation note restored.
  
  It also saw `docs/security_posture.md` still describing the NUS host before it served, which is post-Azure item 2's.

## Open questions

1. ~~**Is `/guide` public?**~~ **No** (author, 2026-11-01): it stays
   behind sign-in, and so does the starter-template download
   (`tests/integration/test_setup_template_download.py`). It is for
   operators and participants (author, 2026-11-01), as it is today:
   each role sees its own sections (19F decision 6).
2. ~~**Does the technical-support contact reuse `OPERATOR_CONTACT_EMAIL`?**~~
   **Yes** (author, 2026-11-01): one address, so item 4 shows the
   existing setting on the footer, the error pages and the invalid-link
   landing rather than adding one.

---

## Deliberately out of scope

- Anything that can be written or built without the host. That is the
  whole point of the 2026-09-05 split: if it does not need the
  deployment, it belongs in 19E / 19C, not here. Item 4's mechanism is
  the exception, kept beside the address it serves.
- Anything that names NUS resources: it belongs in Cordware (author,
  2026-11-01).
- Re-doing the four items the audit found already shipped. A currency
  pass over the Guide / `known_limitations` is not a rewrite.
- New feature work not in the workplan §18 list.

---

## Doc impact

Written 2026-10-05 against "What remains" above. The plan is reserved,
so `tools/close_check.py 20` reports these as not yet modified until the
segment builds.

- `docs/README.md` — a row for the new administrator guide (what remains, 1). <!-- doc-impact-waived: item 1 removed 2026-11-01; Cordware documents the host -->
- `docs/troubleshooting.md` — the institutional half appended (what remains, 2). <!-- doc-impact-waived: item 2 moved to Cordware's docs/troubleshooting.md, 2026-11-01 -->
- `docs/known_limitations.md` — currency pass against the deployed host
  (what remains, 3).
- `docs/operations_runbook.md` — currency pass: in-app administration against the deployed host (what remains, 3).
- `app/web/templates/guide.html` — currency pass: the real
  sign-in flow (what remains, 3).
- `spec/settings_inventory.md` — §8: `OPERATOR_CONTACT_EMAIL` also shown on the footer, the error pages and the invalid-link landing (what remains, 4). <!-- doc-impact-waived: item 4 deferred 2026-11-01; nothing about the setting changed -->
- `docs/README.md` — the `operations_runbook.md` and `known_limitations.md` rows match the re-scoped files (what remains, 3).
- `guide/todo_master.md` — delete the segment's queue entry (at close).

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
