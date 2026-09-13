# Role landing and visibility

Answers one question from the reader's side: **given my role — or my
lack of one — can I sign in, where do I land, and what do I see?**

Every table below is stated per role and per lifecycle state, at the
granularity a reader can act on: a session in each of the five lifecycle
states, a full roster on each, and one signed-in persona per row.

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

| Signed-in as | Audiences resolved | Result |
|---|---|---|
| No role at all | **none** | **303 → `/about`**; no Guide link in the chrome |
| Reviewee with no current grant | **none** | as above — indistinguishable from no role |
| Operator | `operator` | every `operator`-audience card |
| Sys-admin | `operator` | every `operator`-audience card |
| Reviewer only | `reviewer` | For reviewers |
| Reviewee **with** a current grant | `reviewee` | For reviewees |
| Observer only | `observer` | For observers |
| Operator + reviewer | `operator`, `reviewer` | both sets — roles union |

**A viewer who resolves no audience gets no sections — not every
section.** The opposite fallback is tempting, since the Guide carries no
session data and an empty page seems to serve nobody, but it does not
survive the comparison it implies: a union of all four audiences shows a
stranger *more* of the Guide than any role-holder sees, while a reviewer
sees one section. `visible_audiences` returns the empty set and
`routes_guide` turns it into the bounce below, so the resolver stays
pure.

`/about` rather than a 404 because the chrome offers the Guide link to
everyone, and refusing a link the app itself rendered is a worse answer
than moving the reader somewhere useful; `/about` is the "signed in but
no access" landing. The chrome additionally
stops rendering the link for such a viewer, so the bounce is a safety
net rather than the normal path.

**The reviewee rows are why `participants.disclosable_roles` is
grant-aware, and has to stay so.** Without that, a reviewee granted
nothing resolves the `reviewee` audience and is handed a "For
reviewees" card — the same disclosure `/me` and `/results` refuse,
relocated one page over rather than removed.

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
| `archived` | listed, "not opened" **+ an `archived` companion pill** | no | — |

The surface route admits `is_ready` **or `is_expired`** — a **closed**
session's review surface still opens. Draft, validated and archived
render the not-open page instead.

**Why `archived` carries a second pill.** `not opened` is true of a draft
session and of an archived one, for opposite reasons: a draft is not open
*yet*, an archived session is not open *any more* and will not be again.
One label for both leaves the reader unable to tell whether waiting is
worth anything, so archived rows render a muted `archived` pill beside
the status. It is a **companion, not a fourth status value**: the
`session_status` string is unchanged, because the **reviewer's**
reachability is derived from it (`!= "not opened"`) and a new value
would re-link the reviewer surface on an archived session. The
observer's link is gated independently, on `is_archived` directly; the
two agree here but by different routes.

**The render condition is on the session, not the role.** The template
tests `session.status == "archived"` once per row, so the tables below
list the companion under both Reviewer and Observer for the reader's
convenience, not because two rules exist. Only reviewer and observer
rows can reach an archived session at all — a reviewee-only row cannot,
since `reviewee_has_current_grant` is false there — so a row-level
condition and a per-role one cannot be told apart from the outside.

### Reviewee

The reviewee role does not follow the lifecycle; it follows the
**grant**.

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

**The grant needs two things, and lifecycle is one of them.** A
reviewee's `while_ongoing` cell is off by construction, so
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

The last row is why the window tests lifecycle and not the anchor
alone. `revert_session_to_draft` accepts `expired` → `draft` and leaves
`responses_release_at` stamped, so an anchor-only window would go on
showing released responses on a session the operator has withdrawn. The
anchor survives the revert; the grant it used to carry does not.

So a five-state lifecycle table would still mislead — `expired` alone
does not produce a row, and the grant is what decides — but lifecycle is
not irrelevant to it either.

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
| `archived` | listed, "not opened" **+ an `archived` companion pill** | **no — unlinked** | 200, empty |

**Observers are deliberately not grant-gated**: being appointed an observer is not a disclosure *about* the observer, so the
privacy argument that gates reviewees does not transfer. They may see
that they are an observer before their window opens — which is why the
link is live on `draft` and `validated` as well as `ready` and
`expired`.

**Archived is the one exception.** Archive closes every
non-operator grant, so `/collation` there is empty by construction and a
live link to it is a dead end. The row keeps its "not opened" text and
loses its link, matching the reviewer row beside it. The surface itself
still answers **200** — observers are not route-gated the way reviewees
are — it simply has nothing to render.

**Access is not lifecycle-gated on this surface; content is.** The route
gates only on an active roster row, so it returns 200 in every state
including archived. What renders is decided per instrument by the
visibility policy and the release window
(`spec/visibility_policy.md`).

**Archived sessions stay on `/me` for reviewers and observers**, reading
"not opened" until the session is deleted; they are deliberately not
filtered out. Only the *reviewee* role leaves an archived
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
`participants.disclosable_roles` applies the same predicate so the
Guide does not offer them a page they would be refused.

---

## 6. Known divergences and standing guards

Recorded rather than fixed here, because each is a behaviour decision
rather than a typo.

**The observer archive rule is emergent, and one line makes it local.**
No grant resolves for an observer on an archived session — but not
because `app/web/views/_observer_collation.py` works it out. The
after-release window requires `sessions.status = "expired"` and an
archived session is not expired, so both window predicates return
`False` and `resolve_mode` grants nothing. That is a property of
`session_lifecycle`, not of this view: relax either predicate and an
archived session whose release anchor is in the past resolves a live
grant again — `"raw"`, on a policy authored for the observer audience.

So the view states the rule locally: an `is_archived` short-circuit
returning `ObserverCollationContext(sections=[], cohort_empty=False)`,
as **defense in depth**. `cohort_empty` must be `False` there —
`True` renders "No cohort is configured for you yet", blaming the
operator for something that is configured.
`tests/unit/test_observer_archive_short_circuit.py` pins the
short-circuit by simulating that relaxation, which is the only
condition under which it is observable at all. **It is not redundant
with the window predicates, and must not be removed as though it were.**

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
