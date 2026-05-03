# Segment 11 — Cleaning up unfinished business

(Originally drafted as Segment 10E before the 2026-05-03 segment
renumber promoted it. Cross-references in older docs may still
point to "10E" by name.)

**Status:** Forward-looking plan. Picks up the loose ends the audit at
`guide/archive/segment_1-10_unfinished.md` (2026-05-03) surfaced
across Segments 1–10. Land these before Segment 12 (export / audit
retention) starts so the operator surface settles cleanly.

This is a punch list, not a feature segment. Most items are small;
each lands as its own PR. Items with detail in
`guide/unfinished_business.md` are cross-referenced; new items the
audit surfaced are sketched here in just enough depth to act on, with
the convention that each gets a full `unfinished_business.md` entry
the moment work starts.

**Scope cut (2026-05-03).** Two items originally listed here have
been officially deferred to Segment 15 and removed from the queue
below: inline-editable rows on the Manage pages (now
`unfinished_business.md` #25) and local Postgres docker-compose
(now `unfinished_business.md` #26). Both also appear in
`docs/status.md` "What's deliberately not yet there" with Segment 15
as the named target.

---

## Combined punch list (recommended grouping + ordering)

Tier 1 lands first because each item is genuinely 5 minutes and clears
review bandwidth for the bigger items. Tier 2 unblocks Tier 3 (each
decision answers a "should we X?" that Tier 3 work depends on). Tier 4
is the medium-sized work that wants the chrome / arch / surface
already settled.

### Tier 1 — Tiny / 5-minute cleanups

| Item | Source | Notes |
|------|--------|-------|
| **#9 — `get_or_create_default_instrument` docstring refresh** | `unfinished_business.md` #9 | Pointer fix at `app/services/assignments.py:402`. |
| **#8 + #12 — CSV email-validation drift + cross-table identity check** | `unfinished_business.md` #8 + #12 | Bundle: same `_parse_email` helper. #8 sets up #12. |
| **#23 — Sessions-list Delete button doesn't actually delete** | `unfinished_business.md` #23 | Convert `<a>` → POST `<form>` with `onsubmit="return confirm(...)"`. |
| **2.6 — Sort-column UX status note** | This file (was §2.6) | Decide & document in `docs/status.md`; semantics never landed. |

### Tier 2 — Decisions (each unblocks Tier 3 or 4 work)

| Item | Source | Decision needed |
|------|--------|-----------------|
| **2.1 — AG Grid fate** | This file (was §2.1) | Still on the roadmap (name a target segment), or "the plain HTML table is the design" (update workplan + `docs/status.md`)? |
| **2.3 — Queue-based batch invitation sending** | This file (was §2.3) | Pin to **Segment 15** with real-SMTP work (recommended), or carve as its own item before then? Workplan §12 work item #7 named it but no plan owns it today. |
| **#7 — CSRF decision write-up** | `unfinished_business.md` #7 | Easy Auth + SameSite cookies, or CSRF tokens? If "tokens," that becomes its own segment. |
| **#24 — Help-contact merge field source** | `unfinished_business.md` #24 (open question section) | Per-session field on `ReviewSession`, per-operator field on `User`, or global env var? Settles before email template editor coding starts. |

### Tier 3 — Small features

| Item | Source | Notes |
|------|--------|-------|
| **#21 — Six canonical button restyle** | `unfinished_business.md` #21 | Sequenced before #22 per existing roadmap (Home rebuild uses these buttons). |
| **2.4 — Operator Inactivate UI** | This file (was §2.4) | Per-row Inactivate button on Reviewers / Reviewees Manage pages with audit event on flip. |
| **#10 — `correlation_id` into deadline lazy-close** | `unfinished_business.md` #10 | Bundle with whichever route refactor next touches `observe_deadline`. |
| **#6 + #24 — Decouple `invitations.py` from `Request` + email template editor** | `unfinished_business.md` #6 + #24 | Bundle: #6 cleans the surface that #24 then extends. Depends on Tier 2 #24 help-contact decision. |

### Tier 4 — Medium features

| Item | Source | Notes |
|------|--------|-------|
| **#22 — Home body rebuild + Option F relocation** | `unfinished_business.md` #22 | Depends on Tier 3 #21 (chrome buttons settled first). 4–6 small PRs. |
| **#5 — Audit-event `detail` schema convention** | `unfinished_business.md` #5 | Spec write-up in `spec/architecture.md` then incremental emitter migration. Segment 12 export needs this stable. |
| **2.2 — Vanilla-JS autosave on `/save`** | This file (was §2.2) | Depends on Tier 2 #2.1 AG Grid decision: bundle if grid lands; otherwise standalone debounce + last-saved-indicator PR. |

---

## Promote-to-`unfinished_business.md` convention

Items above sourced "This file (was §N)" don't have a full `Why /
Where / Plan` write-up yet — they live as sketches here. The
moment work starts on one, promote it to a full
`unfinished_business.md` entry first so the catalog stays the source
of truth and Segment 11 retires gracefully.

---

## Out of scope

- Anything in `docs/status.md` "What's deliberately not yet there"
  with a named target segment ≥12 (export, RuleBased, production
  hardening, real SMTP).
- The two deferrals above (inline-edit rows / local Postgres
  compose) — see `unfinished_business.md` #25 + #26 and the Segment
  15 stub.
- New features not in the audit. Segment 11 is closing books on
  Segments 1–10, not opening new scope.
