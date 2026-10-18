# Public IDs: URLs that don't count the workspace

**Opened:** 2026-10-18 · **Theme:** stop URLs and page source exposing
workspace-wide row counts · **Related:** `spec/architecture.md`
(domain entities), `spec/participant_model.md` (`/me` routes),
`spec/reviewer-surface.md` (the review form)

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/archive/pair_context_tags_further_clarify.md`: each item
carries its own `### Doc impact` and `### Status`, checked by hand at
close (`tools/close_check.py` reads only `segment_*` files).

---

## Item 1 — A session's URL carries a random public ID

### Opportunity

`sessions.id` is an auto-increment primary key
(`app/db/models/review_session.py:28`), and it is the session's URL
handle: `/operator/sessions/{id}/…` and `/me/sessions/{id}/…`. Anyone who
can open one session can read off roughly how many sessions the workspace
has made, and watch it grow. Access is never at stake, because every
route checks permission (`require_session_operator`, the participant
gates) and a stranger gets 404. The leak is the count (author,
2026-10-18: "mainly so that the count isn't exposed").

### Decision

Add `sessions.public_id`: a random, unique, indexed string, set once when
a session is created and never changed. URLs carry it in place of the
integer. Everything below the route layer keeps the integer key, so
foreign keys, joins, services, audit `refs`, exports and the Settings CSV
are untouched.

- **Shape:** 10 characters from a lowercase alphabet without look-alikes
  (`23456789abcdefghjkmnpqrstuvwxyz`, 31 symbols), so about 49 bits
  (31^10 ≈ 8×10^14). It comes from `secrets.choice`, and a rare collision
  retries against the unique index.
- **Path parameter keeps its name.** `{session_id}` in the 172 route
  paths stays, and its value is now the public ID. The resolvers in
  `app/web/deps.py` look the session up by `public_id`, and handlers keep
  `review_session.id` for queries.
- **Assigned on every path that makes a session:** Create, Duplicate
  (`session_clone.py`), Rehydrate (`session_rehydrate.py`), and the
  migration's backfill for existing rows.

Rejected: making `sessions.id` itself a random string. That means 14
foreign-key columns retyped on Postgres and SQLite, every join on a wider
key, and about 140 typed signatures changed, all to buy URL opacity that
one column gives on its own (assessed 2026-10-18).

### Semantics

- **An integer in a session URL no longer resolves.** `/me/sessions/12/…`
  answers 404, as for any unknown session. That is subject to Open
  question 1.
- **Emails are unaffected.** Invitations and reminders link to
  `/me/invite/<token>` (`app/services/invitations.py`), never to a
  session ID.
- **Form posts that carry the integer stay as they are.** Examples are
  the lobby's bulk-select `value="{{ session.id }}"`
  (`spec/sessions_overview.md`) and the audit-log filters. They are page
  source on operator pages, not URLs. They may move later, but this item
  does not need it.
- **Browser storage keys** built from the session ID
  (`rrw-…-{{ session.id }}`, 7 sites) switch to the public ID. A
  remembered sort or column width resets once per session, which is
  acceptable pre-Azure.
- **The public ID is not a secret.** It does not grant access and is not
  a token, so it is not logged or treated as one. It only stops being a
  counter.

### Judgment calls — decided

- The path parameter stays `{session_id}`, so the 172 route paths and the
  170 redirects that echo it are unchanged.
- No Jinja-wide `session.url` helper is introduced. The sweep is
  mechanical (`.id` → `.public_id` where a URL is built), and a helper
  would be a second refactor in the same rungs.

### Blast radius (measured)

Taken 2026-10-18 at `c39186b4`.

- **Model and migration:** `app/db/models/review_session.py` gets one
  column, plus one Alembic migration (backfill, then unique index) that
  must round-trip on `ci-postgres`.
- **Session creators:** `sessions.create_session`,
  `session_clone.clone_session` and the Rehydrate apply in
  `session_rehydrate.py`.
- **Resolvers:** `app/web/deps.py`, 7 functions taking `session_id: int`
  (`grep -c "session_id: int" app/web/deps.py`), plus 38 route signatures
  (`git grep -n 'session_id: int' -- app/web | wc -l`).
- **Python URL builders from an entity**, which must change, about 114
  sites: `{review_session.id}` 102, `{s.id}` 6, `{session.id}` 5,
  `{clone.id}` 1. A further 57 use `{id}` / `{sid}` and need reading one
  by one. Command:
  `git grep -ohE '/sessions/\{[a-z_.]*id\}' -- 'app/*.py' | sort | uniq -c`.
- **Python URL builders from the path parameter**, unchanged: 170.
- **Template URL builders:** 97 sites in 25 templates (`{{ session.id }}`
  90, `{{ s.id }}` 6, `{{ outcome.session_id }}` 1). Command:
  `git grep -ohE '/sessions/\{\{ ?[a-z_.]+ ?\}\}' -- app/web/templates | sort | uniq -c`.
- **Template JS building session URLs:** 4.
- **Tests:** 3,076 lines in 260 files build `/sessions/{…id}` URLs
  (`git grep -nE '/sessions/\{[a-z_.]*id\}' -- tests | wc -l`). Most
  interpolate `session.id`, so they need `.public_id`, mechanically.
- **Specs:** URL prose uses `{session_id}` / `{id}` placeholders that stay
  true. The specs that state the URL identity are the ones in Doc impact.

### PR ladder

1. **This plan** (prose).
2. **Column and assignment.** Model column, migration with backfill, and
   all three creators set it. Nothing reads it yet, and URLs are
   unchanged. Must not touch routes.
3. **Resolve and build.** The `deps.py` resolvers look up by
   `public_id`; every URL builder, template, JS site and storage key
   moves to `public_id`; the tests sweep with it. This is one rung
   because a half-switched app links to URLs it cannot resolve. If the
   diff is too large to read, split it by surface: operator first, then
   participant. Each half then resolves both forms for its one rung, with
   a fallback removed in the next.
4. **Specs and close.**

### Definition of done

- `sessions.public_id` is non-null, unique and set on Create, Duplicate
  and Rehydrate, and the migration round-trips on `ci-postgres`.
- No URL the app emits carries `sessions.id`. A test renders the lobby,
  Session Home, `/me` and a review page, and asserts that no
  `/sessions/<digits>` link appears.
- `/operator/sessions/<integer>/…` and `/me/sessions/<integer>/…` answer
  404, pinned by a test (or redirect, if Open question 1 says so).
- `### Doc impact` is present and current, and `### Status` is compacted
  at close.

### Open questions

1. **Should old integer URLs redirect?** This affects bookmarks and the
   author's open tabs. Recommended: no. Pre-Azure sessions are
   disposable, and an integer route kept alive keeps the counter
   reachable, even if only for viewers already permitted. Author decides.
2. **Operator-side instrument IDs** in `?editing=<id>#instrument-<id>` on
   the Instruments page: see Out of scope. Author decides whether they
   join as a later item.

### Out of scope

- **Other entities' integer IDs in operator URLs and form targets:**
  instruments, invitations, data shapes, fields, reviewers, reviewees,
  relationships and observers. Operators are trusted staff. The
  instrument ID is the only one in the address bar
  (`?editing=`, `#instrument-`).
- **The integer primary key, foreign keys and joins.** They are unchanged
  by design.

### Doc impact

- `spec/architecture.md` — domain entities: a session's `public_id`, its shape, and that URLs carry it while every reference below the route layer uses `id` (Item 1).
- `spec/participant_model.md` — the `/me/sessions/{session_id}/…` routes take the public ID; an integer answers 404 (Item 1).
- `spec/operator_ui_concept.md` — operator page URLs carry the public ID (Item 1).
- `docs/database.md` — the `sessions.public_id` column and its unique index (Item 1).

---

## Item 2 — The review form stops naming answers by assignment ID

Lower priority (author, 2026-10-18: "less of an issue", since it is page
source, not a URL). It is planned so that it is ready if wanted, not
queued.

### Opportunity

Every answer box on the review surface is named
`response[{assignment.id}][{field_key}]`
(`app/web/templates/reviewer/review_surface.html:468`), and
`assignments.id` is workspace-wide. A reviewer who views the page source
can read off roughly how many assignments the whole workspace has made.

### Decision

Name each answer by its row's position on the page:
`response[{row_index}][{field_key}]`. The server maps positions back to
assignment IDs from the same page context it rendered, which already
holds the visible rows in order. Because the mapping is rebuilt on the
server, a forged index can only address a row the reviewer was shown.

Rejected: signing or encrypting the assignment IDs. That adds key
handling to a page form to protect a count, which a position does
without any key.

### Semantics

- **A page that changed between render and post** has a different set or
  order of rows, for example after a Generate in between. It must be
  refused, not mapped by position onto the wrong rows. Today the POST
  only drops assignment IDs from other pages
  (`app/web/routes_reviewer/_surface/_routes.py`, the save handler's
  docstring); there is no render stamp. So this item adds one: a hidden
  digest of the page's ordered assignment IDs (a keyed hash, so it
  reveals no count), checked on post. A mismatch re-renders the page
  with a "this page changed" notice and saves nothing.
- **Group pages** fan one row's answer out to its group copies, as today.
  Only the key the form uses changes.

### Blast radius (measured)

Taken 2026-10-18 at `c39186b4`.

- **Template and parser:** 2 sites
  (`git grep -n 'response\[' -- app/web/templates/reviewer app/web/routes_reviewer app/services`):
  `review_surface.html` and `app/services/responses/_core.py`.
- **Tests:** 8 files post `response[…]` forms
  (`git grep -ln 'response\[' -- tests`).
- **Spec:** `spec/reviewer-surface.md` (`response[{rep_id}][{field}]`).

### PR ladder

1. **Build:** template, parser mapping, the new page digest and its
   refusal, tests and spec, in one rung.

### Open questions

1. **Build at all?** It waits on the author's word.

### Doc impact

- `spec/reviewer-surface.md` — response inputs key off the row's position on the page, mapped server-side (Item 2).
