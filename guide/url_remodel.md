# URL remodel — `/reviewer/` → `/me/` (aggressive plan)

> **Stub created 2026-05-28.** Captures the aggressive
> hard-rename plan for the participant-side URL prefix,
> assuming the app is in beta with no real users to worry
> about. Extracted from `guide/participant_model_upgrade.md`
> §5.1, then sharpened against an actual blast-radius
> measurement.

## Why this exists separately from the participant-model arc

The participant-model upgrade (`guide/participant_model_upgrade.md`)
is segments 21+ work — substantial, adds new audiences
(reviewees, observers), new data structures, magic-link auth.
The URL-prefix rename is **independent prep work** that can
land any time. Decoupling it lets the rename ship now while the
participant features remain future work.

`guide/participant_model_upgrade.md` §5 / §5.1 now points back
to this doc and keeps a short summary; the substantive
URL-shape decisions + execution plan live here.

## Goal

Rename the reviewer-surface URL prefix from `/reviewer/` to
`/me/`, with no compatibility shim, in a single small PR.
Sets up the future meta-lobby (where one identity sees its
reviewer + reviewee + observer roles surfaced from one URL)
without requiring any of the participant features to ship
first.

## Recommended URL shape (final state)

```
/me/                       — participant meta-lobby
/me/sessions/{id}/{page}   — per-session participant surface
                              (today: reviewer-mode only;
                               later: reviewer + reviewee + observer
                               tabs / sections gated by resolved role)
/operator/                 — administrative surfaces (unchanged)
/operator/sys-admin/       — Sys Admin nests under operator (status quo)
/auth/me                   — the current /me JSON debug endpoint
                              moves here (one-line migration)
```

**Drop `/reviewer/`. Do not introduce `/reviewee/` or
`/observer/`.** Move everything participant-facing under
`/me/`.

### Why `/me/` rather than `/user/`

Conversational ("you are at your page") and matches how
identity surfaces self-refer in chrome today ("Signed in as
…", "My Reviews"). Also clean because `/me` is already
half-claimed by the JSON debug endpoint in
`app/web/routes_auth.py` — the only cost is moving that to
`/auth/me`.

### Why drop `/reviewee/`

A `/reviewee/` URL would force the system to model someone as
"primarily a reviewee", contradicting the overlap premise
(one identity has multiple, overlapping roles). A meta-lobby
with a "Your results" section handles the reviewee-only case
without giving it its own URL prefix — one bookmark per user
no matter what roles they accumulate, and a reviewer who later
gets reviewee results doesn't have to switch URLs.

### Why drop `/observer/`

Observers are **participants** who happen to have view-access
to aggregated results, not **administrators** who happen to
have restricted access. Folding them under `/operator/` would
force every operator-route guard to add an "...but observers
can read this" branch and would muddy the "/operator/ = admin"
semantic that is currently clean. The lobby section for
observers lives under `/me/` alongside reviewers / reviewees.

### Per-session URL design (single page, role-tabbed)

Inside a session, a user who has multiple roles in it (e.g.
they're both reviewer AND reviewee on the same session — the
360° self-assessment case) lands on one URL with sections /
tabs for each role they have. Picks up the existing
multi-page reviewer-surface contract naturally — pages are the
operator-defined runs of instruments; the lobby gates which
instruments + which "lens" (form / results / observation) the
user sees. The reviewer surface already passes `preview_mode`
through `_surface_context` to repurpose the same template for
the operator preview — adding
`view_mode={form, results, observation}` is the natural
extension: one template, one context builder, three rendering
branches gated by the resolved role(s). Beats mode-prefixed
routes (`/me/sessions/{id}/respond/{page}` etc.) because
there's less shape to maintain and the per-session role
resolution happens once.

## Why hard rename, not redirect shim

The participant_model_upgrade.md §5.1 sketch proposed a
three-step migration with 301 redirects to keep old URLs
working forever. Inspecting the actual world: **none of the
"forever" cases exist in beta.**

| Concern | Status |
|---|---|
| Invitation links in the wild | None — email-send is still inert (Segment 14B not shipped); every `email_outbox` row at `status="queued"` has never gone out and will regenerate when 14B activates. |
| Browser bookmarks | Zero real users; dev-slot tabs refresh-fixable. |
| External integrations | None known. |

A redirect shim would be 50-100 lines of code defending
against problems that don't exist. Skip it.

## Blast radius (measured)

Filtered to actual `/reviewer/` surface URLs (excluding
`/reviewers` operator-roster noise):

| Area | Files | Occurrences |
|---|---:|---:|
| Production code (`app/`) | 9 | 31 |
| Templates (`app/web/templates/`) | 9 | 16 |
| Tests | 33 | 290 |
| Live spec / docs | ~10 | low |
| **Total** | ~60 | ~340 |

### The substantive changes

Four router prefix declarations carry the actual rename:

- `app/web/routes_reviewer/_summary.py:39` —
  `APIRouter(prefix="/reviewer")` → `prefix="/me"`
- `app/web/routes_reviewer/_dashboard.py:34`
- `app/web/routes_reviewer/_invite.py:23`
- `app/web/routes_reviewer/_surface.py:65`

The other 300+ matches are mechanical search-replace: template
``href``s, form actions, test ``client.get("/reviewer/...")``
strings, internal redirect URLs in `_dashboard.py` / `_surface.py`,
`return_to.py` allowlist entries, `breadcrumbs.py` builders.

### One regex worth flagging

`app/services/invitations.py:460` defines
``_INVITE_URL_PATTERN = re.compile(r"https?://\S+/reviewer/invite/[A-Za-z0-9_\-]+")``.
This scrubs invitation URLs out of strings (email-preview /
audit redaction). Update to match `/me/invite/`.

### Optional polish

The `app/web/routes_reviewer/` folder name is no longer
literally correct after the rename (it serves `/me/` now). Two
options:

- **Leave it alone.** Internal name, no callers care, low value.
- **Rename to `app/web/routes_participant/`.** More accurate;
  small extra mechanical churn (`from app.web.routes_reviewer.…`
  imports change). Adds ~20 mechanical edits.

I'd leave it alone for the rename PR and rename the folder
later if the participant features land and it starts to read
wrong.

## Execution plan

**One PR, ~1-2 hours of focused mechanical work.**

1. Move ``/me`` JSON + ``/me/debug`` HTML in
   ``app/web/routes_auth.py`` to ``/auth/me`` + ``/auth/me/debug``.
2. Flip the four ``routes_reviewer/`` router prefixes from
   ``/reviewer`` to ``/me``.
3. Bulk find / replace ``/reviewer/`` → ``/me/`` across:
   - ``app/web/templates/`` (link / form / form-action URLs)
   - ``app/web/`` Python (URL builders, redirect targets,
     ``return_to.py`` allowlist, ``breadcrumbs.py``, the
     ``_preview_surface.py`` comment mirror, ``views/_instruments.py``)
   - ``tests/`` (~290 ``client.get / .post`` strings)
4. Update the invite-URL regex in
   ``app/services/invitations.py:460``.
5. Update live spec / docs:
   - ``spec/reviewer-surface.md`` URL-pattern section
   - ``docs/status.md`` mentions of the surface URL (if any)
   - ``guide/codebase_assessment_28may.md`` if it references the URL
   - ``guide/participant_model_upgrade.md`` §5 / §5.1 — trim
     the migration sketch to "shipped; see
     guide/archive/url_remodel.md" once this doc is archived.
   - This file → trim to a short "what shipped" status note
     pointing at the PR.
6. Run full suite (``pytest -n auto``). Mechanical changes
   should be all-or-nothing — any test that fails the regex
   replace is a sign of an edge case to inspect.

The archived ``guide/archive/`` and ``spec/archive/`` docs
keep their historical ``/reviewer/`` references — they're
snapshots, not living documentation.

## Risk acceptances

- **Browser-tab 404 storm.** Dev-slot tabs already open on
  ``/reviewer/...`` URLs 404 until refreshed. No real users
  affected.
- **Email-outbox rows referencing ``/reviewer/invite/...``.**
  Outbox rows at ``status="queued"`` from pre-rename code
  paths still embed the old URL in their HTML body. Email-send
  is inert (Segment 14B not shipped); the rows will be
  regenerated when 14B activates. If a deployment somehow has
  rows that have actually sent — they haven't, the transport
  is wired to a dev outbox — those would 404.
- **External integrations.** None known.
- **Future regression risk.** A late-breaking caller could
  fail in a test the rename PR didn't catch. The fix is
  trivial (one-line URL update); the full-suite run on the
  PR catches anything actively tested.

## Done when

- All four ``routes_reviewer/`` router prefixes are ``/me``.
- ``rg "/reviewer(?:/|\")" app tests`` returns zero matches
  (the operator-side ``/reviewers`` roster URL stays
  untouched).
- The ``/me`` JSON debug endpoint lives at ``/auth/me``.
- Full suite passes unchanged in shape (URL strings updated;
  no behaviour edits).
- ``guide/url_remodel.md`` → ``guide/archive/`` per the
  segment-closeout convention.
- ``guide/participant_model_upgrade.md`` §5 / §5.1 trimmed +
  pointed at the archived doc.

## Sequencing

- **Independent.** Doesn't block or depend on anything in the
  numbered queue. Can land any time before the participant
  arc opens.
- **Best landed before 14B Part A.** 14B will start sending
  emails for real; landing the rename first means the
  invitation URLs in those emails ship with the future-correct
  URL on day 1, avoiding a generation of ``/reviewer/...``
  URLs in real inboxes.
- **One PR. ~1-2 hours of focused work.** No new features, no
  schema changes, no behaviour change beyond the URL path.

## Related context

- ``guide/participant_model_upgrade.md`` §5 — the participant
  arc this URL prep sets up.
- ``guide/codebase_assessment_28may.md`` — the watch list this
  doesn't appear on (URL renames don't show up as code-health
  flags; this is a forward-looking prep).
