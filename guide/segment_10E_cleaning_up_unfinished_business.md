# Segment 10E — Cleaning up unfinished business

**Status:** Forward-looking plan. Picks up the loose ends the audit at
`guide/archive/segment_1-10_unfinished.md` (2026-05-03) surfaced
across Segments 1–10. Land these before Segment 11 (export / audit
retention) starts so the operator surface settles cleanly.

This is a punch list, not a feature segment. Most items are small;
each lands as its own PR. Items with detail in
`guide/unfinished_business.md` are cross-referenced; new items the
audit surfaced are sketched here in just enough depth to act on, with
a note where they belong long-term.

---

## 1. Items already tracked in `guide/unfinished_business.md`

These have full Why / Where / Plan write-ups in the catalog. 10E pulls
them into a single segment-scoped queue.

| # | Item | Tier | Notes |
|---|------|------|-------|
| #5 | Audit-event `detail` schema convention | medium | spec/architecture.md write-up + incremental emitter migration |
| #6 | Decouple `invitations.py` from `Request` | small | bundles with #24 |
| #7 | CSRF decision write-up | small | one paragraph in `docs/authentication.md` |
| #8 | CSV email-validation drift | tiny | sets up #12 |
| #9 | `get_or_create_default_instrument` docstring refresh | tiny | 5-min cleanup |
| #10 | Thread `correlation_id` into deadline lazy-close | small | bundle with whichever route next touches `observe_deadline` |
| #12 | Reviewer/Reviewee CSV cross-table identity check | small | builds on #8 |
| #21 | UI consistency updates aligning with the new chrome | varied | umbrella for restyling the six canonical buttons + follow-ons |
| #22 | Home body rebuild + Option F relocation | medium | depends on #21 |
| #23 | Sessions-list Delete button doesn't actually delete | small | UX bug; route + template |
| #24 | Operator-editable email template editor | medium | has a help-contact source decision to settle first |

Tracking continues to live in `unfinished_business.md`. 10E only
ratifies the order — see §3 below.

---

## 2. New items surfaced by the audit (need an `unfinished_business.md` entry on first touch)

The audit found seven items that weren't tracked anywhere. Sketches
below; promote each to a full `unfinished_business.md` entry the
moment work starts so the catalog stays the source of truth.

### 2.1 AG Grid replacement of the reviewer table — Segment 8 unfinished

The workplan §11 explicitly listed AG Grid as the second half of
Segment 8 ("Now replace the simple table with AG Grid while keeping
the same save endpoint"). The first half (plain HTML table) shipped;
the second never did. The surface works without it, but the workplan
deferral was never formalised.

**Decision needed first.** Does AG Grid still belong on the roadmap,
or is the plain HTML table the design? If "still belongs," name a
target segment (10E, 11, 14, …). If "design," update the workplan +
`docs/status.md` "What's deliberately not yet there" to make that
explicit so a future agent doesn't re-scope it on autopilot.

### 2.2 Vanilla-JS autosave — Segment 8 follow-on

`docs/status.md` mentions it ("Follow-on PR after Segment 8") but no
plan owns it. Reviewer experience today requires explicit Save
clicks. Probably bundle with #2.1 if AG Grid lands; otherwise a
small standalone PR layering autosave over the existing `/save`
endpoint with debounce + last-saved indicator.

### 2.3 Queue-based batch invitation sending — Segment 9.2 work item #7

Workplan §12 named "Add queue-based batch sending." Never
implemented; today the outbox-write loop runs synchronously inside
the request. Probably folds into Segment 15 real-SMTP work since
that's when out-of-request send becomes load-bearing — but no plan
currently owns it. Either pin it to Segment 15 explicitly in
`docs/status.md` or carve it as its own item.

### 2.4 Operator UI to flip `Reviewer.status` / `Reviewee.status` to inactive

`docs/status.md` says "Not yet planned." The per-row inactive filter
is enforced defensively in assignment-generation and reviewer-surface
paths but operators have no UI to set the flag. A small Inactivate
button on each row of the Reviewers / Reviewees Manage pages would
do it, with an audit event on the flip.

### 2.5 Inline-editable rows — reviewers / reviewees / assignments Manage pages

The disabled "Edit" buttons across all three Manage pages are
placeholders today (Segment 9.4 deferred scope). Whatever pattern
lands here applies to all three. Probably the biggest item on this
list — needs a design pass before code. `docs/status.md` says "Not
yet planned; would slot before activation."

### 2.6 Sort-column UX for response / display fields

The Segment 10D plan flagged "semantics ('default row order on
reviewer surface') not yet decided" and the sort affordance never
landed. Low priority and not blocking — flag here so a future
instruments-page touch knows the prior decision lapsed and doesn't
re-decide it without context.

### 2.7 Local Postgres docker-compose for dev

`segment_05A.md` §3.5 explicitly deferred this; SQLite + the
`ci-postgres` job covers most needs. Recorded here so the deferral
isn't mistaken for a silent drop. Probably never lands; 10E either
confirms "won't fix" in `docs/status.md` or commits to a target
segment.

---

## 3. Suggested ordering (pre-Segment-11)

A pragmatic order. Smaller cleanups first to unblock review bandwidth,
decisions ahead of the work that depends on them.

1. **Tiny / 5-minute** — #9 (docstring), #8 + #12 (CSV email pair),
   #23 (sessions-list Delete button), #2.6 (sort-column status note),
   #2.7 (local-Postgres status note).
2. **Decisions** — #2.1 (AG Grid fate), #2.3 (queue-based send
   target), #7 (CSRF), #24 help-contact-source. Each is a few
   paragraphs in the right doc; together they unblock the rest.
3. **Small features** — #21 button restyle (sequenced before #22
   per the existing roadmap), #2.4 (Inactivate UI), #10
   (correlation_id on deadline close), #6 + #24 bundled (Request
   decoupling + email template editor).
4. **Medium features** — #22 (Home rebuild), #5 (audit-event
   detail schema convention + incremental emitter migration), #2.5
   (inline-editable rows — needs design pass first).

`#2.5` (inline-edit rows) is the only item that probably wants its
own segment plan before code lands, because the design pattern picked
will repeat across all three Manage pages.

---

## 4. Out of scope

- Anything in `docs/status.md` "What's deliberately not yet there"
  with a named target segment ≥11 (export, RuleBased,
  multi-instrument-beyond-10D, production hardening, real SMTP).
- New features not in the audit. 10E is closing books on Segments
  1–10, not opening new scope.