# Segment 20D — Header chrome

**Opened:** 2026-11-02, at the author's request · **Theme:** Review Robin's header becomes Cordware's shared top bar, and operators gain a Unit · **Related:** `docs/header_chrome.md` (the functional spec this builds to), `spec/visual_style_rrw.md`, `residentialapps/guide/segment_1C_ra_leave.md` (Residential's share)

## Opportunity

Review Robin and Residential read as two products (`docs/header_chrome.md` §1). Review Robin's header is a text block: "Review Robin Web App (version …)", the theme toggle and a breadcrumb on the left; "Signed in as …", up to four text links and a Sign out button on the right, in two variants (operator in `app/web/templates/base.html`, participant in `app/web/templates/reviewer/_top_bar.html`). Residential has one slim bar with a switcher and an avatar. Nothing names the institution, and a neighboring unit hosted on the same deployment has no way to show its own name (author, 2026-11-02).

## Decision

**Build `docs/header_chrome.md` for Review Robin: the shared bar, its two menus, the workspace's institution name and the operator's Unit.** The header changes and nothing below its bottom line does (§1 of the spec).

- One partial for every viewer, replacing the operator block in `base.html` and the reviewer bar: icon, top line over "Review Robin", the switcher; theme toggle, name, avatar and account menu (§2–§4).
- The breadcrumb stays inside the header, on a row under the bar (§5).
- `CORDWARE_INSTITUTION_NAME`, a Cordware platform setting beside `APP_ENV`, is the default top line (§6).
- `users.unit`, set by a sys admin on Accounts Management and shown read-only on Settings, replaces it: a session shows its creator's Unit (§6). On Accounts Management it is a **column after Name** (author, 2026-11-02).

Rejected: *a per-session name, editable on Session Home.* Steadier when owners differ, but a column and a control for a courtesy; the author ruled it out ("let's not complicate").

Rejected: *Residential's bar extracted into a shared Cordware partial.* The import boundary keeps applications from sharing templates through `cordware`, and the two families' entries differ; each builds to the same contract instead.

## Semantics

- **Unit empty or whitespace** stores `NULL` and resolves to the default; trimmed; at most 80 characters, refused above with the form's message.
- **Default empty** and no Unit: no top line; "Review Robin" alone, vertically centered.
- **A session's creator** is `sessions.created_by_user_id`, non-nullable, so every session has one. Their Unit is read at render: a sys admin's change shows on existing sessions at once. A creator who is no longer an operator keeps their Unit for this purpose.
- **Your reviews** shows the default unless every listed session resolves to one Unit (§6's table).
- **A non-operator account** holds no Unit control on Accounts Management; a Unit set while they were an operator is kept, unused off their sessions.
- **Accounts Management's Unit column** shows what that operator's pages resolve to. A set Unit is plain text. With no Unit, the column shows the workspace default (`CORDWARE_INSTITUTION_NAME`) as a **display pill** (`pill pill-count`, the lobby's style), marking it as following the Cordware setting. With no default either, it shows "—". Non-operators' cells are blank (author, 2026-11-02).
- **Concurrent edits** to one account's Unit: last write wins, each audited.
- **Removed items:** the "(version …)" text, "Signed in as", the inline links and the Sign out button leave the bar; the account menu holds each, with today's gates, `return_to` and per-page omissions.

## Judgment calls — decided

- The icon is Review Robin's own favicon string, already in `base.html`, not imported from `cordware/web/app_icons.py`: an application never imports the host's web package.
- One partial with a participant flag, rather than two partials, so the reviewer bar cannot drift again.
- The Unit audit event is a `changes` envelope on the user, named like its neighbors in `app/services/users.py` (`workspace.*`), e.g. `workspace.user_unit_set`.
- **`CORDWARE_INSTITUTION_NAME` is set in production by the private Cordware repository**, not in RRW: the real value never enters this public repository. Unset is safe, since the bar then has no top line.

## Blast radius (measured)

Taken 2026-11-02 at `f8c5cad1`.

| What | Count | Command |
|---|---|---|
| Templates overriding `top_bar` | 11 | `grep -rln 'block top_bar' app/web/templates \| wc -l` |
| Includers of the reviewer bar | 11 | `grep -rln 'reviewer/_top_bar.html' app/web/templates \| wc -l` |
| Test files naming "Signed in as" / `chrome-link` / `signout` / `chrome-app-identity` | 8 / 17 / 4 / 7 | `grep -rln -- '<term>' tests \| wc -l` |
| Test files naming `data-your-reviews` | 8 | as above |
| `chrome` lines in `base.html` | 45 | `grep -n chrome app/web/templates/base.html \| wc -l` |
| Specs and docs naming "Review Robin Web App" | 6 | `grep -rln 'Review Robin Web App' spec docs \| wc -l` |

## PR ladder

Code slices take one `diff-reviewer` read, at rung 5, on the cumulative diff from the base SHA rung 1's PR body records.

1. **The bar, scaffold.** The shared partial, its CSS in `base.html`, the icon, "Review Robin" without a top line, the breadcrumb row; the switcher and account menu holding today's links, version beside About. The reviewer bar retired. Tests moved to the new markup. Must not touch anything below the header's line.
2. **Menus and narrow widths.** One menu open at a time, Escape and an outside click close it; under 640 px the toggle and name move into the account menu, the breadcrumb's middle collapses. A browser test drives both menus by keyboard.
3. **The workspace's institution name.** `CORDWARE_INSTITUTION_NAME` in `cordware/settings.py`, read through Cordware's settings; the top line renders it on every page.
4. **Unit, scaffold.** Accounts Management's Unit column after Name (plain text, or the default as a display pill) with its sys-admin edit control, and Settings' read-only line, inert, with real copy.
5. **Unit, wired.** Migration adding `users.unit`; the service and its audit event, registered in `EVENT_SCHEMAS`; the page resolution in `app/web/views/`; tests for each row of §6's table. Last build rung: the cumulative read.

## Definition of done

- Every Review Robin page renders the bar of `docs/header_chrome.md` §2; no page renders "Review Robin Web App", "Signed in as" or a `.signout` button.
- `app/web/templates/reviewer/_top_bar.html` is gone.
- The browser checks pass: both menus by keyboard, light and dark, 390 px and 1280 px; a before-and-after comparison differs only above the header's line.
- With the default unset and no Units, no top line; with it set, every page shows it; a sys admin's Unit for an operator shows on that operator's sessions, to their co-owners and participants; operators cannot edit it.
- `alembic upgrade head` and the downgrade round-trip pass on Postgres in `ci-postgres`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**Where the Unit control sits on Accounts Management.**~~ **A column after Name; the inherited default shows as a display pill** (author, 2026-11-02).

## Out of scope

- Residential's share: under its own plans, `residentialapps/guide/segment_1C_ra_leave.md` (the shared bar), `residentialapps/guide/segment_1D_support_logs.md` (Support Logs' entries) and `residentialapps/guide/segment_1B_rosters_and_organization.md` (the Unit fallback).
- ApplyDesk: not yet an application; `docs/header_chrome.md` fixes its bar for when it is.
- Anything below the header's line, the session nav card included.

## Doc impact

- `spec/visual_style_rrw.md` — both "Top bar" sections replaced by the shared bar, its menus and the breadcrumb row.
- `spec/operator_ui_concept.md` — "Cross-page chrome (top of every page)" to the shared bar; Accounts Management, in "Page taxonomy", gains the Unit column after Name.
- `spec/settings_inventory.md` — `users.unit` in §1 (sys-admin-set), `CORDWARE_INSTITUTION_NAME` in §8.
- `spec/architecture.md` — `users.unit` on the User entity and the new audit event type.
- `cordware/spec/identity.md` — `CORDWARE_INSTITUTION_NAME` among the platform settings applications read.
- `docs/header_chrome.md` — Review Robin's part marked built; retired once Residential's ships.
- `guide/todo_master.md` — the queue entry, deleted at close.
