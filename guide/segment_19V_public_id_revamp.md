# Segment 19V — public IDs: URLs that don't count the workspace

**Opened:** 2026-10-18 · **Theme:** stop URLs and page source exposing
workspace-wide row counts · **Related:** `spec/architecture.md`
(domain entities), `spec/participant_model.md` (`/me` routes),
`spec/reviewer-surface.md` (the review form)

Opened as `guide/public_id_revamp.md` and renamed to a segment at the
author's word (2026-10-18). **Items close independently**, each with its
own `### Doc impact` and `### Status`, as in 19U. So there is no
segment-level `## Doc impact`, and `python3 tools/close_check.py 19V.1`
reads Item 1's.

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
  answers 404, as for any unknown session. Old integer URLs stop working,
  with no redirect (author, 2026-10-18).
- **Emails are unaffected.** Invitations and reminders link to
  `/me/invite/<token>` (`app/services/invitations.py`), never to a
  session ID.
- **Form posts that carry the integer stay as they are.** Examples are
  the lobby's bulk-select `value="{{ session.id }}"`
  (`spec/sessions_overview.md`) and the audit-log filters. They are page
  source on operator pages, not URLs. They may move later, but this item
  does not need it.
- **The CSVs are unaffected, including the round trip.** No exported
  file carries `sessions.id`:
  - the Settings CSV carries `session.code` and the settings, never the
    row ID (`app/services/session_config_io/_serialize.py`);
  - roster, relationship and response files key by email or identifier
    and by positional instrument names (`instrument_{n}`);
  - download filenames use the code (`extracts.filename`).

  So a file exported before this item imports unchanged after it.
  `public_id` is not exported either: a session made by Rehydrate or
  Duplicate is a new session and draws its own ID, and a Settings import
  onto an existing session leaves the ID alone. Exporting it would invite
  a collision on reload.
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

### Status

**Closed 2026-10-18** (#3126, #3127, #3128); the segment stays open for
Item 2 and follow-ups.

- **Ladder as planned, plus one fix PR.** Rung 3 landed whole, not split
  by surface. Beyond the measured sites it reached `app/web/return_to.py`
  (its session regexes read digits) and the sys-admin outbox / audit-log
  / adopt routes. #3128 acted on the read.
- **Decisions confirmed at build.** One context-sensitive model default
  (`_new_public_id`, the `_next_session_seq` pattern) covers every create
  path and fixture. Every resolver shares `sessions.get_by_public_id`,
  which checks the shape before it queries. The public ID is logged on an
  operator-gate denial, as the only trace of a probe; Semantics' "not
  logged" meant not handled as a token. Tests hand helpers the integer
  through `tests/integration/_public_id.py`; browser tests hold the public
  ID and resolve the key with `_builder.session_pk`.
- **Reads: one** (`diff-reviewer`, `18d9013f..a42b3173`). No `app/`
  blocker. It found five tests passing vacuously on integer URLs and a
  NUL byte reaching Postgres as a 500; both fixed in #3128.
- **Doc impact grew** by `spec/settings_inventory.md` and
  `spec/reviewer-surface.md` (the read). `spec-writer` flagged nothing
  that changed a decision. Specs outside the manifest keep their `{id}`
  placeholders, which `spec/architecture.md` now defines.

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
  404, pinned by a test.
- A test pins that a session made by Rehydrate gets its own `public_id`,
  and that a Settings export carries none.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19V.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- On the segment's last item: plan moved to `guide/archive/` + index row

### Open questions

1. ~~Should old integer URLs redirect?~~ No: they stop working (author,
   2026-10-18; a local database may be wiped if the migration needs it).
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
- `spec/settings_inventory.md` — the session-scoped sort cookies and Extract-data storage keys are named by the public ID (Item 1; added at the cumulative read).
- `spec/reviewer-surface.md` — URL examples use a public ID, not an integer (Item 1; added at the cumulative read).

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

Name each answer by its row's ordinal on the page:
`response[{ordinal}][{field_key}]`. The ordinal is the row's rank among
the page's assignments sorted by assignment ID. That order is
independent of display: a reviewer's column sort reorders the DOM and
writes a cookie (`app/web/templates/base.html`, the shared sort handler),
and the POST rebuilds the rows in the cookie's order
(`app/web/routes_reviewer/_surface/_context.py`), so a display position
would point at a different row after a sort (Codex on #3124). The server
rebuilds the page's assignment set, sorts it by ID and maps ordinal back
to ID. A forged ordinal can therefore only address a row on the
reviewer's own page.

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
  digest of the page's assignment-ID set in ID order (a keyed hash, so
  it reveals no count), checked on post. A mismatch re-renders the page
  with a "this page changed" notice and saves nothing.
- **A client-side sort is not a change.** The ordinals and the digest
  both come from ID order, so a sort between render and post leaves them
  valid, and the save lands on the rows the reviewer typed into.
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

### Status

- **Build (2026-10-18), one rung.** `responses._form_keys` owns the
  ordinals and the page digest; `parse_form_payload` takes the page's
  ordered IDs. Save and Submit read the page they were posted from
  (`?page=` for Submit). The digest is required only when a post
  carries answers, so Clear and an answerless Submit need none. A
  stale post reuses the refused-write page (participant audit P3) with
  a `page_changed` cause and 409, its typed values listed bare. Tests
  post through `tests/integration/_answer_form.py`.
- **Digest key (2026-10-18), from the reads.** The first build keyed the
  digest by `PARTICIPANT_TOKEN_SALT`, which has a public default, so a
  reviewer could brute-force the IDs back out (`diff-reviewer`); hashing
  the visible row data instead still exposed hidden identifiers (Codex
  on #3130). Shipped: the ID set keyed by a per-session secret,
  `sessions.form_key` (migration `c4e8b2f6a1d9`), never rendered or
  exported. The read also caught a non-ASCII digest answering 500, and
  specs still describing ID-keyed form bodies; fixed in #3130.

### PR ladder

1. **Build:** template, parser mapping, the new page digest and its
   refusal, tests and spec, in one rung.

### Open questions

1. ~~Build at all?~~ Yes: "build 19V" (author, 2026-10-18).

### Doc impact

- `spec/reviewer-surface.md` — response inputs key off the row's position on the page, mapped server-side (Item 2).
- `docs/database.md` — the `sessions.form_key` column that keys the page digest (Item 2; added at build).
- `spec/permissions.md` — a reviewer form body carries no assignment ID (Item 2; added at the read).
- `docs/security_posture.md` — §5.6's reviewer POST note: ordinals, the 409, the service filter (Item 2; added at the read).
- `spec/architecture.md` — `_form_keys.py` in the module map (Item 2; added at the read).

---

## Item 3 — The observer's CSV address stops carrying the instrument ID

Raised 2026-10-18, while building the browser check set (#3131).

### Opportunity

An observer's per-instrument download is
`/me/sessions/{public_id}/collation/instruments/{instrument_id}.csv`
(`app/web/routes_reviewer/_collation.py:102`, built in
`app/web/views/_observer_collation.py:181`). `instruments.id` is
workspace-wide, so a participant reads off roughly how many instruments
the whole workspace has made. Item 1 fixed this for the session in that
same address; its out-of-scope list ruled out other entities' IDs in
*operator* URLs only.

### Decision

Address the instrument by its `session_seq`:
`…/collation/instruments/{session_seq}.csv`. `session_seq` already exists
(19Q Item 6). It is per session, set once at creation, and never moved by
drag-and-drop. It is not yet unique: nothing constrains
`(session_id, session_seq)`, and `spec/instruments.md` records that two
rows in one flush would share a number. So as the address it gets a unique
index (one migration), and the route looks the instrument up by
`(session_id, session_seq)`, under the same 404s as today. An integer
`instruments.id` that happens to match some other instrument's
`session_seq` in this session reaches that one, which reveals nothing:
a session's own instruments are already listed on the page.

Rejected: a random `instruments.public_id` like Item 1's. It costs a
column and a value from every creation path, to hide a number that a
per-session sequence already hides once it is unique.

### Semantics

- **Uniqueness.** A unique index on `(session_id, session_seq)` makes a
  duplicate an insert error instead of a second row that shares an
  address (Codex on #3133). The migration first renumbers any duplicate
  above the session's highest number, keeping the lower ID's value.
  Every creation path already flushes at once, and the instrument
  writers lock the session row, so a collision means a defect, not a
  race to retry.
- **A recycled number.** A trailing delete hands the number back
  (`_next_session_seq`), so after deleting the newest instrument and
  adding one, an old bookmark reaches the new instrument. The 404s
  still apply, so an observer gets only what they could download anyway.
- **A non-integer or unknown seq** answers 404, as an unknown ID does
  now.

### Blast radius (measured)

Taken 2026-10-18 at `e406297e`.

- **Route and builder:** 2 sites
  (`git grep -n 'collation/instruments' -- app`): `_collation.py` and
  `_observer_collation.py`, plus the route's docstring.
- **Tests:** 2 files, 16 lines
  (`git grep -n 'instruments/' -- tests/integration/test_observer_collation_body.py tests/integration/test_reviewer_identity_level.py`).
- **Spec:** `spec/participant_model.md` (the collation row of the route
  table) and `spec/instruments.md` (the "nothing constrains duplicates"
  note).
- **Schema:** one migration, the unique index; `docs/database.md`.

### Status

**Closed 2026-10-18** (#3135), one rung as planned; the segment stays open.

- **Decisions confirmed at build.** The route takes the number as a
  string and answers 404 unless it is 1–9 digits, so `abc`, `-1`, an
  overflow or a NUL never reaches the query as a 422 or a 500. The
  migration renumbers duplicates in Python, lowest `id` first, so it
  reads the same on SQLite and Postgres.
- **Scope moved: the batched insert.** The constraint turned the
  latent duplicate into an `IntegrityError` for 50 tests whose fixtures
  add several instruments in one flush. `_next_session_seq` now keeps
  the numbers it hands out on the batch's execution context, so such a
  flush numbers its rows in turn. Every app creation path already
  flushed per row. One test had written `session_seq=1` into a session
  already holding 1, and now takes the default.
- **Reads: one** (`diff-reviewer`, `719097ce..ad848f25`). No blocker.
  It found the other-session test passing with no grant on the other
  instrument (now granted; the route and the cohort each scope by
  session, so it fails only with both gone), and leading zeros reaching
  an instrument (`0002.csv`; the number is now canonical, no leading
  zero). The plan's "unique index" shipped as a unique constraint. The
  DoD's "`id` appears nowhere in the page" is pinned as no
  `instruments/{id}.csv`: a bare integer can match anything on a page.
  `spec-writer` dropped two provenance tags and flagged nothing else.
- **The tests live in a new file**, `tests/integration/test_collation_csv_address.py`,
  not the DoD's `test_observer_collation_body.py`, because they pad the
  workspace so that `id` and number differ.

### PR ladder

1. **Build:** the unique index and its migration, route lookup, URL
   builder, tests and specs, in one rung.

### Definition of done

- The collation page links `…/instruments/{session_seq}.csv`. A test
  pins that the instrument's `id` appears nowhere in the page.
- `tests/integration/test_observer_collation_body.py` covers an unknown
  seq answering 404, and another session's instrument staying out of
  reach.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19V.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; on the segment's last item, plan moved to `guide/archive/` + index row

### Open questions

1. ~~Build at all?~~ Yes (author, 2026-10-18).
2. ~~The review page's sort keys?~~ Folded into 19V as Item 4 (author,
   2026-10-18).

### Out of scope

- **Operator URLs**, as in Item 1.

### Doc impact

- `spec/participant_model.md` — the collation CSV route takes the instrument's per-session number, not its ID (Item 3).
- `spec/instruments.md` — `session_seq` is unique per session, by index (Item 3; added at Codex's read of the plan).
- `docs/database.md` — the unique index on `instruments (session_id, session_seq)` (Item 3; added at Codex's read of the plan).

---

## Item 4 — The review page's sort keys stop carrying IDs

Raised 2026-10-18 as Item 3's open question 2, and folded in at the
author's word.

### Opportunity

After Item 3, the review page is the last participant page whose source
carries workspace-wide IDs (an audit of `/me` templates, views and
downloads, 2026-10-18). Its sortable tables name the remembered-sort
cookie `rrw-sort-rs-{public_id}-{instrument.id}`, and its headers carry
`display:{field.id}` and `response:{field.id}`
(`app/web/templates/reviewer/review_surface.html:333`, `:374`, `:396`).
A reviewer reads off how many instruments and fields the workspace has
made.

### Decision

Key each on what the page already shows:

- **Cookie:** `rrw-sort-rs-{public_id}-{instrument.session_seq}`. The
  number is unique per session since Item 3.
- **Display header:** `display:{source_type}.{source_field}`, e.g.
  `display:reviewee.tag_1`. The display-field service refuses a second
  field with the same source on an instrument.
- **Response header:** `response:{field_key}`. Unique per instrument
  (`uq_instrument_field_key`), and already in the answer boxes' names.

Rejected: a per-instrument ordinal for fields, as Item 2 did for
answers. An ordinal shifts when a field is deleted, so a remembered sort
would move to the next column. A source or key stays with its column
through reorders and deletes.

### Semantics

- **An old cookie** is forgotten once: its name changes, and its keys
  match nothing. This is the same as Item 1's address change.
- **A duplicate source.** The Settings import does not refuse two
  display fields with one source, so two headers can share a key. Both
  columns show the same values, so a sort by either is the same. The
  server maps the key to the first in display order.
- **A deleted field or column.** Its key matches no header and is
  dropped, as an unknown key is today. A recycled `session_seq` hands an
  old instrument's remembered sort to its successor, which keeps only
  the keys that still match.
- **The browser script** compares keys as strings (`getAttribute`, never
  a CSS selector), so a field key containing quotes or colons needs no
  escaping.

### Blast radius (measured)

Taken 2026-10-18 at `eb6c5748`.

- **App:** 3 template sites (`review_surface.html:333`, `:374`, `:396`),
  the decoder in `app/web/views/_sort.py` and its one caller
  (`app/web/routes_reviewer/_surface/_context.py:533`). Base's sort
  script is key-agnostic: it only matches the `response:` prefix
  (`app/web/templates/base.html:5425`).
- **Tests:** 6 files, 29 lines (`grep -rnE "rrw-sort-rs|[\"'](display|response):[^ ]" tests/ --include=*.py`).
- **Spec:** `spec/sort_by_reviewee.md` (cookie name and keys) and
  `spec/settings_inventory.md` (cookie inventory row).

### Status

**Closed 2026-10-19** (#3137), one rung as planned; the segment stays open.

- **Decisions confirmed at build.** The decoder maps `display:` keys
  through a source-to-ID table built in display order, so a duplicate
  source resolves to the first field. A key in the old `display:<id>`
  form names no column and is dropped.
- **Reads: one** (`diff-reviewer`, `7e02e9bf..ac226b28`). No blocker;
  three nits, all fixed: a stale cookie-shape comment in `base.html`, a
  stale browser-test docstring, and the server-side display-key test
  storing a key no header emits (now the tag header's own). Semantics'
  "matches no header" is, at build, "matches no display field": a hidden
  field's key still sorts, as the old `display:N` did, and
  `spec/sort_by_reviewee.md` says so. `spec-writer` fixed one stale
  cookie line in the same spec.
- **Doc impact grew** by `spec/ui_elements.md`, whose `.col-chip-row`
  row named the `response:N` form.
- **The browser checks** gained a row in
  `guide/things_to_check_in_browser.md`, and step 8 of the checklist run
  order now checks the keys.

### PR ladder

1. **Build:** cookie name, header keys, decoder, tests and specs, in one
   rung.

### Definition of done

- The review page's source carries no instrument or field ID in a sort
  key or cookie name; a test pins it with an instrument whose `id`
  differs from its `session_seq`.
- A sort stored under the new keys is applied by the server on reload,
  and `tests/browser/test_reviewer_sort_cookie.py` passes.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19V.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; on the segment's last item, plan moved to `guide/archive/` + index row

### Open questions

None.

### Out of scope

- **Operator pages**, as in Item 1. Their sort cookies already use the
  public ID, and their tables are the operator's own.

### Doc impact

- `spec/sort_by_reviewee.md` — the reviewer cookie is named by `session_seq`, and its keys by display source and response `field_key` (Item 4).
- `spec/settings_inventory.md` — the `rrw-sort-rs` cookie row names the instrument by `session_seq` (Item 4).
- `spec/ui_elements.md` — the `.col-chip-row` row's `response:N` key becomes `response:` (Item 4; added at build).
