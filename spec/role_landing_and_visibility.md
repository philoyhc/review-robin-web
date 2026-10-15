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

> **Your reviews** — There's nothing here for you right now. You're
> signed in as their@address. If you expected to see a review here,
> check that it was sent to this address, or contact the person running
> it. [About Review Robin]

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
| `draft` | listed, "Not open yet" | no | — |
| `validated` | listed, "Not open yet" | no | — |
| `ready` | listed, "Open" — past the deadline "Available" if they saved an answer they may read back, else "Closed" | **yes** | opens |
| `expired` | listed, "Available" or "Closed", as past the deadline | **yes** | **opens** |
| `archived` | listed, "Finished" | no | — |

The surface route admits `is_ready` **or `is_expired`** — a **closed**
session's review surface still opens. Draft, validated and archived
render the not-open page instead.

**One status rule for every role** (participant audit M6, author's
ruling 2026-10-15; `spec/reviewer-surface.md` "Session-status pill
vocabulary"). "Open" and "Closed" say whether the review accepts
responses; "Available" is closed to responses but viewable by one of
the row's roles now; "Finished" is archived.
The label decides no link: the **reviewer's** reachability still
follows `session_status_for_reviewer` (`!= "not opened"`), and the
observer's tests `is_archived` directly.

### Reviewee

The reviewee role does not follow the lifecycle; it follows the
**grant**.

| Currently-resolving grant? | `/me` row | Linked? | `/results` |
|---|---|---|---|
| no | **absent** | — | **404**, identical to a stranger's |
| yes | listed | **yes** | 200 |

A grant resolves when at least one instrument in the session has a
`reviewee` policy row whose after-release mode is live **inside an open
response-release window** (`visibility_policies.reviewee_has_current_grant`).
A reviewee's `while_ongoing` cell is off by construction, and the
database refuses to store any other value there (`ck_view_policy_cell`,
`spec/visibility_policy.md` §3.1). No grant resolves on an archived session — the archive
override closes every non-operator grant.

**The grant needs two things, and lifecycle is one of them.** The
grant lives entirely in the after-release window, and that window
requires `sessions.status = "expired"` as well as a reached anchor,
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
anchor survives the revert; the grant does not.

So a five-state lifecycle table would still mislead — `expired` alone
does not produce a row, and the grant is what decides — but lifecycle is
not irrelevant to it either.

**A reviewee with no current grant is indistinguishable from a
stranger** — the same empty `/me`, the same 404 — which is the point of
the segment rather than a side effect. If they also hold a reviewer or
observer role on that session, the row survives on *that* role and only
the Reviewee pill is missing.

**Learning it through another role is accepted** (author, 2026-10-15).
The rule above covers the reviewee role. Another role on the same session
can show someone that they are a reviewee, and two such routes are
deliberate exceptions. Each works only where that role is shown who the
reviewee is:

- **Self-review.** A reviewer assigned to review themselves, or a group
  they belong to (`Assignment.is_self_review`, `spec/assignments.md`
  § *Self-review policy*), knows they are a reviewee because the
  assignment says so. The reviewer surface opens in `ready` and
  `expired`. Draft, validated and archived sessions show only the
  pre-open page.
- **An observer in their own cohort.** An observer whose cohort rule
  matches their own reviewee rows (the rule matches on tags) can find
  themselves named in the per-instrument CSV under `Raw`. The
  `/collation` page names no one in any mode.

**What other people wrote about the person reaches them only inside one
of their own windows.** For a reviewee, that is the response-release
window (`/results`). For an observer, it is the observer's visibility
windows (`/collation`). Neither route opens anything before then:

- A reviewer's grant covers only responses they keyed in themselves
  (`spec/visibility_policy.md` §1.1). A self-reviewer reads back their
  own self-review and never what others wrote about them, in any state.
- `Raw`, the only mode that names reviewees, is available to observers
  only in the after-release window (`spec/visibility_policy.md` §3.1).
  `Anonymized` replaces names with tokens, and `Summarized` shows counts
  and aggregates. The observer's own rows can be part of the data in
  either mode, including the while-ongoing `Summarized` view, but that
  stays inside an observer window.

**Making a reviewee an observer is the operator allowing this**
(author, 2026-10-15). The operator who makes a reviewee an observer
accepts three consequences, and none of them is a defect:

- The observer's `Summarized` aggregates, while the session is still
  running, can include what others wrote about them.
- In the `Anonymized` CSV, an observer who is also a self-reviewer on an
  individual-scoped instrument can find their own reviewee token through
  the `SelfReview` column, and with it every other row about them. A
  group-scoped instrument offers no such route: a group's row blanks the
  reviewee instead of tokenizing it
  (`app/services/extracts/by_instrument_extract.py`).
- A cohort that matches only the observer's own rows shows them their own
  results.

Nothing hides small cohorts, and nothing drops an observer's own rows.

### Observer

| Session state | `/me` row | Linked? | `/collation` |
|---|---|---|---|
| `draft` | listed, "Not open yet" | **yes** | **200** |
| `validated` | listed, "Not open yet" | **yes** | **200** |
| `ready` | listed, "Open" — past the deadline "Available" while an observer grant resolves, else "Closed" | yes | 200 |
| `expired` | listed, "Available" or "Closed", as past the deadline | yes | 200 |
| `archived` | listed, "Finished" | **no — unlinked** | **404** |

**Observers are deliberately not grant-gated**: being appointed an observer is not a disclosure *about* the observer, so the
privacy argument that gates reviewees does not transfer. They may see
that they are an observer before their window opens — which is why the
link is live on `draft` and `validated` as well as `ready` and
`expired`.

**Archived is the one exception.** Archive closes every
non-operator grant, so `/collation` there is empty by construction and a
live link to it is a dead end. The row reads "Finished" and loses its
link, matching the reviewer row beside it. Once archived a session is
off limits (participant audit M4): the surface answers **404** there,
as do its CSV and the reviewer's `/summary` and `/summary.csv`.

**Before archive, access is not lifecycle-gated on this surface;
content is.** The route gates on an active roster row and on the
session not being archived. What renders is decided per instrument by
the visibility policy and the release window
(`spec/visibility_policy.md`).

**Archived sessions stay on `/me` for reviewers and observers**, reading
"Finished" until the session is deleted; they are deliberately not
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
`True` renders "You haven't been given anyone to observe in this review
yet", telling the observer nothing is assigned when a cohort is
configured.
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
