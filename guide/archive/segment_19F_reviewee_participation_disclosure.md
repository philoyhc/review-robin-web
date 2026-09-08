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

   **Amended at build, 2026-09-07 — sys-admins are exempt, on
   `require_session_operator` only.** PR 1 surfaced that
   `sys_admin_sessions.html` links every session name to the route this
   gate guards, so the uniform 404 turned a link the app renders into a
   dead end for the one role whose job is workspace oversight. The
   author's reason: *the whole point is that they should be able to see
   what's going on in the workspace as a whole.* A 404 conceals nothing
   from someone reading a page that lists every session by name. They
   get the old 403, reworded to name the adopt door (18S Item 3).
   *Rejected: option (a), unlinking the name for a non-owner sys-admin*
   — it removes an affordance to protect information the same page
   already shows.

   Two things keep the exemption narrow, and both are asserted:
   it sits **behind an existence check**, since without one it would
   answer "you are not an owner of this session" for ids that never
   existed — a worse leak than the one being closed; and it is
   **`require_session_operator` only**, because nothing in the app
   routes a sys-admin to `/results` or `/collation`, so the three
   participant gates have no affordance to keep legible and answer 404
   to everyone. Super-admins need no branch of their own: both sign-in
   paths in `get_or_create_user` force `is_sys_admin` for them.

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

8. **The response-release window requires the session to have closed**
   (author, 2026-09-07, from probing what PR 2 had actually shipped).
   The two visibility windows mean literally *as data is coming in*
   (`while_ongoing` = `ready`) and *after the review has closed*
   (`after_release` = `expired`). Until now the second checked only the
   anchors, so any path that wrote them without the Release button
   opened a window the UI would never offer.

   **This was already the Workflow card's rule.** It gates both Release
   and Stop-release on `is_expired`, with a comment saying "responses
   are released *because the session is over*". Only the predicate
   disagreed — so this closes a gap between two halves of the codebase
   rather than introducing a new position.

   **The case that prompted it:** `revert_session_to_draft` accepts
   `expired` → `draft` and does **not** clear `responses_release_at`. An
   operator who reverts believes the session is withdrawn, back to
   before activation — and it went on showing released responses to
   every non-operator audience. *Rejected: clear the anchor on revert*
   — the anchor is a schedule, not a state; leaving it inert means
   re-closing the session re-opens the window on the schedule the
   operator set, which is what "release at time T" should mean.
   *Rejected: gate only the reviewee predicate* — the windows' meaning
   is global, and a rule that held for one audience and not the other
   two would be the same divergence in a new place.

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

**2026-09-07 — closed (#2187). Intended versus done.** The ladder was
planned as five rungs and shipped as **eight**: PR 2a (the window
correction, folded in at the author's direction), PR 3 renumbered when
decision 6 arrived, and PR 7 added during the close itself. Every rung
in the plan shipped; nothing was struck. The scope grew twice, both
times because probing the running app contradicted the plan — decision 5
(the uniform 404) and decision 6 (the Guide bounce) were both author
decisions taken mid-build, and both are recorded above.

**Five specs the plan never named**, against nine it did:
`spec/reviewer-surface.md`, `spec/architecture.md` and
`spec/rrw_functional_spec.md` at PR 6; `spec/role_navigator.md` at
PR 7; `spec/lifecycle.md` at the close. `close_check` caught exactly one
of the five, and only because `spec_registry.py` maps the module that
changed. **A manifest is written from the routes a change is expected to
touch, and a rename travels further than that** — the other four came
from grepping the retired names and from the close's `spec-writer` pass.

**The `spec-writer` pass found a defect, not a doc slip.** Its four
confirmed drift items were adjudicated one by one against the code;
three were prose. The fourth was `build_role_chips` answering from
roster membership alone, which became **PR 7** — the segment's own
contract, applied on `/me` and not on the chip strip. A close that only
reads prose would have missed it, because the prose was describing the
code correctly.

**Two DoD lines need reading rather than running.**

- *"`grep -rn "roles_held_anywhere" app/` is empty"* — it is **not**
  empty, and should not be. Two docstrings cite the retired name as
  history (`participants.py`, `deps.py`). The line's intent — no
  callable, no definition, no import by that name — holds:
  `grep -rn "roles_held_anywhere(" app/` is empty. A grep for a bare
  identifier cannot tell a use from a mention of a use.
- *"no `W16 will gate` / `W17 will gate` comment remains"* — true of
  that phrasing. PR 7 found `_shared.py` carrying *"the W16 / W17 gates
  will land later"*, which says the same thing and passes the grep.
  **A grep-shaped tripwire only catches the phrasing it was written
  for**; this is the second time in one segment (PR 5's comment quoting
  the phrase was the first).

**Two findings out of scope, recorded here rather than fixed.** Both
came from the close's audit of the chip across twelve reviewee
conditions, run against rendered pages:

1. **A reviewee `while_ongoing` grant can be imported, and the editor
   would reject it.** `visibility_policies` validates the
   `(audience, window)` cell on the editor path and refuses
   `reviewee` + `while_ongoing` outright; the Settings-CSV importer
   (`session_config_io/_apply_instrument.py`) writes policy rows
   straight from the parsed spec with no such check — the parser
   validates the vocabulary, not the cell. Driven end to end,
   `apply_session_config` returns `errors == []`, and on a `ready`
   session the reviewee then gets a `/me` row and a **200 on
   `/results`** — reading responses mid-flight, the state decision 3
   exists to prevent. **Not 19F's**: it dates from 18P PR A2 and would
   have rendered values mid-flight before this segment too; 19F's
   predicate merely honours the row like any other. The fix is a
   validation call on the import path plus a decision on what an
   offending row should do (reject the import, or coerce the cell to
   `None`) — a choice for the author, and **rehydrate** applies its
   settings bundle through the same call.

   *(Corrected 2026-09-08. This read "and the same door serves clone
   and rehydrate". Rehydrate yes — `session_rehydrate.py:515` calls
   `apply_session_config`. **Clone no**: `clone_session` copies no
   view-policy rows at all, which `spec/roundtrip_coverage.md` already
   recorded — "Clone still doesn't copy it — a clone reverts to default
   visibility". The claim was wrong when written, not made wrong later,
   which is why it is corrected here rather than left standing as a
   dated record. **Resolved 2026-09-08 as 19C Item 9** (#2188): the
   author chose reject-with-a-named-error, and the guard landed in the
   parse phase.)*
2. **The archived reviewer surface renders no chip strip.** It serves
   `reviewer/pre_open.html`, which has never included the partial
   (unchanged since `f2899b07`), so a multi-role user loses the
   navigator on that one page. Cosmetic, pre-existing, no disclosure.

**One correction made at close.** `release_responses_now`'s docstring
said release windows "are orthogonal to `draft / validated / ready /
expired`". PR 2a made that false — the window it stamps opens only while
the session is `expired` — so the docstring was corrected. The call
itself is unchanged, and the Workflow card only ever offered the button
on an expired session, which is why nothing broke.

**2026-09-07 — PR 7 shipped: the chip strip, found by the close's
`spec-writer` pass and not by the ladder.** `build_role_chips`
(`app/web/routes_reviewer/_shared.py`) had been answering from roster
membership alone: `enabled: True` for the reviewee and observer chips,
no grant check, no archive check. So a user who was an active reviewer
**and** an ungranted reviewee on the same session opened the reviewer
surface and was shown a live **Reviewee** chip — a link to the 404 PR 4
had just introduced, and, more to the point, a statement that they are
a reviewee here, which is precisely the disclosure PR 2 had closed one
surface over.

**The chip is omitted, not greyed.** Greying it would keep making the
statement; the dashboard drops the role from `roles` rather than
disabling its link, and the strip now matches. The observer chip does
the opposite — present, greyed on an archived session — because being
an observer is not a disclosure about the observer (decision 4), and
that asymmetry is the same one decisions 1–4 already carry.

**A test asserted the defect.**
`test_collation_chips_show_reviewee_when_user_holds_both` set up exactly
this pairing on a `draft` session and asserted the live anchor. It was
written before PR 4 made the target refuse, and no rung revisited it —
the suite was pinning the bug in place. Rewritten as a pair (absent
without a grant, present with one), plus four unit tests on the builder
for the archived-observer case, which no participant surface can
reach: archive closes the reviewee grant so `/results` 404s, and on
`/collation` the observer chip is the active one and carries no link
either way.

**Why the ladder missed it.** The blast radius counted `role_links` in
`_dashboard.py` and stopped there. The chip strip asks the same
question from a different function on a different surface, and
`git log -- app/web/routes_reviewer/_shared.py` shows no 19F commit
before this one. Its docstring still read *"the W16 / W17 gates will
land later"* — a stale marker of exactly the kind that started this
segment, and one that slipped past PR 5's `will gate this` grep because
it is phrased differently. **A grep-shaped tripwire only catches the
phrasing it was written for.**

**2026-09-07 — PR 6 shipped: the specs pass, and it found a spec the
plan never named.** `close_check.py 19F` passes on the manifest, but
emits two notes: `_dashboard` and `_results` touched, with
`spec/reviewer-surface.md` absent from `Doc impact`. That file is what
`spec_registry.py` maps both modules to, and the segment rewrote both —
twice each. **Undeclared spec impact is the exact failure the section
exists to prevent**, and the manifest passing while the note fired is
worth noting on its own: the check verifies commitments kept, not
commitments complete.

**Six stale claims in it, none cosmetic:**

- the `/me` cross-role union described the three rosters as
  symmetric — reviewee rows are grant-gated now;
- the reachability table said `reviewee` and `observer` links are
  "always `True`", both now conditional;
- the "View responses" column was a placeholder waiting for a
  release-window gate — which landed on the *row* instead, making a
  dedicated column a restatement;
- the `/results` gate was documented as
  `require_reviewee_in_session` returning **403**, three changes out
  of date;
- the observer gate's **403** likewise; and
- the claim that W16 applies its window inside the per-instrument
  render "not at route-level 403" — precisely what PR 4 reversed.

**Three 403s in that file are correct and were left alone**, checked
against the code rather than swept: the reviewer Save/Submit/Clear
refusals (`_surface/_context.py`, post-gate route checks on a caller
already confirmed as a reviewer) and the invitation-mismatch page. A
segment that converts status codes creates a strong pull to convert
every mention of one; the discipline is to grep, then read each.

**Also qualified:** the claim that the invitation-mismatch page is "the
only reviewer-side page that returns a non-200 under normal flow". Still
true for a caller in the right place, but `/results` now 404s an
ungranted reviewee, so the sentence needed the distinction rather than a
deletion.

**Then a name sweep found two more undeclared specs.** Grepping the
retired `roles_held_anywhere` and the superseded
`require_reviewee_in_session` across `spec/` and `docs/` turned up
`spec/architecture.md` (twice — the reviewee-results entry and the
participant-gate summary, neither mentioning the 404) and
`spec/rrw_functional_spec.md`. Both added to `Doc impact`. Three
undeclared paths in one segment is the number worth remembering: the
manifest is written at planning time from the routes a change is
*expected* to touch, and a gate rename propagates further than that —
`close_check` caught one of the three, and only because
`spec_registry.py` maps the module. The other two needed the grep.

**Left alone, deliberately:** `docs/status.md`'s historical timeline
rows still say `roles_held_anywhere` and "a viewer holding nothing sees
everything". Those are dated records of what shipped at the time, not
current claims, and rewriting them would falsify the history this
segment keeps citing. The distinction is between a spec, which must be
true now, and a log, which must be true of its date.

**2026-09-07 — PR 3 shipped: the Guide audience gate** (built last,
after 5, since the ladder's numbering fixed its dependency and not its
date). `visible_audiences` returns an empty set for a viewer holding
nothing, `/guide` bounces them to `/about` with a 303, and the chrome
stops offering the link.

**The plan was wrong about the starting point, and the correction is the
rung's real work.** It said PR 3 "renames `roles_held_anywhere` to match
what PR 2 made it mean". PR 2 never touched that function — it gated
`_dashboard.py` directly. So the rename had nothing to rename *to* until
the reviewee arm was actually made grant-aware here, which is what makes
the footnote case work: without it a reviewee granted nothing still
resolves the `reviewee` audience and is handed a *For reviewees* card,
and 19F's disclosure moves one page over instead of closing. Renamed to
`disclosable_roles`, whose docstring carries the reviewer/observer vs
reviewee asymmetry as decisions 2–4 rather than as an inconsistency.

**The blast radius was right about hrefs and wrong about audiences.** It
counted eight templates carrying a `/guide` href, seven of them
operator-only, "leaving 1 — the chrome link row in `base.html`". True,
and beside the point: participant surfaces override `top_bar` with
`reviewer/_top_bar.html`, which carries **no Guide link at all**. So
gating `base.html` alone changes nothing a stranger sees on `/me`. My
first chrome test asserted against `/me` and failed for exactly that
reason. Counting where a string appears is not the same as counting
where an audience meets it.

**Two defects found on `/about` by rendering it, both fixed here.** The
page depended on `get_current_user`, so (1) it had been rendering
*"Signed in as "* with an **empty name** — the identical defect 19E rung
7 found and fixed on `/guide`, in the sibling route nobody re-checked —
and (2) it never stamped the chrome flag, so a stranger bounced there
from `/guide` was offered a link straight back to the page that bounced
them. A visible loop, and the rung would have shipped it. Repointed at
`get_or_create_user`, which fixes both.

**The chrome flag fails open by construction.** It is stamped as
`guide_hidden` (a hide flag, not a show flag) and read as
`is not true`, so a page that never reaches `get_or_create_user` renders
the link and the route's redirect decides. Failing closed would hide the
Guide from operators on any page that missed the stamp — worse, and
silent.

**One test inverted, exactly as the plan predicted.**
`test_a_viewer_holding_no_role_sees_everything` was the single test the
blast radius named as needing inversion rather than adjustment, and it
was the single failure the change produced. Rewritten in place under the
opposite name, with rung 7's reasoning quoted so the reversal reads as a
decision that changed.

**One FastAPI detail:** annotating the route `-> HTMLResponse |
RedirectResponse` breaks collection outright — FastAPI builds a response
model from the return annotation and a union of two response classes is
not a valid Pydantic field. Annotated `Response` instead.

**Tests: 2,900 passed / 16 skipped**, up 4. Mutation-checked three
ways — restoring the all-audiences fallback turns 3 red; dropping the
grant check from the reviewee arm turns the ungranted-reviewee test red;
putting `/about` back on the header-derived user turns the chrome test
red.

**Doc impact honoured at this rung:** `spec/audience_and_identity_model.md`
(the reversed contract, the reviewee asymmetry, the rename),
`spec/operator_ui_concept.md` (the filter paragraph and the chrome row's
new condition, including that only `base.html` ever carried the link),
and `spec/role_landing_and_visibility.md` §3.

**2026-09-07 — PR 5 shipped: the observer archive short-circuit and
the unlinked archived row.** The headline is that **the divergence this
rung existed to close was already closed** — by PR 2a, as a side effect
of a different decision.

`spec/role_landing_and_visibility.md` §6 recorded
`_observer_collation.py` resolving a live `"raw"` grant on an archived
session, because `is_response_release_window_open` was purely
anchor-based. PR 2a made that window require `expired`; archived is not
expired, so both window predicates now return `False` and no grant
resolves. **Verified against a running app before rewriting the entry**
rather than inferred — the same rule that has caught two wrong
statements earlier in this segment. §6 now records the divergence, what
actually closed it, and that the closing change was not the one written
for it.

**The short-circuit landed anyway, as defence in depth**, and the plan
should be read as amended on that point: it is no longer a fix. Without
it the archive rule is *emergent* — true only while two predicates in
`session_lifecycle` keep refusing archived sessions, which is a property
of those functions and not of this view. Stated locally it survives a
relaxation of either.

**Testing something unobservable.** A test for the short-circuit cannot
fail by deleting the line, since 2a already produces the same output —
so the test simulates the future it insures against, monkeypatching a
window predicate to admit an archived session. With the line, no
sections; without it, `"raw"` resolves and §6's divergence returns. That
is the only condition under which the line is observable, and it is the
only mutation-sensitive test of the three.

**Two vacuous-test traps, both caught before they were believed.** The
first draft seeded the observer with `cohort_rule={"rules": []}` —
`observer_has_rule` returns False on an empty list, so the view returned
before the archive branch and **all three tests passed without reaching
the code under test**. The mutation check is what exposed it: removing
the short-circuit changed nothing. The second was a positive control
asserting `sections != []`, which needed a real cohort *and* real
assignments to be meaningful; rather than rebuild that fixture in a unit
file it now points at the integration test that already does it, and
asserts something the unit level can actually settle — that
`cohort_empty` stays `False`, since `True` would render *"No cohort is
configured for you yet"* and blame the operator for something that is
configured. That value was chosen by reading the template, not guessed.

**Decision 7 landed** as one condition on the observer's `/me` link:
live in every state but `archived`. Neither behaviour had any test
before this rung — the change produced zero failures, which is how that
was discovered — so both directions are now pinned.

**The Definition-of-done tripwire caught me quoting it.** That line
reads `grep -rn "will gate this" app/` is empty — and both replacement
comments I wrote *quoted the retired marker* to record what had stood
there, which left the grep matching my own prose and the check
permanently failing. Reworded to describe the marker without repeating
the phrase. A cheap mistake, but the general shape is worth keeping: a
check that greps for a string is defeated by any comment explaining the
string, so the two cannot both exist.

**Tests: 2,896 passed / 16 skipped**, up 5.

**Doc impact honoured at this rung:** `spec/role_landing_and_visibility.md`
(§4 observer table, §6 divergence closed with its history) and
`spec/visibility_policy.md` §3.3 (the override is now enforced in two
places, and why the redundancy is deliberate).

**2026-09-07 — PR 4 shipped: `/results` answers 404 without a grant.**
`require_reviewee_with_current_grant` composes the roster gate with
`reviewee_has_current_grant`, and **both** the GET and the
`POST .../acknowledge` companion depend on it. Kept as a separate
dependency rather than folded into `require_reviewee_in_session`: that
gate answers a roster question and its name says so, and merging them
would leave a gate promising less than it did — the trap
`roles_held_anywhere` is being renamed out of at PR 3.

**A deliberate feature is retired here, and it deserves naming.** The
old `test_results_body_window_closed_shows_scaffolding_without_values`
pinned a *pre-release scaffolding* view: with a policy authored on
`after_release` but the window not yet open, the section rendered the
reviewer rows — **names and emails** — with only the values hidden
behind muted em-dashes. `_reviewee_results.py` described it as
intentional, "a preview the operator can use". But it is the reviewee's
own surface, and it told them who was lined up to review them before
anyone had granted them anything: a sharper disclosure than the `/me`
row this segment started from. PR 4 leaves it no state to render in.
Recorded, not silently dropped — if the preview is wanted, it belongs
on an operator surface, where previewing what a reviewee *will* see is
unobjectionable.

**Ten tests moved; four had premises that no longer exist.** The four
were all "the page renders but shows nothing" cases — no policy row,
pre-release, and two explicitly-closed windows. Each now asserts 404,
with the old intent kept in the docstring, because "renders empty" and
"does not open" are different disclosures and the tests were pinning
the weaker one.

**A second dead branch, and this one was relocated rather than
retired.** `test_results_reviewer_chip_disabled_when_session_not_opened`
asserted a greyed reviewer chip on `/results` for a draft session —
unreachable now, since `/results` implies a grant, which implies
`expired`, where that chip is live. But unlike the fall-through at
PR 2a the branch is **not** dead in general: an observer can open
`/collation` on a draft session and see exactly that chip. So the case
moved to `/collation` instead of being rewritten away, and the
`/results` test now asserts the chip is always live there. Worth the
distinction — deleting it would have dropped live coverage.

**One self-inflicted scare worth recording.** Restoring a mutation with
`git checkout <file>` reverted the rung's own edits to that file, not
just the mutation, and the suite caught it three steps later — seven
failures where one was expected. Backups for mutation checks now go
through `cp`, never `git checkout`, since the working tree holds
uncommitted work by definition at that point.

**Tests: 2,891 passed / 16 skipped**, up 4. Mutation-checked twice:
no-opping the grant check turns 7 red; pointing only the POST back at
the roster gate turns exactly the acknowledge test red.

**Doc impact honoured at this rung:** `spec/participant_model.md` (the
gate, the shared companion route, and the retired scaffolding) and
`spec/role_landing_and_visibility.md` §4.

**2026-09-07 — PR 2a shipped: the response-release window requires
`expired`.** Decision 8, and it came from the author reading PR 2's own
write-up rather than from the plan: the claim that a `draft` session
could show a reviewee a row was true, and prompted the question of
whether it should be.

**The answer was already in the codebase, twice, disagreeing with
itself.** `_workflow_card.py` gates Release and Stop-release on
`is_expired` and explains why in a comment — "responses are released
*because the session is over*". `is_response_release_window_open`
checked only the anchors. So the UI and the predicate had held opposite
positions since the release window shipped, and every path that writes
the anchors without the button — Quick Setup, Session Edit, and
critically `revert_session_to_draft` — opened a window the card would
never have offered. PR 2a moves the rule into the predicate, which is
the only place all five callers pass through.

**The concrete defect, which the author intuited before the code was
read:** reverting a released session to draft leaves
`responses_release_at` stamped, so a *withdrawn* session went on showing
released responses to reviewees and observers alike. Now inert. The
anchor is deliberately not cleared — it is a schedule, not a state.

**Two consequences neither of us named when deciding.**

- **The Reviewer → Reviewee fall-through is now dead code.** A reviewee
  link exists only on an `expired` session; on `expired`,
  `session_status_for_reviewer` returns `"closed"`, which *enables* the
  reviewer link. So every state carrying a reviewee link also carries a
  live reviewer link, and reviewer is first in priority order. The test
  that covered the fall-through is **rewritten to assert the new truth**
  rather than deleted, and says why. Reviewee → Observer is still
  reachable.
- **A test had to change vehicle, not just setup.**
  `test_session_status_pills_are_visibly_styled` built `draft` / `ready`
  / `expired` rows out of reviewees; two of those states can no longer
  carry a reviewee row at all. Switched to observers, who are not
  grant-gated (decision 4), which preserves exactly what it tested —
  `_non_reviewer_session_status` is shared.

**25 tests moved**, all of them sessions that opened a release window
without closing the session. The fixture absorbed 8 of them:
`grant_reviewee_visibility` now closes the session as part of granting,
because closing *is* part of what a grant means and a caller who
forgets it would read the result as a bug in the gate.

**Left permissive on purpose:** `release_responses_now` still accepts a
call on an unclosed session — it stamps the anchor and the window stays
shut. Guarding it too would put the rule in two places, and the import /
apply-config paths write these columns as well. Pinned by a test that
the call is inert and that closing later opens it.

**The `while_ongoing` correction rides along**, as the author directed:
`spec/visibility_policy.md` defined it as `[activated_at, deadline)`,
which the code has never implemented — `lifecycle.is_ready` reads the
status column. The difference is observable, because `expire_session` is
only ever called from the Close button and never automatically at the
deadline: a session past its deadline that nobody closed is still
`ready`, and still inside the window. Spec corrected to match, with the
old definition and the reason quoted.

**Tests: 2,887 passed / 16 skipped.**

**2026-09-07 — PR 2 shipped: the reviewee role is gated on a
currently-resolving grant.** `visibility_policies.reviewee_has_current_grant(db,
review_session)` is the predicate the plan named, built where the plan said
and answering the session-level question — *is there anything for a reviewee
to see here right now*. `_dashboard.py` filters the `reviewee` `_add` through
it, so the role leaves `roles` and `role_links` together and the row survives
on any other role the user holds (decision 2). One query per reviewee session,
and often none: when neither window is open the predicate returns before
touching the policy table.

**The dashboard triage was 6 tests, not the 11 the plan flagged.** The plan
said all 11 dashboard tests would have to be re-read to decide whether each
wanted *a* row or a *reviewee* row; in the event only 6 failed, because the
rest seed reviewers or observers. Each of the 6 wanted a reviewee row, so all
6 took a grant rather than a rewrite. The re-reading the plan budgeted for was
real but cheaper than measured — worth recording as a case where the ceiling
was conservative in the useful direction.

**The fixture is the reusable part.** `grant_reviewee_visibility` in
`tests/integration/conftest.py` creates the two things a grant needs together —
an open release window *and* an `after_release` reviewee policy row — because
either alone is silently insufficient and a test that sets only one reads as a
bug in the gate. It is a **fixture, not an importable helper**: `tests/conftest.py`
shadows the module name, so `from conftest import …` inside an integration test
resolves to the parent file and fails. Found by doing it the other way first.

**The W16 marker is retired here, not at PR 6.** The plan assigned both stale
`will gate this` comments to the specs rung, but PR 2 *is* the work the W16
comment predicted, so leaving it would have shipped a comment that was false
about the line beneath it. The W17 observer marker stays for PR 5, which is the
rung that actions it.

**One trap re-hit, and it is the same one as 19E's.** A new test asserted
`"/results" not in body` to prove no reviewee link renders — and failed,
because `base.html` inlines the entire stylesheet and a CSS comment mentions
`/results`. The assertion is now id-qualified. This is the second time this
session that a whole-page substring assertion has been wrong for exactly this
reason; on this page, any bare path fragment is a false positive waiting to
happen.

**Tests: 2,881 passed / 16 skipped**, up 13. Nine unit tests pin the
predicate's own edges (`tests/unit/test_reviewee_current_grant.py`) and four
integration tests pin what a reviewee sees. Mutation-checked in four places —
dropping the dashboard gate turns 4 red; dropping the predicate's audience
filter, its session filter, or its archive short-circuit each turns exactly one
red, so no test is covering another's ground by accident.

**Doc impact honoured at this rung:** `spec/participant_model.md` §5 (the grant
precondition, the three properties, and the row appearing and disappearing as
windows move) and `spec/role_landing_and_visibility.md` §4 — whose reviewee
lifecycle table is **replaced rather than amended**, because the reviewee role
no longer follows the lifecycle at all. Vary one session's state and nothing
else: `ready` with the release window closed shows nothing, `draft` with it
open shows a row. Keeping a five-state table there would have been a
well-formatted lie. Observers keep
their lifecycle table, now stated as its own section.

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
- **A sys-admin got a bare 404 on a link the app just showed them —
  resolved the same day by an author decision; see below.**
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

**2026-09-07 — the sys-admin finding, resolved: option (b), the
exemption.** The author took the second option and gave the reason the
first one missed: *the whole point is that they should be able to see
what's going on in the workspace as a whole.* Unlinking the session name
(option (a), my recommendation) would have removed an affordance in
order to protect information the very same page already displays — every
session, by name, on `/operator/sys-admin/sessions`. The 404 was
protecting nothing from that reader.

So `require_session_operator` answers **403** to a sys-admin who is not
an owner of an existing session, with the message reworded to name the
adopt door rather than restating the old *"You do not have access"*.
Two guards, both asserted:

- **Behind an existence check.** Written without one, the exemption
  answers *"you are not an owner of this session"* for an id that never
  existed — turning a refusal into a confirmation, and a worse leak than
  the one this rung closed. Mutation-checked: dropping the check turns
  the guard test red.
- **`require_session_operator` only.** Nothing in the app routes a
  sys-admin to `/results` or `/collation`, so the three participant
  gates have no affordance to keep legible; they answer 404 to everyone,
  sys-admins included. Scoping this myself rather than reading "exempt
  sys-admins" as global — flagged here in case the author wants it
  wider.

Super-admins needed no separate branch: both sign-in paths in
`get_or_create_user` force `is_sys_admin` for them, so the capability
nesting super ⊇ admin already holds at the gate.

**The `## Definition of done` grep changed with it**, and the change is
struck rather than rewritten: it read "returns only `require_sys_admin`"
and now returns two lines. The replacement test pins each of the two to
its own function, so the looser property ("there are some 403s") cannot
pass in place of the real one.

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
7. **PR 7 — the chip strip** *(added 2026-09-07, during the close)*.
   Mirrors PRs 2 and 5 into `build_role_chips`
   (`app/web/routes_reviewer/_shared.py`): the `reviewee` chip is
   omitted without a currently-resolving grant, the `observer` chip
   greys on an archived session. Found by the close's `spec-writer`
   pass, not by the ladder — the plan's blast radius counted the
   dashboard's `role_links` and never the chip strip, which answers the
   same question on a different surface. **Must not touch** the
   dashboard, the gates, or any route.

Each rung leaves the app coherent. PR 1 narrows what every refusal
discloses without changing who passes. After PR 2 the reviewee row is
gated while the surface is still reachable by direct URL — a narrower
disclosure than today, not a wider one — and PR 4 closes that. PR 3 sits
between them because it depends on PR 2's predicate and nothing depends
on it; landing it there means the Guide and the dashboard agree about
who a no-grant reviewee is from the moment either of them changes.

## Definition of done

- All four session-scoped gates answer **404** on refusal, with a body
  indistinguishable from an unknown session id, asserted for each gate.
  ~~`grep -rn "HTTP_403_FORBIDDEN" app/web/deps.py` returns only
  `require_sys_admin`.~~ **Revised 2026-09-07 with decision 5's
  sys-admin exemption:** that grep returns **two** lines —
  `require_sys_admin`, and `require_session_operator`'s exemption — and
  a test pins both to their own function so a third cannot appear in a
  participant gate unnoticed.
- The sys-admin exemption answers **403** for an existing session the
  sys-admin does not own and **404** for an absent id, asserted against
  both.
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
  appears and disappears as windows move (PRs 1, 2); §5's observer
  reachability row gains the archived exception PR 5 made true without
  touching this file, and §6 gains the chip strip's copy of both rules
  (PRs 5, 7).
- `spec/role_landing_and_visibility.md` — §3's Guide-audiences table
  loses its "no role → all four" row for the bounce to `/about` (PR 3);
  §4's reviewee table is rewritten from "listed and linked in every
  state" to the gated behavior, and its reviewee/observer table gains the
  archived observer row's unlinked state (PRs 2, 5); §6 loses the
  observer-archive divergence once PR 5 closes it (PRs 1–5).
- `spec/visibility_policy.md` — the archive override's scope restated
  now that both non-operator audiences honor it (PR 5); §3 window
  definitions corrected — `after_release` gains the `expired`
  precondition and `while_ongoing` is restated as `status = "ready"`
  rather than the `[activated_at, deadline)` interval the code never
  implemented (PR 2a).
- `spec/audience_and_identity_model.md` — the `/guide` audience contract
  **reverses**: a viewer holding nothing sees nothing and is bounced to
  `/about`. The entry that goes says *"a viewer holding nothing sees
  everything"*, written at 19E rung 7 on 2026-09-06; the replacement
  names it as superseded rather than quietly occupying its place (PR 3).
  **Corrected again at close:** a `/guide` sentence still warned against
  advertising *"a page that will 403"*, and §3 still named
  `require_reviewee_in_session` as the `/results` gate (close).
- `spec/operator_ui_concept.md` — the `/guide` role-filtering paragraph,
  itself rewritten at 19E's close on 2026-09-07, and the chrome link
  row's new conditional (PR 3).
- `spec/permissions.md` — §5 Failure semantics: the "not a session
  member; not an active participant" row moves from **403** to **404**,
  and §3's per-route matrix follows (PR 1).
- `docs/security_posture.md` — the permission matrix's failure codes, and
  the session-enumeration vector recorded as closed rather than
  undiscovered (PR 1). **Corrected again at close:** the
  authorization-model prose and the §5.6 table still described all four
  gates as **403** while the same file's later section documented the
  404 conversion in detail — a file contradicting itself one screen
  apart (close).
- `spec/reviewer-surface.md` — **added at build, PR 6**, and the plan
  should have named it at planning time. `close_check.py` flagged it:
  the segment touched `_dashboard.py` and `_results.py` twice each, and
  `spec_registry.py` maps both to this file. Six stale claims, none of
  them cosmetic: the `/me` cross-role union (reviewee rows are
  grant-gated now), the reachability table's two "always `True`" rows
  (reviewee and observer both conditional), the "View responses"
  placeholder waiting for a gate that landed on the row instead, the
  `/results` gate (`require_reviewee_with_current_grant`, 404 not 403,
  and the retired pre-release scaffolding), the observer gate's 403, and
  the claim that W16 applies its window "not at route-level" — which PR
  4 reversed (PR 6). **Also PR 7:** the chip-strip section claimed
  reachability "mirrors the dashboard's `role_links.enabled` logic" —
  true of the reviewer chip, false of the other two (PR 7).
- `spec/architecture.md` — **added at build, PR 6**. Names the
  participant gates in two places: the reviewee-results entry and the
  gate summary. Both said `require_reviewee_in_session` and neither
  mentioned the 404 (PR 6).
- `spec/rrw_functional_spec.md` — **added at build, PR 6**. Same stale
  gate name on the reviewee-results paragraph (PR 6).
- `spec/role_navigator.md` — **added at close, PR 7**, and the fourth
  path the plan never named. Its reachability table still read
  *"reviewee — Always (today). W16 will gate on `responses_release_at` +
  `release_until_offset`"* — stale three ways over: W16 shipped in
  PRs #1737–#1752, PR 4 moved the question to the route, and
  `release_until_offset` was retired for the absolute
  `responses_release_until` column. The observer row's "Always" was
  accurate about the code and wrong about the contract, which is what
  PR 7 fixes (PR 7).
- `spec/lifecycle.md` — **added at close**, the fifth undeclared path.
  The release-from anchor row said *"Route-level 403 gates stay
  unimplemented"*; `require_reviewee_with_current_grant` is exactly one,
  answering 404 (close).
- `docs/status.md` — a row per rung as it lands, plus the close's
  currency pass over `Capabilities today`.
