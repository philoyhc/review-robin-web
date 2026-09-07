# Role landing and visibility

**Current as of 2026-09-07 (Segment 19F PR 2).** Answers one question from
the reader's side: **given my role — or my lack of one — can I sign in,
where do I land, and what do I see?**

Every table below was **recorded from a running app**, not derived from
reading the routes: a fresh database seeded with one session in each of
the five lifecycle states, a full roster on each, and one signed-in
persona per row driving the real Easy Auth header path. Where behaviour
surprised the author it was re-tested before being written down; two
first-pass results turned out to be harness faults and are not in these
tables.

**What this file is not.** The authorization *contract* — which gate
guards which route, and with what status code — is
`spec/permissions.md` §3, which is organised route → gate. This file is
the transpose: role → experience. The audience taxonomy and the
reasoning behind the role model are
`spec/audience_and_identity_model.md`; the running-system security
review is `docs/security_posture.md`.

---

## 1. Who can sign in

**Anyone the identity provider authenticates.** There is no allowlist
check on the sign-in path.

`get_or_create_user` (`app/web/deps.py`) creates a `users` row for any
principal carrying an email claim. The only rejection is a **missing
email claim**, which is a 401. The operator / sys-admin allowlists
(`OPERATOR_EMAILS`, `SYS_ADMIN_EMAILS`, `SUPER_ADMIN_EMAILS`) seed the
`is_operator` / `is_sys_admin` **columns** on that first sign-in; they
do not gate whether the row is created.

So in a deployment fronted by institutional MS365, **every account in
the tenant can sign in.** Someone with no role lands on `/me` and reads:

> **Your reviews** — You have no pending reviews (their@address).

This is the current posture, not an oversight in the gates: the gates
work, and they run *after* sign-in. Restricting sign-in itself would be
a **new** gate that does not exist today. See §6.

---

## 2. Where you land

`GET /` is a **302** whose target follows the role, and deliberately
never a 301 — the target changes when a role changes.

| Signed-in as | `GET /` | `GET /me` | `GET /operator/sessions` |
|---|---|---|---|
| No role at all | 302 → `/me` | 200, empty state | 303 → `/me` |
| Operator | 302 → `/operator/sessions` | 200 | 200 |
| Sys-admin | 302 → `/operator/sessions` | 200 | 200 |
| Reviewer only | 302 → `/me` | 200, lists their sessions | 303 → `/me` |
| Reviewee only | 302 → `/me` | 200, lists their sessions | 303 → `/me` |
| Observer only | 302 → `/me` | 200, lists their sessions | 303 → `/me` |

The 303 on `/operator/sessions` is `OperatorAllowlistDenied`, handled in
`app/main.py` — a bounce to the user's own home, not a 403 page.

**Sys-admin implies operator** (F4), so a sys-admin who owns no session
still lands on the lobby.

---

## 3. What you see on `/guide`

`/guide` is one page addressed to every audience, filtered per card by
`app/web/views/_guide.py`. Resolved audiences, recorded:

| Signed-in as | Audiences resolved | Cards shown |
|---|---|---|
| No role at all | **all four** | all eleven |
| Operator | `operator` | the eight operator cards |
| Sys-admin | `operator` | the eight operator cards |
| Reviewer only | `reviewer` | For reviewers |
| Reviewee only | `reviewee` | For reviewees |
| Observer only | `observer` | For observers |
| Operator + reviewer | `operator`, `reviewer` | both sets — roles union |

The no-role row is a deliberate fallback, not an accident: an empty
Guide serves nobody, the page carries no session data, and a viewer the
app cannot classify is usually about to be rostered. Reasoning in
`spec/audience_and_identity_model.md` → "`/guide` — one surface,
audience-filtered content".

---

## 4. What a participant sees, by session lifecycle state

The row that appears on `/me`, and whether the role's own surface opens.
Recorded per state with an active roster row in each.

### Reviewer

| Session state | `/me` row | Linked? | Surface |
|---|---|---|---|
| `draft` | listed, "not opened" | no | — |
| `validated` | listed, "not opened" | no | — |
| `ready` | listed, "open" | **yes** | opens |
| `expired` | listed, "closed" | **yes** | **opens** |
| `archived` | listed, "not opened" | no | — |

The surface route admits `is_ready` **or `is_expired`** — a **closed**
session's review surface still opens. Draft, validated and archived
render the not-open page instead.

### Reviewee

**Rewritten for Segment 19F PR 2 (2026-09-07).** The reviewee role no
longer follows the lifecycle at all; it follows the **grant**.

| Currently-resolving grant? | `/me` row | Linked? | `/results` |
|---|---|---|---|
| no | **absent** | — | **404**, identical to a stranger's |
| yes | listed | **yes** | 200 |

A grant resolves when at least one instrument in the session has a
`reviewee` policy row whose mode is live **under the windows open right
now** (`visibility_policies.reviewee_has_current_grant`). Because a
reviewee's `while_ongoing` cell is always off by construction, in
practice this means *inside an open response-release window*, and never
on an archived session — the archive override closes every non-operator
grant.

**The grant needs two things, and lifecycle is one of them** (19F
PR 2a). A reviewee's `while_ongoing` cell is off by construction, so
their grant lives entirely in the after-release window — and that window
now requires `sessions.status = "expired"` as well as a reached anchor,
because responses are released *because the session is over*
(`spec/visibility_policy.md` §3.2). Take one session and vary it:

| One session | Reviewee row |
|---|---|
| `ready`, anchor reached | **none** — the review is still running |
| `expired`, no policy row or window closed | **none** |
| `expired`, anchor reached, policy row set | **shown** |
| reverted to `draft` after all of the above | **none** |

The last row is the case that prompted PR 2a:
`revert_session_to_draft` accepts `expired` → `draft` and leaves the
anchor stamped, so a session the operator had withdrawn used to go on
showing released responses. The anchor survives the revert but goes
inert.

So a five-state lifecycle table would still mislead — `expired` alone
does not produce a row, and the grant is what decides — but lifecycle is
no longer irrelevant to it either.

**A reviewee with no current grant is indistinguishable from a
stranger** — the same empty `/me`, the same 404 — which is the point of
the segment rather than a side effect. If they also hold a reviewer or
observer role on that session, the row survives on *that* role and only
the Reviewee pill is missing.

### Observer

| Session state | `/me` row | Linked? | `/collation` |
|---|---|---|---|
| `draft` | listed, "not opened" | **yes** | **200** |
| `validated` | listed, "not opened" | **yes** | **200** |
| `ready` | listed, "open" | yes | 200 |
| `expired` | listed, "closed" | yes | 200 |
| `archived` | listed, "not opened" | **no — unlinked** | 200, empty |

**Observers are deliberately not grant-gated** (19F decision 4): being
appointed an observer is not a disclosure *about* the observer, so the
privacy argument that gates reviewees does not transfer. They may see
that they are an observer before their window opens — which is why the
link is live on `draft` and `validated` as well as `ready` and
`expired`.

**Archived is the one exception** (decision 7). Archive closes every
non-operator grant, so `/collation` there is empty by construction and a
live link to it is a dead end. The row keeps its "not opened" text and
loses its link, matching the reviewer row beside it. The surface itself
still answers **200** — observers are not route-gated the way reviewees
became at PR 4 — it simply has nothing to render.

**Access is not lifecycle-gated on this surface; content is.** The route
gates only on an active roster row, so it returns 200 in every state
including archived. What renders is decided per instrument by the
visibility policy and the release window
(`spec/visibility_policy.md`).

**Archived sessions stay on `/me` for reviewers and observers**, reading
"not opened" until the session is deleted — the author declined to
filter them (2026-09-07). Only the *reviewee* role leaves an archived
session, and it leaves via the archive override closing its grant rather
than by a filter.

---

## 5. The word "active" means two different things

This is the single likeliest source of a sentence that reads true and
is not, so it is worth stating plainly:

- **`Reviewer.status == "active"`** (and the reviewee / observer
  equivalents) is the **roster row's** status — *is this person still on
  the list*, as opposed to `"inactive"`, which excludes them while
  keeping their history. **This is what every access gate checks.**
- **An "active session"** informally means a live one, but the lifecycle
  column has five values (`draft`, `validated`, `ready`, `expired`,
  `archived`) and no gate checks for "unarchived". Where lifecycle is
  checked at all it is checked as a **specific state set** — the review
  surface's `is_ready or is_expired` — and never as "not archived".

A reviewee identified by a **non-email identifier** holds no role for
any of this: `require_reviewee_in_session` applies
`participants.is_email_identified`, so they cannot reach `/results`, and
`participants.roles_held_anywhere` applies the same predicate so the
Guide does not offer them a page they would be refused.

---

## 6. Known divergences

Recorded rather than fixed here, because each is a behaviour decision
rather than a typo.

**~~The archive visibility override does not reach observers.~~
Closed 2026-09-07** — and the history is worth keeping, because it was
not closed by the change written to close it.

*As recorded:* `app/web/views/_observer_collation.py` had no archive
check, computing `after_release_open` from
`lifecycle.is_response_release_window_open`, which was then purely
anchor-based and returned `True` on an archived session whose release
anchor was in the past. `resolve_mode` returned a **live grant** —
verified returning `"raw"`. End-to-end exposure was never demonstrated
(it also needs the observer's cohort to resolve to assignments carrying
responses), so this was a live grant to close rather than a proven leak.

*What actually closed it:* **19F PR 2a**, which required
`sessions.status = "expired"` for the after-release window. An archived
session is not expired, so both window predicates now return `False`
here and no grant resolves — verified against a running app before this
entry was rewritten. The fix was a side effect of a different decision.

*What 19F PR 5 then added:* the `is_archived` short-circuit anyway, as
**defence in depth**. Without it the archive rule is *emergent* — it
holds only while two predicates in `session_lifecycle` keep refusing
archived sessions, which is a property of those functions rather than of
this view. `tests/unit/test_observer_archive_short_circuit.py` pins it
by simulating a future relaxation of one of those predicates, which is
the only condition under which the line is observable at all.

**Sign-in is open to the whole tenant** (§1). If the intended posture is
that only allowlisted operators and rostered participants may sign in,
that is a new gate. Two things it would have to settle: whether an
unrecognised principal gets a `users` row at all (audit trail against a
clean table), and how the first super-admin bootstraps — the
`SUPER_ADMIN_EMAILS` seed happens *inside* `get_or_create_user`, so a
gate placed before it locks out the person meant to set the system up.

---

## 7. Cross-references

- `spec/permissions.md` §3 — the same territory as route → gate, with
  status codes. Read that when changing a gate; read this when
  answering "what will this person see".
- `spec/audience_and_identity_model.md` — the audience taxonomy, the
  three-tier role model, and the `/guide` audience contract.
- `spec/participant_model.md` — the `/me` cross-role union and the two
  participant surfaces' contracts.
- `spec/visibility_policy.md` — what renders once a participant is
  through the door.
- `spec/lifecycle.md` — the five session states and their transitions.
- `docs/security_posture.md` — the running-system audit.
