# Segment 20N — The Operator Lobby and the User Lobby

**Opened:** 2026-11-13 · **Theme:** one name for each landing page, across Cordware's apps · **Related:** `spec/sessions_overview.md`, `spec/reviewer-surface.md`, `docs/header_chrome.md`, Apply Desk's own lobbies (`applydesk/guide/todo_master.md`)

## Opportunity

Review Robin's two landing pages have two different kinds of name. The operator's is *Sessions* in the switcher and *Sessions Lobby* as its H1. The participant's is *Your reviews* in both. Apply Desk names its landing pages *Exercises* and *My ApplyDesk*. A user who moves between the apps through Cordware's switcher meets four names for two ideas. And `/operator` sends a non-operator to the lobby gate, which bounces them to `/me?notice=organizers`, rather than straight to `/me` as `/` does.

The author (2026-11-13) asked for one vocabulary across the apps: **Operator Lobby** and **User Lobby**. Both `/` and `/operator` should go to the Operator Lobby for an operator account, and to the User Lobby for anyone else.

## Decision

1. **The switcher** (`app/web/templates/_partials/top_bar.html`) offers **Operator Lobby** (`/operator/sessions`, operators and sys-admins only) and **User Lobby** (`/me`, everyone).
2. **The pages are retitled** to match. `/operator/sessions`'s H1 and `<title>` become *Operator Lobby*. `/me`'s become *User Lobby*. The URLs stay.
3. **`/operator` lands by role, as `/` does**: `/operator/sessions` for an operator or sys-admin, `/me` for anyone else. The lobby's own gate is unchanged, as a second line of defense.
4. **Breadcrumb links keep their words** (author). This segment does not touch any breadcrumb trail.

**Rejected:** renaming the routes (`/operator/lobby`, `/me/lobby`). The URLs are bookmarked and cited in emails; the names are what readers see.

## Semantics

- **The `<title>` suffix** stays `— Review Robin Web`, as on every other page.
- **The operator's switcher** lists both lobbies. An operator with assignments reaches the User Lobby from it, as they reach *Your reviews* today.
- **`/operator`** depends on `get_or_create_user`, as `/` does. A signed-out request meets Easy Auth before either.
- **`/me?notice=organizers`** stays for the deep links that land a non-operator on an operator page (`app/main.py`'s handler). Only bare `/operator` changes.

## Judgment calls — decided

- **The participant pages' Secondary *Your reviews* buttons** (`invite_mismatch.html`, `pre_open.html`, `summary.html`, `about.html`'s link) become *User Lobby*. They name the page they go to, like the switcher, and are not breadcrumbs.
- **`Sessions Lobby` joins `RETIRED_TERMS`**, since no code constant derives *Operator Lobby*. *Your reviews* does not join it: it is plain English that live prose uses for other things.

## Blast radius (measured)

Taken 2026-11-13 at `0fec4eba0`.

| What | Count | Command |
|---|---|---|
| *Sessions Lobby* in app, spec, docs | 7 lines, 4 files | `grep -rnF "Sessions Lobby" app spec docs --include=*.py --include=*.html --include=*.md` |
| *Your reviews* in app, spec, docs | 22 lines, 12 files | `grep -rnF "Your reviews" app spec docs --include=*.py --include=*.html --include=*.md` |
| Tests naming *Your reviews* or `data-your-reviews` | 6 files | `grep -rlF "Your reviews" tests; grep -rlF "data-your-reviews" tests` |
| The `/operator` redirect | 1 handler | `app/main.py` `operator_root` |

## Status

Building (2026-11-13).
- Rung 2, the build: the switcher, both pages' H1 and `<title>`, the participant pages' Secondary buttons and `/about`'s link read *Operator Lobby* / *User Lobby*; `/operator` lands by role through `/`'s own handler. `Sessions Lobby` joined `RETIRED_TERMS`, so `spec/sessions_overview.md` and `spec/rehydrate.md` took the new name in this rung rather than at close (the gate fails otherwise); the other Doc impact specs wait for the close's `spec-writer`.

## PR ladder

1. **Plan** (this file), its README row and its `guide/todo_master.md` entry. Prose only.
2. **The build.** The switcher's two entries; the two pages' H1 and `<title>`; the participant pages' *Your reviews* buttons; `/operator` by role; `RETIRED_TERMS`. Tests: the switcher's entries per role, the two titles, and `/operator` for an operator and for a participant. Must not touch breadcrumbs or URLs.
3. **Close**: `spec-writer` over the Doc impact specs; archive.

## Definition of done

- The switcher reads *Operator Lobby* and *User Lobby*; `tests/integration/test_participant_chrome.py` asserts both.
- `/operator/sessions` and `/me` carry the new H1 and `<title>`.
- `/operator` redirects a participant to `/me` and an operator to `/operator/sessions`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20N` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None. Apply Desk's lobbies follow in its own segment and are not this plan's.

## Out of scope

- **Apply Desk's lobbies**: its own plan (`applydesk/guide/`).
- **Breadcrumbs** (author) and **URLs** (Decision, rejected alternative).

## Doc impact

- `spec/sessions_overview.md` — the page's H1 is *Operator Lobby*.
- `spec/reviewer-surface.md` — `/me`'s H1, the switcher's entries and the Secondary buttons read *User Lobby*.
- `spec/visual_style_rrw.md` — the participant H1 and the top line's row name the User Lobby.
- `spec/rehydrate.md` — the Rehydrate button sits in the Operator Lobby.
- `spec/role_landing_and_visibility.md` — the dashboard's name, and `/operator` landing by role.
- `docs/header_chrome.md` — §3's switcher rows: Operator Lobby and User Lobby.
