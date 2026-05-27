# Reviewer-side visibility audit

What a reviewer can see on each reviewer-facing route, at every
realistic combination of session lifecycle / instrument
accepting-state / deadline / submission state. Built by reading
the routes + services in `app/web/routes_reviewer/` and
`app/services/session_lifecycle.py` — **the codebase, not the
spec**.

Use this when reasoning about a "why can the reviewer (not) see
X?" report.

---

## TL;DR

- **The master gate is `lifecycle.is_ready(session)`** at
  `app/web/routes_reviewer/_surface.py:823`. Anything that isn't
  `ready` (so: `draft`, `validated`, the un-wired `expired` /
  `archived`) shows the `pre_open.html` placeholder and **no
  form**.
- **Once `ready`, the form always renders**. Whether inputs are
  editable depends on `lifecycle.session_accepts_responses(...)`
  (a function of `is_ready` + `Instrument.accepting_responses` +
  the session deadline). Whether inputs are *prefilled with the
  reviewer's saved values* when that returns False depends on
  `Instrument.responses_visible_when_closed`.
- **Deadline passage is request-driven**, not scheduled:
  `lifecycle.observe_deadline(...)` runs on every reviewer-side
  GET / POST and lazily flips `accepting_responses=False` once
  `now ≥ deadline`. No scheduled job — the close is materialised
  the first time anyone hits the route after the moment passes.
- **`/summary` requires every assignment submitted.** Partial
  submitters get 303'd back to `/reviewer`.
- **Reviewers never see `include=False` rows.** The assignment
  query filters them out — no "skipped" rendering, the rows
  simply don't exist for that reviewer.
- **`archived` is the post-Segment-18A reach state** (set by
  `lifecycle.archive_session` from the Sessions lobby's archive
  action). The reviewer dashboard filters archived sessions out
  entirely; if a reviewer somehow lands on the surface URL the
  master gate falls through to `pre_open.html`.
- **`expired` is the post-2026-05-26 close-session state.**
  `lifecycle.expire_session` (the Workflow card's Close session
  button) flips `ready → expired` and closes every instrument
  (`accepting_responses=False`). The surface route accepts both
  `ready` AND `expired` as render-the-form states; the closed
  instruments + the per-instrument
  `responses_visible_when_closed` toggle then govern what the
  disabled inputs show. From `expired` the operator can click
  Revert to draft (shared `/sessions/{id}/revert` route — service
  accepts both `ready` and `expired` as starting states); the
  flip back to `draft` preserves every saved response.

---

## Canonical predicates (gates in dependency order)

| Predicate | File:line | What it returns True for |
|---|---|---|
| `lifecycle.is_ready(session)` | `app/services/session_lifecycle.py:60-61` | Session status is literally `"ready"` (activated). |
| `lifecycle.is_expired(session)` | `app/services/session_lifecycle.py:72-73` | Session status is `"expired"` (post-Close-session). Set by `expire_session()` and cleared by `revert_session_to_draft()`. |
| `lifecycle.is_archived(session)` | `app/services/session_lifecycle.py:76-77` | Session status is `"archived"` (post-archive-from-draft). Set by `archive_session()`; reversible via `unarchive_session()`. |
| `lifecycle.session_accepts_responses(session, instrument)` | `app/services/session_lifecycle.py:582-596` | `is_ready(session)` **AND** `instrument.accepting_responses` **AND** (no deadline OR `now < deadline`). |
| `lifecycle.observe_deadline(db, session, …)` | `app/services/session_lifecycle.py:640-696` | Called at request time on the reviewer surface + summary routes; flips every `accepting_responses=True` instrument to `False` once `now ≥ deadline`. Stamps `Instrument.deadline_closed_at`; audits with `reason="deadline"`. **Idempotent.** |
| `Instrument.responses_visible_when_closed` | `app/db/models/instrument.py` | Per-instrument display flag. When `accepting=False`, decides whether the reviewer's *previously-saved values* are still prefilled in the disabled inputs. |
| `responses_service.reviewer_session_state(...).pill_state == "submitted"` | `app/web/routes_reviewer/_summary.py:41-53` | Every one of the reviewer's assignments in the session is submitted. |
| `Assignment.include.is_(True)` filter | `app/web/routes_reviewer/_surface.py:76` (and equivalents on `_summary.py`, `_dashboard.py`) | Excludes operator-deactivated rows entirely from the reviewer's view. |

---

## Reviewer routes — what each one does

| URL | Handler | State check | What it renders |
|---|---|---|---|
| `GET /reviewer` | `_dashboard.py:133` | None (lists sessions where the reviewer's row is `status="active"`). Computes a pill + a "session status" badge for each row. | Dashboard listing. Per-session pill = `not started` / `in progress` / `submitted`; per-session status = `not opened` (session not `ready`) / `open` (`ready` + ≥1 accepting instrument before deadline) / `closed` (`ready` but deadline passed or all instruments `accepting=False`). Row link: `→ /summary` if `submitted`, else `→ /1`. |
| `GET /reviewer/sessions/{id}` | `_surface.py:782` | None — bare-URL convenience redirect. | 303 → `/reviewer/sessions/{id}/1`. |
| `GET /reviewer/sessions/{id}/{position}` | `_surface.py:795` | `lifecycle.is_ready(session) OR lifecycle.is_expired(session)` (line 823). | If neither → `reviewer/pre_open.html` ("opens later" banner + deadline text if set + back link to dashboard). Else → `reviewer/review_surface.html`: editable form when `ready` + instrument accepting + before deadline, otherwise disabled form with per-cell behaviour governed by `accepting` + `responses_visible_when_closed`. `expired` always renders the disabled-form variant since every instrument is `accepting=False` after close. |
| `POST /reviewer/sessions/{id}/{position}/save` | `_surface.py:870` | `_require_session_accepting(...)` (line 303) — needs `session_accepts_responses(session, instrument)`. | 200 on success; 403 otherwise. |
| `POST /reviewer/sessions/{id}/submit` | `_surface.py:962` | `_require_session_accepting(...)` per assignment. | 303 to summary on success; 403 otherwise. |
| `POST /reviewer/sessions/{id}/clear` | `_surface.py:1032` | Same as `/submit`. | 303 to surface on success; 403 otherwise. |
| `GET /reviewer/sessions/{id}/summary` | `_summary.py:56` | `pill_state == "submitted"` (every assignment submitted). | If not fully submitted → 303 to `/reviewer`. If fully submitted → `reviewer/summary.html` with per-instrument breakdown of submitted answers. |
| `GET /reviewer/sessions/{id}/summary.csv` | `_summary.py:109` | Same as the HTML summary (`pill_state == "submitted"`). | CSV download of own submitted responses, or 303 to `/reviewer`. |
| `POST /reviewer/sessions/{id}/recall` | `_surface.py` (next to `/submit`) | `lifecycle.is_ready(session)` only (no per-instrument-accepting check — recall is about removing the submitted stamp, not writing new values). | 403 outside `ready`. On `ready`: nulls `submitted_at` on every Response row for this reviewer's assignments, audits `responses.recalled`, 303s to `/1` so the reviewer lands on the editable form. Surfaced by the "Recall my submission" button on `summary.html`, which only renders when `can_recall = lifecycle.is_ready(session)`. |
| `GET /reviewer/invite/{token}` | `_invite.py:26` | None (token lookup + email match). | Stamps `opened_at` on the invitation row; 303 to `/reviewer/sessions/{id}`. State of the destination decides what they actually see. |

---

## The visibility matrix

Each row is a realistic state combination. Columns marked "n/a" mean the dimension doesn't materially affect the route's behaviour at that lifecycle. "Surface" = `GET /reviewer/sessions/{id}/{position}`.

| # | Session lifecycle | Instrument `accepting` | Deadline | Reviewer has assignments | Has saved responses | All submitted | Surface shows | Write paths | `/summary` shows | Dashboard pill / status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `draft` | n/a | n/a | yes | n/a | — | `pre_open.html` placeholder + deadline text (if set) + back link | 403 | 303 → `/reviewer` | "not started" / status="not opened" |
| 2 | `validated` | n/a | n/a | yes | n/a | — | `pre_open.html` (same) | 403 | 303 → `/reviewer` | "not started" / status="not opened" |
| 3 | `ready` | True | future | yes | no | — | Full form, editable; per-cell empty | Save / Submit / Clear all 200 | 303 → `/reviewer` | "not started" / status="open" |
| 4 | `ready` | True | future | yes | yes (drafts) | no | Full form, editable; inputs prefilled with current draft | Save / Submit / Clear all 200 | 303 → `/reviewer` | "in progress" / status="open" |
| 5 | `ready` | True | future | yes | yes (mix) | partially | Full form, editable; some rows in their submitted state, others in draft | Save / Submit / Clear 200 only on still-open rows | 303 → `/reviewer` | "in progress" / status="open" |
| 6 | `ready` | True | future | yes | yes | **yes** | Bare-URL `→ /summary` (dashboard link picks summary). Surface URL still renders the form, editable. | All write paths 200. | `summary.html` + `summary.csv` accessible | "submitted" / status="open" |
| 7 | `ready` | True | **past** (observe_deadline fired) | yes | any | any | Surface renders disabled inputs. Values visible iff `responses_visible_when_closed`. "No longer accepting responses" banner. | 403 | 303 → `/reviewer` unless fully submitted | per-state / status="closed" |
| 8 | `ready` | False (operator-closed), `responses_visible_when_closed=False` (default) | future or past | yes | yes (drafts or submitted) | n/a | Disabled inputs, **blank** (saved values hidden). Banner. | 403 | 303 → `/reviewer` unless fully submitted | per-state / status="closed" if all instruments closed |
| 9 | `ready` | False (operator-closed), `responses_visible_when_closed=True` | future or past | yes | yes | n/a | Disabled inputs, **prefilled** with saved values. Banner. **Read-only view of own work.** | 403 | 303 → `/reviewer` unless fully submitted | per-state / status="closed" if all instruments closed |
| 10 | `ready` | any | any | **no** (no assignments — e.g. rule filtered them out) | — | — | The surface page still renders for any reviewer in the session, but with zero rows in their table; the reviewer dashboard shows them no link to a per-instrument page either. | n/a | 303 → `/reviewer` (zero assignments → `pill_state ≠ "submitted"`) | "no assignments" if session has 0 active for this reviewer; otherwise per-instrument-row "no assignments" pill |
| 11 | `ready` | any | any | yes, but **all rows `include=False`** | n/a | — | Assignment query filters them out. Functionally identical to row 10. | n/a | Same as row 10. | Same as row 10. |
| 12 | `expired` (post-Close-session) | `False` on every instrument, `responses_visible_when_closed=False` | n/a | yes | yes | n/a | Surface renders disabled inputs, **blank** (saved values hidden). "No longer accepting responses" banner. Same as row 8 but reached via Close session instead of per-instrument close. | 403 | 303 → `/reviewer` unless fully submitted | status="closed" |
| 13 | `expired` (post-Close-session) | `False` on every instrument, `responses_visible_when_closed=True` | n/a | yes | yes | n/a | Surface renders disabled inputs, **prefilled** with saved values. Read-only view of own work, post-close. Same as row 9 but reached via Close session. | 403 | 303 → `/reviewer` unless fully submitted | status="closed" |
| 14 | `archived` (post-archive-from-draft) | n/a | n/a | yes (but reviewer dashboard filters this session out) | any | n/a | Reviewer dashboard hides the session. If they hit the URL directly, the surface bails to `pre_open.html` (`archived` is neither `ready` nor `expired`). | 403 | 303 → `/reviewer` | session absent from dashboard |

---

## Notes & nuances

### `pre_open.html` is the only "you don't get to see anything yet" surface

It's the same template for every non-`ready` state. The session
deadline is shown if set, otherwise there's no specific
"opens at" date — there's no `opens_at` field on sessions today;
the operator's act of clicking Activate is the only signal.

The template does **not** consult `responses_visible_when_closed`,
**not** consult the reviewer's saved responses, and **not** link
to a per-instrument page. There's no "preview your work pre-
activation" affordance.

### Deadline passage is lazy

`observe_deadline()` only runs when a reviewer (or anyone with a
similar request) hits a route that calls it. So an instrument
whose `deadline` passes overnight stays nominally
`accepting=True` in the DB until the first request the next
morning. Once that request lands, the close is audited with
`reason="deadline"` and persists. The reviewer who fired it sees
the post-deadline state on that same response.

### `accepting_responses=False` while session is `ready` is independent

Operators can manually close individual instruments while the
session stays `ready` (e.g. "instrument 1 is done, instrument 2
keeps accepting"). The reviewer-surface render handles them
per-row:

- Each instrument's form is rendered on its own URL (`/{id}/{position}`).
- Inputs on a closed instrument render `disabled` regardless of the
  reviewer's submission state.
- The "no longer accepting responses" banner is set at the top of
  the page when `not any_accepting` across the visible rows
  (`review_surface.html:47-58`).

### The `responses_visible_when_closed` toggle's two modes

- **`False` (default)** — once an instrument closes, the reviewer
  sees a disabled form with **blank** inputs. They have no way to
  read what they submitted unless they kept a copy.
- **`True`** — the same disabled form is **prefilled** with their
  values. Effectively a read-only "what I submitted" view, served
  through the same template they used to type it.

The toggle is per-instrument; the operator can decide per
instrument whether reviewer-side post-close visibility makes
sense for that data.

### `/summary` is binary

Either every assignment is submitted and the reviewer gets a
clean tabular summary + CSV download, or they get bounced. There's
no "show my drafts in progress" intermediate view today. This is
the route a fully-submitted reviewer would use to look back at
their own answers regardless of instrument-close state — but it
**stops working** if the operator reverts the session, since
revert blanks `submitted_at` on responses and the pill drops out
of `submitted`. (Drafts in the DB survive; the summary view of
them does not.)

### `Assignment.include=False` rows are invisible to reviewers

The Assignments-page Self-review toggle (and the per-row
include/exclude toggle) sets this flag. Once `False`, the
assignment is filtered out of every reviewer route's query —
they don't see "skipped" / "excluded" pills, the rows simply
don't appear. This is the canonical operator path for
suppressing self-reviews per the `excludeSelfReviews=False`
project policy (`spec/assignments.md` "Self-review policy").

### The dashboard's two badges aren't the same thing

- **Pill** (`session_pill_for_reviewer` in
  `app/services/responses.py:1328`) reports the reviewer's own
  submission state: `not started` / `in progress` / `submitted` /
  `no assignments`. Independent of session lifecycle.
- **Session status badge** (`session_status_for_reviewer` in
  `app/services/session_lifecycle.py:668`) reports the session's
  accepting-state from the reviewer's perspective: `not opened`
  (`draft` / `validated`) / `open` (`is_ready` + ≥1 instrument
  accepting + before deadline) / `closed` (`is_expired`, or
  `is_ready` but everything's shut by manual close / deadline).
  The dashboard hides the link to a session whose status reads
  `not opened`; `closed` keeps it live so reviewers can still
  reach `/summary` (and the per-instrument surface with
  `responses_visible_when_closed=True`) after the operator
  closed the session.

A reviewer can be `submitted` against a session that's now
`closed`, for example — that's the normal end state.

### Invitation tokens don't bypass anything

The token landing handler (`_invite.py:26-72`) stamps `opened_at`
and 303s the reviewer to the session's bare URL. From there the
surface route decides what they see. Pre-activation tokens still
land on `pre_open.html`. Post-archive tokens (if `archived` ever
becomes a real transition) would too.

---

## Cross-refs

- `spec/instruments.md` — the operator-side meaning of `accepting_responses`,
  `responses_visible_when_closed`, and the heading-row buttons that
  flip them.
- `spec/assignments.md` "Self-review policy" — why `include=False`
  is the canonical suppression mechanism rather than a lifecycle
  flag.
- `spec/session_home.md` — operator's view of the session
  lifecycle states + the Activate / Revert transitions that flip
  `is_ready`.
- `app/services/session_lifecycle.py` — canonical predicates and
  state machine.
- `app/web/routes_reviewer/_surface.py` — the master gate
  (line 823) + the per-cell `show_values` (line 421-429).
- `app/web/routes_reviewer/_summary.py` — the fully-submitted
  gate (line 41-53).
- `app/web/routes_reviewer/_dashboard.py` — the dashboard's pill
  + session-status badge logic.
- `app/web/templates/reviewer/pre_open.html` — the
  "opens later" placeholder.
- `app/web/templates/reviewer/review_surface.html` — the main
  form template; controls per-cell display via the `show_values`
  flag the route passes down.
