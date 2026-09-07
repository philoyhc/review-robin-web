# Segment 19F — Reviewee participation disclosure

**Opened:** 2026-09-07 · **Theme:** a reviewee learns they are being reviewed only once something has been granted to them · **Related:** `spec/role_landing_and_visibility.md`, `spec/participant_model.md`, `spec/visibility_policy.md`, `spec/audience_and_identity_model.md`, `guide/archive/participant_model_upgrade.md`

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
   no role at all.** *Rejected: a bespoke outcome for this case* — the
   whole point is that the two are indistinguishable, so whatever a
   stranger gets is what a no-grant reviewee gets.

   *Two corrections to this bullet, 2026-09-07, from probing the running
   app rather than reading it (see `## Status`).* It originally said the
   reviewee should "land on the generic empty `/me`" and rejected the
   gate's 403 because its message "confirms both that the session exists
   and that they are on it". Both were wrong. A stranger hitting
   `/results` does **not** land on `/me` — they get a 403 error page — so
   "treated as a stranger" and "land on `/me`" are different outcomes and
   only one can hold; the first is the governing intent. And the 403's
   message reads *"You are **not** an active reviewee in this session"*,
   which confirms the session exists and says nothing about membership.
   What it leaks is existence, and that is what decision 5 closes.
4. **Observers are not gated** *for disclosure*. An observer may see
   that they are an observer before their window opens. *Rejected:
   symmetry with reviewees* — being appointed an observer is not a
   disclosure *about* the observer, so the privacy argument does not
   transfer. Their identical stale placeholder comment is corrected, not
   actioned. Decision 5 still changes their gate's **failure code**,
   which is a different thing from gating them.

5. **Every session-scoped gate answers 404, not 403, when the caller
   holds no role on that session** (author, 2026-09-07). Today the split
   is 403 for "the session exists but you are not on it" and 404 for "no
   such session", so **any signed-in person can enumerate session ids**
   by reading the status code — measured against a running app across
   all four gates. Content does not leak; existence and count do. The
   author's rule: *if you do not have a role granting visibility, you
   should not be able to infer anything.* *Rejected: keep 403 and record
   the leak as posture* — it is a two-line change per gate against a
   principle the author states plainly, and "recorded" is how the W16
   placeholder survived two years.

   This reaches `require_session_operator` as well as the three
   participant gates: an operator who does not own session *n* can
   enumerate other operators' sessions by the same means, and the
   principle does not stop at the participant boundary.

6. **`/guide` closes to a viewer who resolves no audiences** (author,
   2026-09-07). A signed-in stranger currently sees the **whole** Guide —
   all eleven cards — while every role-holder sees only their own
   sections. That is backwards. It is 19E rung 7's fallback, shipped
   2026-09-06 and spec'd the same day — *"a viewer holding nothing sees
   everything"*, on the reasoning that an empty Guide serves nobody — and
   the author reverses it: it makes no sense to give a stranger more than
   a reviewer gets. A viewer whose audience set resolves empty is
   **bounced to `/about`**, and the chrome renders no Guide link for
   them.

   *Rejected: 404 on `/guide`* — the chrome offers that link to everyone
   (`base.html:3509`), and a 404 on a link the app itself just showed you
   is a worse answer than a redirect. *Rejected: render the shell with no
   cards* — precisely what rung 7 argued against, and it would leave the
   Guide's own "Signed in as" chrome sitting above nothing.

   `/about` is not a new destination: it has been the app's "signed in
   but no access" landing since 18R Item 6 retired `/request-access`, and
   it carries the identity and operator-contact note such a viewer
   actually needs. The bounce mirrors `require_operator`'s
   `OperatorAllowlistDenied` → 303 to `/me`.

   **This reverses a two-day-old decision, and the plan says so rather
   than papering over it.** The contract it overturns is written in
   `spec/audience_and_identity_model.md` (at rung 7) and in
   `spec/operator_ui_concept.md` (rewritten at 19E's close hours later).
   Both must say the opposite when 19F lands, and `## Status` must record
   a decision changing — otherwise the next drift sweep reads two
   rewrites of one paragraph in three days as a spec that cannot keep
   still.

7. **An archived session's observer row is present but unlinked**
   (author, 2026-09-07). Decision 4 keeps the observer's row in every
   lifecycle state, and archived sessions stay on `/me` for reviewers and
   observers alike (see `## Out of scope`), reading "not opened". PR 5
   closes the observer's archive grant, so `/collation` on an archived
   session is empty by construction and a live link to it is a dead end.
   The row renders unlinked, matching the reviewer's "not opened" row
   beside it. *Rejected: keep the link live* — it would be the only link
   in that table guaranteed to lead nowhere.

**Landing rules, restated as the segment's invariant** — strangers and
participants always land on `/me`; operators, sys-admins and
super-admins always land on the session lobby. 19F must not change
either; it changes only what a participant's `/me` contains. Decision 6
adds a **redirect**, which is a different thing: `/guide` is a page a
signed-in viewer navigates to, not a place anyone arrives at from
sign-in.

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
roster** — which, under decision 5, means a **404**. One code, one body,
for all four of: no such session, a session you hold no role on, a role
you hold with no current grant, and a role that has been made inactive.
A caller who can tell those apart can infer, and inference is the thing
being closed.

**404 is the only status these gates return on refusal.** The four
session-scoped gates (`require_session_operator`,
`require_reviewer_in_session`, `require_reviewee_in_session`,
`require_observer_in_session`) lose their 403s. The one-line `detail`
strings go with them: *"You are not an active reviewee in this session"*
answers the question it is refusing to answer.

**Not affected by decision 5:** `require_operator` (the workspace
allowlist) keeps its 303 to `/me` — it discloses nothing about any
session. `require_sys_admin` keeps its 403 — a caller who reaches it is
already inside the operator surface, so there is no session existence to
infer. Both stay as `spec/permissions.md` §5 has them.

**Logging is unchanged.** The gates' `permission denied` warnings keep
naming the gate, user and session. The point is what a *caller* can
infer, not what an operator can debug — and losing the log line would
trade one problem for a worse one.

**A non-email-identified reviewee is unaffected** — they already hold no
reviewee role anywhere (`participants.is_email_identified`), so this
gate never sees them. The Validate page's
`reviewees.unreachable_for_results` warning keeps its current meaning.

**Operators are never gated by the *visibility* rule.** The operator
preview surfaces resolve modes for their own purposes; decisions 1–4
touch the participant path only. Decision 5 is the exception and says so:
it changes `require_session_operator`'s failure code, not who may pass
it.

**The Guide gate rides the same predicate as the `/me` row.** A no-grant
reviewee must be refused `/guide` too, or the segment closes the row and
leaves the *For reviewees* card standing one page over — the same
disclosure, relocated. `visible_audiences()` already unions the operator
flag with `participants.roles_held_anywhere`, so the gate follows for
free **once that function is grant-aware**. It is not today: it returns
`reviewee` for any active, email-identified reviewee. That is the whole
reason the Guide rung lands after the predicate rung rather than first,
where its independence would otherwise put it.

**`roles_held_anywhere` stops meaning what it is called.** Once its
reviewee arm consults the visibility resolver, the function answers
*roles that currently grant something*, not *roles held*. It has exactly
one caller (`app/web/views/_guide.py`), so renaming it is contained — and
leaving the old name would put a lie one line above the gate that most
needs reading. The new name is a build decision; `## Status` records it.

**Nothing outside the chrome offers a non-operator a Guide link.** Seven
templates carry one besides `base.html` — six deep links into Guide
sections (`#guide-create_and_set_up` ×5, `#guide-give_access` ×1) from
the Setup and Instruments pages' `What this page is for` disclosures,
plus the lobby first-run card's — and every one of those pages is
operator-only already. So decision 6's markup work is exactly one
conditional, in the chrome link row.

**The archived observer link is not a new mechanism.** `_dashboard.py`
enables the observer link unconditionally today; decision 7 gives it a
lifecycle condition of the same shape the reviewer link already carries
(`session_status != "not opened"`).

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
  resolves a live grant on an archived session) is **in scope as PR 5**,
  not deferred. *(Said "PR 3" when written; the ladder named it PR 4 even
  then, and decision 6's rung shifted it to PR 5. Corrected 2026-09-07 —
  a rung number in prose is the first thing a re-cut ladder makes
  wrong.)* It is the same file family, the same override, and the
  same one-line shape as the reviewee guard it should mirror.
- **404 conversion is its own rung, landing first** (2026-09-07). It is
  independent of the visibility work, it is the change most likely to
  break tests in bulk, and shipping it alone means a bisect points at one
  commit rather than at a rung doing two things.
- **The gates keep logging what they refuse** — see `## Semantics`. The
  inference being closed is the caller's, not the operator's.
- **The Guide rung lands after the predicate rung, not first**
  (2026-09-07). Decision 6 reads like an independent change and is not:
  refusing a no-grant reviewee depends on `roles_held_anywhere` becoming
  grant-aware, which is PR 2's work. Landing it earlier would close the
  Guide to strangers while still handing a no-grant reviewee the *For
  reviewees* card — the disclosure this segment exists to close, moved
  rather than removed.
- **The reversal is recorded as a reversal** (2026-09-07). Two specs
  written in the previous 36 hours state the contract decision 6
  overturns. The `## Doc impact` bullets name them and say what they
  said, so a reader meets a decision that changed rather than a paragraph
  that would not settle.
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
| `403` assertions across tests | 47 in 21 files | `grep -rn "== 403" tests/ --include=*.py \| wc -l` |
| …of which assert a **participant** gate | 7, one file | `grep -rn "403" tests/integration/test_participant_deps.py \| wc -l` |
| Session-scoped gates losing their 403 | 4 | `require_session_operator`, `require_reviewer/reviewee/observer_in_session` in `app/web/deps.py` |

The 11 dashboard tests are the number to respect for the visibility
work: most seed a reviewee and assert a row. Each has to be re-read to
decide whether it wants a *reviewee* row or merely *a* row, and that
reading is the bulk of the `/me` rung rather than the gate itself.

**47 is not the 404 rung's number.** Most of those 403s belong to
sys-admin, owner-management and allowlist paths that decision 5 leaves
alone; only the participant file is certain, and the operator-gate
assertions have to be read individually to tell "not on this session"
(becomes 404) from "not a sys-admin" (stays 403). That triage is the
rung's real work, and the count above is the ceiling, not the estimate.

**Decision 6's own radius**, counted 2026-09-07 at `770c774d` — small,
and the smallness is the point: rung 7 put the whole audience question
behind one function.

| What | Count | Command |
|---|---|---|
| Callers of `roles_held_anywhere` | **1** | `grep -rn "roles_held_anywhere" app/ --include=*.py` → `views/_guide.py` |
| Test files naming it or `visible_audiences` | 1 | `grep -rln "roles_held_anywhere\|visible_audiences" tests/ --include=*.py` |
| Tests hitting `/guide` | 5 files | `grep -rln 'get("/guide' tests/ --include=*.py \| wc -l` |
| Templates with a `/guide` href | 8 | `grep -rln 'href="/guide' app/web/templates \| wc -l` |
| …of which are operator-only pages | 7 | six Setup / Instruments disclosures + the lobby first-run card |
| …leaving markup to change | **1** | the chrome link row in `base.html` |
| Specs naming `/guide` | 7 | `grep -rln "/guide" spec/ \| wc -l` |

One test **inverts** rather than adjusts:
`tests/integration/test_guide_scaffold.py::test_a_viewer_holding_no_role_sees_everything`
asserts `visible_audiences(db, viewer) == frozenset(AUDIENCES)`, which is
the contract decision 6 reverses. It should be rewritten in place, under
a name that says the opposite, rather than deleted — the assertion is
still the right assertion, pointed the other way.

## Status

**2026-09-07 — PR 1 shipped: every session-scoped gate answers 404.**
`require_session_operator`, `require_reviewer_in_session`,
`require_reviewee_in_session` and `require_observer_in_session` raise a
bare `HTTPException(404)` on refusal, byte-identical to the one they
already raised for an unknown id. The role-naming `detail` strings are
gone. `require_operator` (303) and `require_sys_admin` (403) untouched,
as planned; `grep -rn "HTTP_403_FORBIDDEN" app/web/deps.py` returns one
line, in `require_sys_admin`, and a test now asserts that rather than
leaving it to a reader.

**The triage came in at 24 assertions across 12 files, against a ceiling
of 47 across 21.** The ceiling was honest — the plan said so — and the
half that fell away is the half it predicted: sys-admin, owner-error and
allowlist paths that decision 5 leaves alone. Method worth keeping:
rather than grepping and judging each `403` by eye, the gates were
converted first and the **suite's failures were the triage**. A test
that failed was by construction one asserting a converted gate; nothing
had to be classified by reading, and nothing could be missed.

**Three findings, none of them the gates.**

- **A test that had never tested its contract.**
  `test_operator_lobby_access_gate.py::test_sys_admin_reaches_other_owners_per_session_route`
  asserted `!= 403` against `/operator/sessions/{id}/audit-log.csv` — a
  URL that does not exist and never has (the route is
  `…/export/audit_log.csv`, and 16C PR 1 moved it to plain
  `require_sys_admin` besides). It 404'd on routing, `!= 403` held, and
  the test passed green while exercising no gate at all: it would have
  passed with the sys-admin bypass deleted. It surfaced only because
  `!= 403` stops being falsifiable *at all* once no refusal is a 403, so
  the assertion had to be strengthened — and strengthening it turned it
  red. Rewritten to hit `owners/add`, which really does mount
  `require_sys_admin_or_session_operator`, and to assert the effect (the
  `session_operators` row appears) rather than the absence of one code.
  **The general lesson: a negative assertion about a status code is only
  as strong as the code's continued existence.**
- **`spec/permissions.md` had the threat model backwards, and that is
  why the vector survived review.** Its gate table argued that
  `require_session_operator` runs the membership check before the
  existence check "so a non-member sees 403, never a 404 that leaks
  existence". A 404 leaks nothing; the **403** is what confirms the
  session is there, and each `detail` confirmed it again in prose. The
  note is corrected in place with the old reasoning quoted, not deleted
  — a spec that was confidently wrong is more useful to the next reader
  than a spec that is silently right.
- **A sys-admin now gets a bare 404 on a link the app just showed them.**
  `sys_admin_sessions.html:31` links every session name to
  `/operator/sessions/{id}`, which sits behind `require_session_operator`
  — and `permissions.user_can_view_session` is strict owner membership,
  with no sys-admin exemption (18S Item 3, deliberately: a sys-admin
  self-adds through the audited adopt door, whose button is on that same
  row). Before PR 1 a non-owner sys-admin clicking that name got a 403
  page that explained itself. Now they get a bare 404 about a session
  they are looking at a list of. **This is a degradation PR 1
  introduces, not a break it exposes** — the link was already refused,
  just legibly. Not fixed here, because the fix is a decision:
  (a) stop linking the name for a non-owner sys-admin and leave Adopt as
  the only affordance — small, in the template, contradicts nothing; or
  (b) exempt sys-admins from the uniform 404, which conceals nothing
  from someone who can already enumerate every session on a dedicated
  page, but breaks decision 5's own `## Definition of done` grep. Author
  decides; (a) is the recommendation.

**Doc impact honoured at this rung** as the bullets tag it:
`spec/permissions.md` (gate table, §5 failure semantics, test index) and
`docs/security_posture.md` (denial-path index, plus the vector recorded
as found-and-closed with its severity and how it was found). The other
four doc-impact paths belong to later rungs and are untouched.

**Suite: 2,867 passed / 16 skipped**, up six for
`tests/integration/test_session_enumeration_gate.py` — the
indistinguishability property per gate, probing **both** an existing
session the caller holds no role on and an absent id, because a gate
answering 404 for one and something else for the other would pass a
one-sided check. Mutation-checked: regressing one gate to its old 403
turns three of the six red.

## PR ladder

1. **PR 1 — 404 on refusal, across all four session-scoped gates.**
   Lands decision 5 alone: `require_session_operator`,
   `require_reviewer_in_session`, `require_reviewee_in_session` and
   `require_observer_in_session` raise 404 with no role-naming `detail`.
   Triages the 47 `403` assertions and converts only those asserting
   "not on this session". **Must not touch** `require_operator`'s 303,
   `require_sys_admin`'s 403, the gates' logging, or any visibility
   logic. First because it is independent of the rest and is the rung
   most likely to move tests in bulk.
2. **PR 2 — the predicate, and the `/me` role gate.** Lands a service
   predicate (`visibility_policies.reviewee_has_current_grant(db,
   session_id)` or nearest name) and applies it in
   `_dashboard.py` so the `reviewee` role drops out of `roles` and
   `role_links` when it returns False, with the row surviving on any
   other role. Re-reads the 11 dashboard tests. **Must not touch**
   `/results`, the observer path, or any landing redirect.
3. **PR 3 — the Guide audience gate** *(added 2026-09-07 with decision
   6; every rung below shifts by one — what this plan first called PR 3
   is now PR 4, and so on)*. Reverses rung 7's no-role fallback:
   `visible_audiences()` returns an empty set for a viewer holding
   nothing, `/guide` bounces such a viewer to `/about`, and `base.html`
   stops rendering the Guide chrome link for them. Renames
   `roles_held_anywhere` to match what PR 2 made it mean. **Must not
   touch** the per-audience card filtering for viewers who *do* hold a
   role — that is rung 7's and it is correct. After PR 2, because the
   reviewee arm of the predicate is PR 2's.
4. **PR 4 — the `/results` surface** *(was PR 3)*. Makes the route answer
   404 when no grant resolves — the same 404 PR 1 established, so "no
   grant" and "not a reviewee" are one outcome. **Must not touch** the
   `/me` dashboard.
5. **PR 5 — the observer archive grant, and the unlinked archived row**
   *(was PR 4)*. Mirrors the reviewee `is_archived` short-circuit into
   `_observer_collation.py`, closing the divergence
   `spec/role_landing_and_visibility.md` §6 records, and lands decision 7
   by giving the observer's `/me` link the lifecycle condition the
   reviewer's already has. Corrects the two stale `W16 will gate` /
   `W17 will gate` comments. **Must not touch** observer visibility in
   any non-archived state — decision 4 stands.
6. **PR 6 — specs** *(was PR 5)*. The doc-impact files below. **Must
   not** change behavior.

Each rung leaves the app coherent. PR 1 narrows what every refusal
discloses without changing who passes. After PR 2 the reviewee row is
gated while the surface is still reachable by direct URL — a narrower
disclosure than today, not a wider one — and PR 4 closes that. PR 3 sits
between them because it depends on PR 2's predicate and nothing depends
on it; landing it there means the Guide and the dashboard agree about
who a no-grant reviewee is from the moment either of them changes.

## Definition of done

- All four session-scoped gates answer **404** on refusal, with a body
  indistinguishable from an unknown session id, asserted for each gate:
  `grep -rn "HTTP_403_FORBIDDEN" app/web/deps.py` returns only
  `require_sys_admin`.
- A signed-in caller cannot tell an existing session they hold no role on
  from a session id that does not exist, asserted by probing both.
- A reviewee with no currently-resolving grant sees no row on `/me` and
  cannot reach `/results`, asserted for `draft`, `ready` with no policy,
  and `archived`.
- A reviewee with a currently-resolving grant sees the row and reaches
  the surface, asserted for an open `while_ongoing` and an open
  `after_release` window.
- A reviewee who is also a reviewer on the same session keeps the row,
  with `reviewee` absent from its role chips.
- An observer's row and surface are unchanged in every lifecycle state
  except `archived`, where the grant is closed and the row renders
  **unlinked**, asserted beside the reviewer's "not opened" row.
- A viewer who resolves no audiences is bounced from `/guide` to
  `/about` and sees no Guide link in the chrome, asserted for a stranger
  **and** for a reviewee with no current grant.
- A viewer holding any role still reaches `/guide` and sees exactly their
  own sections — rung 7's contract, asserted unchanged.
- `grep -rn "roles_held_anywhere" app/` is empty: the function carries a
  name PR 2 made true.
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

- ~~**`/results` with no grant: redirect to `/me`, or 404?**~~
  **Resolved 2026-09-07 — 404**, by decision 5. The question was posed
  as a choice of mechanism for "indistinguishable from having no role";
  probing the running app showed a no-role caller gets a **403**, not a
  redirect, so neither original option matched. The author's answer moved
  the target instead: every refusal becomes 404, and matching it is then
  trivially correct. Recorded here rather than deleted because the
  question was the thing that surfaced the enumeration leak.
- **Cost of per-session resolution on `/me`.** Unknown until measured
  against a user on many sessions. Measured in PR 1; a regression is a
  `## Status` finding and a follow-up rung, per the judgment call above.

## Out of scope

- **Gating sign-in itself.** The author's decision (2026-09-07) is that
  everyone with an institutional MS365 account may sign in and the gate
  belongs after. Recorded in `spec/role_landing_and_visibility.md` §6 as
  the posture, not as a defect. Decision 5 is what makes that posture
  safe to hold: sign-in stays open, and what a signed-in stranger can
  learn from it drops to nothing.
- **`require_operator` and `require_sys_admin`.** Left as they are — see
  `## Semantics`. Neither discloses anything about a session.
- **Observer participation disclosure** — decision 4. Not deferred
  pending a future segment; decided against.
- **Reviewer disclosure.** A reviewer is being asked to do work and must
  know about it; no equivalent question arises.
- **Filtering archived sessions off `/me`.** Raised 2026-09-07 as a
  possible rung and **declined by the author**: reviewers and observers
  keep seeing an archived session as "not opened" until it is deleted.
  The *reviewee* role still leaves an archived session's row, but it
  leaves by the archive override closing the grant (see `## Semantics`),
  not by a filter — so the two roles diverging here is a consequence of
  decision 1, not a second rule.
- **Any change to the landing rules.** They are the invariant 19F
  preserves, not the thing it edits. Decision 6's `/guide` → `/about`
  bounce is a redirect off a navigated page, not a landing.

## Doc impact

- `spec/participant_model.md` — the reviewee `/me` row and `/results`
  contract gain the current-grant precondition, including that the row
  appears and disappears as windows move (PRs 1, 2).
- `spec/role_landing_and_visibility.md` — §3's Guide-audiences table
  loses its "no role → all four" row for the bounce to `/about` (PR 3);
  §4's reviewee table is rewritten from "listed and linked in every
  state" to the gated behavior, and its reviewee/observer table gains the
  archived observer row's unlinked state (PRs 2, 5); §6 loses the
  observer-archive divergence once PR 5 closes it (PRs 1–5).
- `spec/visibility_policy.md` — the archive override's scope restated
  now that both non-operator audiences honor it (PR 5).
- `spec/audience_and_identity_model.md` — the `/guide` audience contract
  **reverses**: a viewer holding nothing sees nothing and is bounced to
  `/about`. The entry that goes says *"a viewer holding nothing sees
  everything"*, written at 19E rung 7 on 2026-09-06; the replacement
  names it as superseded rather than quietly occupying its place (PR 3).
- `spec/operator_ui_concept.md` — the `/guide` role-filtering paragraph,
  itself rewritten at 19E's close on 2026-09-07, and the chrome link
  row's new conditional (PR 3).
- `spec/permissions.md` — §5 Failure semantics: the "not a session
  member; not an active participant" row moves from **403** to **404**,
  and §3's per-route matrix follows (PR 1).
- `docs/security_posture.md` — the permission matrix's failure codes, and
  the session-enumeration vector recorded as closed rather than
  undiscovered (PR 1).
- `docs/status.md` — a row per rung as it lands.
