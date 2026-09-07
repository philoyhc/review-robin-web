# Segment 19F — Reviewee participation disclosure

**Opened:** 2026-09-07 · **Theme:** a reviewee learns they are being reviewed only once something has been granted to them · **Related:** `spec/role_landing_and_visibility.md`, `spec/participant_model.md`, `spec/visibility_policy.md`, `guide/archive/participant_model_upgrade.md`

## Opportunity

An active reviewee sees a row for their session on `/me` — session name,
lifecycle status, a live link to `/me/sessions/{id}/results` — from the
moment an operator uploads the roster, in every lifecycle state, whether
or not any instrument grants them a view. The link is enabled
unconditionally and the surface answers 200. Recorded 2026-09-07 against
a running app and written up in `spec/role_landing_and_visibility.md`
§4: a reviewee on a `draft` session with **no `instrument_view_policies`
row at all** gets a listed, linked row.

That is a disclosure. The row tells someone they are the subject of a
review round, on a named session, before anyone has decided they may see
anything about it — and on an `archived` session, after the decision has
been withdrawn. Nothing about that is inferable from the reviewee's own
actions; they were put on a list.

**This was never the intent, and the code says so.** `_dashboard.py:192`
carries its own note:

> `# W16 will gate this on the responses_release_at / responses_release_until window; today the placeholder accepts any active reviewee.`

W16 shipped (PRs #1737–#1752); W17, carrying the same note for
observers, shipped 2026-06-02. Both placeholders outlived the work meant
to replace them and nothing noticed — the same failure mode
`docs/status.md` already records for a test skip that "outlived its
stated remedy by 104 days". This segment is that follow-up, arriving
late.

## Decision

**A reviewee's `/me` row and `/results` surface are gated on a
currently-resolving visibility grant.** Concretely: the `reviewee` role
contributes to a session's `/me` row only when
`visibility_policies.resolve_mode` returns non-`None` for at least one
instrument in that session, under the windows open *right now*. With no
such grant, the reviewee role is invisible — no row, no link, and
`/results` does not answer.

Four decisions from the author (2026-09-07), each with what it rules out:

1. **Currently, not ever-configured.** A grant that exists but whose
   window has not opened does not count. *Rejected: "any policy row
   exists"* — it would let an operator's setup-time decision disclose
   participation months before the reviewee may see anything, which is
   the disclosure being closed.
2. **Gate the role, not the row.** A reviewee who is also a reviewer or
   observer on the same session keeps the row; only the `reviewee`
   entry leaves `roles` and `role_links`. *Rejected: hide the whole
   row* — it would break two working surfaces to protect a third.
3. **A reviewee with no current grant is treated exactly as someone with
   no role at all**: they land on the generic empty `/me`. *Rejected:
   403 with the gate's existing "You are not an active reviewee in this
   session"* — that message confirms both that the session exists and
   that they are on it, which is the fact being withheld.
4. **Observers are not gated.** An observer may see that they are an
   observer before their window opens. *Rejected: symmetry with
   reviewees* — being appointed an observer is not a disclosure *about*
   the observer, so the privacy argument does not transfer. Their
   identical stale placeholder comment is corrected, not actioned.

**Landing rules, restated as the segment's invariant** — strangers and
participants always land on `/me`; operators, sys-admins and
super-admins always land on the session lobby. 19F must not change
either; it changes only what a participant's `/me` contains.

## Semantics

**"Currently resolving" is per session, not per instrument.** The role
survives if *any* instrument in the session grants the reviewee a mode
now. A session with ten instruments and one open grant is one visible
row, not one-tenth of one.

**Archive closes the row.** `is_archived` already forces every
non-operator grant off in `_reviewee_results.py`, so an archived
session's reviewee role resolves to nothing and the row leaves. That
falls out of decision 1 rather than needing its own rule, and it is the
behavior `spec/visibility_policy.md` already specifies.

**The row appears and disappears as windows move.** A reviewee sees
nothing during the review, then a row when the release window opens,
then nothing again if the operator closes it. This is the accepted cost
of decision 1 and must be stated in `spec/participant_model.md` so it
reads as designed rather than as a bug report waiting to happen.

**No grant ⇒ the route behaves as if the reviewee were not on the
roster.** Per decision 3 the reviewee lands on the generic empty `/me`;
whether that is a redirect or a 404 is PR 2's call, and either must
avoid a body that distinguishes "no grant" from "not a reviewee".

**A non-email-identified reviewee is unaffected** — they already hold no
reviewee role anywhere (`participants.is_email_identified`), so this
gate never sees them. The Validate page's
`reviewees.unreachable_for_results` warning keeps its current meaning.

**Operators are never gated by this.** The operator preview surfaces
resolve modes for their own purposes; 19F touches the participant path
only.

## Judgment calls — decided

- **Named a segment, not a 19C item** — 19C is behavior/contract polish
  and is closed; this is a participant-facing privacy contract with its
  own theme, which is the test the segment-plan skill sets.
- **Reviewee-only scope, observers explicitly excluded** — author
  decision 4. The observer placeholder comment is corrected in the same
  PR that touches its neighbor, because leaving a comment that predicts
  work already done is how this segment came to exist.
- **The known observer archive grant** (`spec/role_landing_and_visibility.md`
  §6 — `_observer_collation.py` has no `is_archived` short-circuit and
  resolves a live grant on an archived session) is **in scope as PR 3**,
  not deferred. It is the same file family, the same override, and the
  same one-line shape as the reviewee guard it should mirror.
- **No new "does any grant resolve" caching** — measure first. The
  dashboard runs three queries today; if the per-session resolution
  proves slow, that is a `## Status` finding and a follow-up, not a
  speculative index.

## Blast radius (measured)

Counted 2026-09-07 at `841bbfa0`, before the first slice.

| What | Count | Command |
|---|---|---|
| Callers of `resolve_mode(` | 4 | `grep -rn "resolve_mode(" app/ \| wc -l` |
| Modules importing it | 3 + its own | `grep -rln "resolve_mode(" app/` → `_observer_collation.py`, `_reviewee_results.py`, `_collation.py` |
| Callers of `require_reviewee_in_session` | 4 files | `grep -rn "require_reviewee_in_session" app/ --include=*.py` → `deps.py`, `_setup_reviewees.py`, `_results.py`, `views/_guide.py` |
| Templates on the `/me` path | 6 | `grep -rln "role_links\|/me/sessions" app/web/templates` |
| Tests hitting `/results` | 5 | `grep -rln "/results" tests/ --include=*.py \| wc -l` |
| Tests hitting the `/me` dashboard | 11 | `grep -rln 'get("/me")' tests/ --include=*.py \| wc -l` |
| Specs naming the results contract | 12 | `grep -rln "/results" spec/ \| wc -l` |

The 11 dashboard tests are the number to respect: most seed a reviewee
and assert a row. Each has to be re-read to decide whether it wants a
*reviewee* row or merely *a* row, and that reading is the bulk of PR 1's
work rather than the gate itself.

## PR ladder

1. **PR 1 — the predicate, and the `/me` role gate.** Lands a service
   predicate (`visibility_policies.reviewee_has_current_grant(db,
   session_id)` or nearest name) and applies it in
   `_dashboard.py` so the `reviewee` role drops out of `roles` and
   `role_links` when it returns False, with the row surviving on any
   other role. Re-reads the 11 dashboard tests. **Must not touch**
   `/results`, the observer path, or any landing redirect.
2. **PR 2 — the `/results` surface.** Makes the route behave as if the
   reviewee were not on the roster when no grant resolves, per decision
   3. **Must not touch** the `/me` dashboard or introduce a body that
   distinguishes "no grant" from "not a reviewee".
3. **PR 3 — the observer archive grant.** Mirrors the reviewee
   `is_archived` short-circuit into `_observer_collation.py`, closing
   the divergence `spec/role_landing_and_visibility.md` §6 records.
   Corrects the two stale `W16 will gate` / `W17 will gate` comments.
   **Must not touch** observer visibility in any non-archived state —
   decision 4 stands.
4. **PR 4 — specs.** The doc-impact files below. **Must not** change
   behavior.

Each rung leaves the app coherent: after PR 1 the row is gated and the
surface is still reachable by direct URL (a narrower disclosure than
today, not a wider one), and PR 2 closes it.

## Definition of done

- A reviewee with no currently-resolving grant sees no row on `/me` and
  cannot reach `/results`, asserted for `draft`, `ready` with no policy,
  and `archived`.
- A reviewee with a currently-resolving grant sees the row and reaches
  the surface, asserted for an open `while_ongoing` and an open
  `after_release` window.
- A reviewee who is also a reviewer on the same session keeps the row,
  with `reviewee` absent from its role chips.
- An observer's row and surface are unchanged in every lifecycle state
  except `archived`, where the grant is closed.
- Strangers and participants land on `/me`; operators, sys-admins and
  super-admins land on `/operator/sessions` — unchanged, asserted.
- No `W16 will gate` / `W17 will gate` comment remains:
  `grep -rn "will gate this" app/` is empty.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

## Open questions

- **`/results` with no grant: redirect to `/me`, or 404?** Decision 3
  fixes the *observable outcome* (indistinguishable from having no
  role); it does not pick the mechanism. PR 2 decides, and records which
  in `## Status`. A redirect matches "land on the generic empty `/me`"
  most literally; a 404 is the more conventional answer for a resource
  the caller may not know exists.
- **Cost of per-session resolution on `/me`.** Unknown until measured
  against a user on many sessions. Measured in PR 1; a regression is a
  `## Status` finding and a follow-up rung, per the judgment call above.

## Out of scope

- **Gating sign-in itself.** The author's decision (2026-09-07) is that
  everyone with an institutional MS365 account may sign in and the gate
  belongs after. Recorded in `spec/role_landing_and_visibility.md` §6 as
  the posture, not as a defect.
- **Observer participation disclosure** — decision 4. Not deferred
  pending a future segment; decided against.
- **Reviewer disclosure.** A reviewer is being asked to do work and must
  know about it; no equivalent question arises.
- **Any change to the landing rules.** They are the invariant 19F
  preserves, not the thing it edits.

## Doc impact

- `spec/participant_model.md` — the reviewee `/me` row and `/results`
  contract gain the current-grant precondition, including that the row
  appears and disappears as windows move (PRs 1, 2).
- `spec/role_landing_and_visibility.md` — §4's reviewee table is
  rewritten from "listed and linked in every state" to the gated
  behavior; §6 loses the observer-archive divergence once PR 3 closes it
  (PRs 1–3).
- `spec/visibility_policy.md` — the archive override's scope restated
  now that both non-operator audiences honor it (PR 3).
- `docs/status.md` — a row per rung as it lands.
