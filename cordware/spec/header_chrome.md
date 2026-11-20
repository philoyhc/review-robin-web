# Header chrome: one top bar across Cordware's applications

**The shared contract for the top bar** in Review Robin, Residential
Operations, Support Logs and Apply Desk. It is Cordware's because the bar
belongs to no one application. Each application's own spec states its
share and points here: `spec/visual_style_rrw.md` ("Top bar"),
`residentialapps/spec/residentialops_ui.md` §2 and
`applydesk/spec/applications.md`.

## 1. Why

The applications looked like two products: Residential had one slim bar
with a switcher and the viewer's initials, Review Robin a text block with
its version, a breadcrumb and a row of text links. The direction taken was
Residential's: one bar, the same in every application, with each
application's own icon, accent and menu entries.

**In Review Robin, only the header changed** (author, 2026-11-02): what
sits above its first horizontal line, the `.chrome` block. The session nav
card, the status strip, page headings and page bodies did not.

## 2. The bar

One row, scrolling away with the page, at every width.

| Left | Right |
|---|---|
| The **app icon**, 28 px, then two lines: the **institution name** (12 px, subtle) over the **app or area name** (16 px, bold) and a ▾. The whole group opens the **switcher** (§3) | The **Light/Dark toggle**, the viewer's **name** (from 960 px), and the **avatar** (initials, accent background), which opens the **account menu** (§4) |

- **The icon replaces Residential's colored square.** It is the
  application's favicon, the one `cordware/web/app_icons.py` copies for
  the landing page, so one SVG serves the tab, the landing page and the
  bar.
- **The top line** is the institution name (§6). Residential's top line is
  the same slot: its resolution in §6 yields the Unit's name.
- **No top line when it resolves empty**: the app name sits alone,
  vertically centered.
- **Under 640 px** the toggle and the name leave the bar for the account
  menu, leaving icon, titles and avatar. The top line truncates with an
  ellipsis before the app name does.
- **The version leaves the bar.** Operators see it in the account menu,
  beside About.

## 3. The switcher

A menu of places in this application, then the way out to the others.
Built as Residential's is: a `details`/`summary` disclosure, no script
needed to open it.

- **First group, headed by the application's name**: the places the
  viewer can reach, the current one marked (✓ and `aria-current`).
- **Support Logs' Unit group, headed "Unit"**, between them, only for a
  viewer holding grants in more than one Residential Unit: those Units,
  the working one marked (✓ and `aria-current`); choosing one sets it
  for this browser (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md`
  §3.7, 2026-11-08).
- **Last group, headed "Cordware"**: **All applications**, the host's
  landing page. An application never lists the host's other mounts
  itself (`residentialapps/spec/residentialops_ui.md` §2 gives why).

| Application, viewer | First group |
|---|---|
| Review Robin, operator or sys admin | Operator Lobby; User Lobby |
| Review Robin, participant | User Lobby |
| Residential Operations | Its areas |
| Support Logs | Its areas |
| Apply Desk | Operator Lobby (operators); User Lobby |

A viewer with only one place and no other application still gets the
menu, for All applications. A page that registers no places shows the
switcher static, without the ▾, as Residential's does.

## 4. The account menu

The avatar opens it, in every application; it holds Sign out.

1. **Who**: the display name in bold; under it the email and the tier,
   "super admin" or "sys admin" when held. Lets a viewer on a shared
   computer confirm who is signed in, which "Signed in as" did.
2. **Application entries**, each only for a viewer who may use it:
   - Review Robin: **Settings** (operators and sys admins), **Admin**
     (sys admins), **Guide** (a viewer who resolves a Guide audience, the
     fail-open `guide_hidden` flag), **About**, with the
     version beside it for operators and sys admins.
   - Residential: **Sys admin**, for a viewer who holds it; in Support
     Logs, **Who can see what**, its staff explainer (2026-11-07); Guide
     and About when they exist.
3. **Under 640 px**: the Light/Dark toggle and the viewer's name.
4. **Sign out**, last, its own group: `/.auth/logout`.

- **Return to origin is kept.** Settings, Admin, Guide and About still
  carry `?return_to=` the current page.
- **An entry is omitted on its own page**: no Settings on
  Settings, no About on About, and none of them on Sign-in details.
- **Guide sits here, not in the switcher** (author, 2026-11-02): it is
  help, not a place.

## 5. Under the bar

At most one thin row, the application's to fill:

- **Residential and Support Logs**: the area's page tabs, unchanged.
- **Review Robin**: the **breadcrumb**
  (`app/web/templates/_partials/breadcrumb.html`), on its own row inside
  the header, under the bar and above the header's one bottom line. No
  line between the bar and the
  breadcrumb. Rendered only where a page has one. Under 640 px the middle
  crumbs collapse to "…". Below the header's line nothing changes (§1).
- **Participants**: no row.

## 6. The top line: institution, or the operator's unit

**One name per workspace, set by Cordware; in Review Robin and Apply Desk
an operator's unit replaces it** (author, 2026-11-02). One deployment may
host a department next door that has no deployment of its own; its people
should see their own name, not the host's. A courtesy, kept simple.

### Where it is set

| Layer | Set by | Holds |
|---|---|---|
| **Workspace default** | The deployer: a Cordware platform setting, `CORDWARE_INSTITUTION_NAME`, read by every application through Cordware's settings | The hosting institution, e.g. "Example University". Empty means no top line |
| **Review Robin, the operator's Unit** | A sys admin, on the account's row in Accounts Management | The account's `users.unit`, e.g. "Department of Example". Empty means the default |
| **Apply Desk, the operator's Unit** | As Review Robin, once its operators have Units; until then the default | As Review Robin |
| **Residential** | Its own setup, where the top-level Unit is named | The top-level Unit's name |

- **Only a sys admin edits Unit.** An operator sees theirs, read-only, on
  Settings, and cannot change it; nor is it set per session.
- **Every change is audited**: `workspace.user_unit_set`, a `changes`
  envelope on the user.
- **Length**: at most 80 characters, trimmed; the bar truncates it.

### Which name a page shows

Review Robin and Apply Desk:

| Page | Name shown |
|---|---|
| A session's pages, operator or participant, Sessions Diagnostics' Outbox and Audit log included | The Unit of the operator who **created** the session, else the default. Co-owners do not change it |
| An operator's other pages (lobby, Settings, Admin, Create session) | The viewer's own Unit, else the default |
| User Lobby, whoever views it | The default, unless every session listed resolves to the same Unit (author, 2026-11-02: a session belongs to its creator's Unit; the viewer's own Unit plays no part here) |
| About, Guide, Sign-in details | The viewer's own Unit if an operator, else the default |

The creator's Unit is read when the page renders, so a sys admin's change
shows on that operator's existing sessions at once.

**Residential**: the top-level Unit's name when it is set and differs
from the default; otherwise the default: in practice, the college. In
Support Logs it is the viewer's working Unit (2026-11-08),
which the summary's accessible name also carries when the viewer has
more than one.

## 7. Behavior and accessibility

- Both menus are disclosures (`details`/`summary`): open on click, Enter
  or Space; close on Escape, on a click outside and when the other opens.
  That closing needs a small inline script; without it a menu still opens
  and closes on its own toggle.
- **Targets**: the switcher, the avatar and every menu entry are at least
  44 px tall, as Residential's are (`residentialapps/spec/residentialops_ui.md`
  §10).
- **Labels**: the switcher's `summary` is labeled "Switch area: {area}";
  the avatar's is labeled "Account: {display name}"; the icon is
  decorative (`alt=""`).
- **URLs** are emitted through `url()`, `here()` and `host_url()`, never
  written root-relative.
- **One template per family**: Review Robin's operator and participant
  bars are one partial, `_partials/top_bar.html`, with different
  entries; Residential and Apply Desk each have their own partial to the
  same contract.

## 8. Each application's share

**This file is the contract for all three**; each application builds its
own bar to it.

- **Review Robin**: every surface, operator and participant (§1).
- **Residential**: the icon in place of the square (§2), Sign out and the
  account menu (§4), the top line's fallback to the workspace default
  (§6), and the toggle moving into the menu under 640 px. Sys admin is an
  account-menu entry, as Review Robin's Settings and Admin are. Its
  switcher's places and tabs are its own.
- **Apply Desk**: the bar of §2–§4 in
  `applydesk/templates/applydesk/base.html`; its top line is the
  workspace default until its operators have Units.

## 9. What holds

- Every page of the three applications renders the bar of §2, with its
  own icon.
- Review Robin's bar shows no version, no "Signed in as", no inline
  links; everything they offered is in the account menu.
- With `CORDWARE_INSTITUTION_NAME` unset and no Units, no page shows a
  top line in Review Robin; set, every page does. An operator given a
  Unit sees it on the sessions they created, and so do those sessions'
  participants and co-owners; operators cannot edit it.
- Both menus work by keyboard, in light and dark, at 390 px and at
  desktop width.
