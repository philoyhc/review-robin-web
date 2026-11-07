# Header chrome: one top bar across Cordware's applications

**Functional spec, built** (author, 2026-11-02). It sets what the top bar
does in Review Robin, Residential Operations, Support Logs and the
envisioned ApplyDesk. Built the same day: Review Robin in segment 20D
(#3505–#3510), Residential Operations and Support Logs in #3511. The
settled parts are also stated in `spec/visual_style_rrw.md` ("Top bar")
and `residentialapps/spec/residentialops_ui.md` §2; this file stays the
shared contract, ApplyDesk's included. §1 describes the chrome it
replaced.

## 1. Why

Today the applications look like two products:

- **Residential** has one slim bar: a colored square, the Unit's name
  over the area's, a switcher menu, the Light/Dark toggle, the viewer's
  name and initials (`residentialapps/spec/residentialops_ui.md` §2).
- **Review Robin** has a text block: "Review Robin Web App (version …)",
  the toggle, a breadcrumb under it, and on the right "Signed in as …",
  up to four text links and a Sign out button
  (`spec/visual_style_rrw.md`, "Non-session and reviewer chrome").
  Participants get a lighter variant
  (`app/web/templates/reviewer/_top_bar.html`). <!-- path-ref-ok -->

The direction is Residential's. One bar, the same in every application,
with each application's own icon, accent and menu entries.

**In Review Robin, only the header changes** (author, 2026-11-02): what
sits above its first horizontal line today, the `.chrome` block. Nothing
below that line changes: not the session nav card, the status strip, page
headings or any page body.

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
- **Last group, headed "Cordware"**: **All applications**, the host's
  landing page. An application never lists the host's other mounts
  itself (`residentialapps/spec/residentialops_ui.md` §2 gives why).

| Application, viewer | First group |
|---|---|
| Review Robin, operator or sys admin | Sessions (the lobby); Your reviews |
| Review Robin, participant | Your reviews |
| Residential Operations | Its areas, as today |
| Support Logs | Its areas, as today |
| ApplyDesk | Its areas, when it has them |

A viewer with only one place and no other application still gets the
menu, for All applications. A page that registers no places shows the
switcher static, without the ▾, as Residential's does.

## 4. The account menu

The avatar opens it. It replaces Review Robin's "Signed in as …", its
text links and its Sign out button, and gives Residential the Sign out it
lacks.

1. **Who**: the display name in bold; under it the email and the tier,
   "super admin" or "sys admin" when held. Lets a viewer on a shared
   computer confirm who is signed in, which "Signed in as" did.
2. **Application entries**, each only for a viewer who may use it:
   - Review Robin: **Settings** (operators and sys admins), **Admin**
     (sys admins), **Guide** (a viewer who resolves a Guide audience, the
     same fail-open `guide_hidden` flag as today), **About**, with the
     version beside it for operators and sys admins.
   - Residential: Sys admin, where it is a menu entry today; in Support
     Logs, **Who can see what**, its staff explainer (2026-11-07); Guide
     and About when they exist.
3. **Under 640 px**: the Light/Dark toggle and the viewer's name.
4. **Sign out**, last, its own group: `/.auth/logout`.

- **Return to origin is kept.** Settings, Admin, Guide and About still
  carry `?return_to=` the current page, as their links do today.
- **An entry is omitted on its own page**, as today: no Settings on
  Settings, no About on About, and none of them on Sign-in details.
- **Guide sits here, not in the switcher** (author, 2026-11-02): it is
  help, not a place.

## 5. Under the bar

At most one thin row, the application's to fill:

- **Residential and Support Logs**: the area's page tabs, unchanged.
- **Review Robin**: the **breadcrumb**
  (`app/web/templates/_partials/breadcrumb.html`), on its own row inside
  the header, under the bar and above the header's one bottom line, where
  it sits today under the app identity. No line between the bar and the
  breadcrumb. Rendered only where a page has one. Under 640 px the middle
  crumbs collapse to "…". Below the header's line nothing changes (§1).
- **Participants**: no row.

## 6. The top line: institution, or the operator's unit

**One name per workspace, set by Cordware; in Review Robin and ApplyDesk
an operator's unit replaces it** (author, 2026-11-02). One deployment may
host a department next door that has no deployment of its own; its people
should see their own name, not the host's. A courtesy, kept simple.

### Where it is set

| Layer | Set by | Holds |
|---|---|---|
| **Workspace default** | The deployer: a Cordware platform setting, `CORDWARE_INSTITUTION_NAME`, read by every application through Cordware's settings as `APP_ENV` is today | The hosting institution, e.g. "Example University". Empty means no top line |
| **Review Robin, the operator's Unit** | A sys admin, on the account's row in Accounts Management | A new field on the operator's account, e.g. "Department of Example". Empty means the default |
| **ApplyDesk, the operator's Unit** | As Review Robin | As Review Robin |
| **Residential** | Its own setup, where the top-level Unit is named | The top-level Unit's name |

- **Only a sys admin edits Unit.** An operator sees theirs, read-only, on
  Settings, and cannot change it; nor is it set per session.
- **Every change is audited**: a `changes` envelope on the user, under a
  new event type registered in `EVENT_SCHEMAS`.
- **Length**: at most 80 characters, trimmed; the bar truncates it.

### Which name a page shows

Review Robin and ApplyDesk:

| Page | Name shown |
|---|---|
| A session's pages, operator or participant, Sessions Diagnostics' Outbox and Audit log included | The Unit of the operator who **created** the session, else the default. Co-owners do not change it |
| An operator's other pages (lobby, Settings, Admin, Create session) | The viewer's own Unit, else the default |
| Your reviews, whoever views it | The default, unless every session listed resolves to the same Unit (author, 2026-11-02: a session belongs to its creator's Unit; the viewer's own Unit plays no part here) |
| About, Guide, Sign-in details | The viewer's own Unit if an operator, else the default |

The creator's Unit is read when the page renders, so a sys admin's change
shows on that operator's existing sessions at once.

**Residential**: the top-level Unit's name when it is set and differs
from the default; otherwise the default. In practice that is the college,
as today.

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
  bars become one partial with different entries, retiring the separate
  reviewer bar; Residential keeps its own partial to the same contract.

## 8. Residential and ApplyDesk

**This file is the contract for all three.** The build is per application:

- **Review Robin**: built, `guide/archive/segment_20D_header_chrome.md`, header only (§1).
- **Residential**: built ahead of its plans, in #3511 (the plans record it): the bar in
  `residentialapps/guide/segment_1C_ra_leave.md`, Support Logs' entries in
  `residentialapps/guide/segment_1D_support_logs.md`, the role and the top
  line in `residentialapps/guide/segment_1B_rosters_and_organization.md`.
  Its share: the icon in place of the square (§2), Sign out and
  the account menu (§4), the top line's fallback to the workspace default
  (§6), and the toggle moving into the menu under 640 px. Sys admin is an
  account-menu entry, as Review Robin's Settings and Admin are (author,
  2026-11-02). Its switcher's places and tabs stay as they are.
- **ApplyDesk** does not exist yet; §2–§6 fix its bar and its Unit so it
  is born matching.

## 9. Done when

- Every page of the three applications renders the bar of §2, with its
  own icon.
- Review Robin's bar shows no version, no "Signed in as", no inline
  links; everything they offered is in the account menu.
- With `CORDWARE_INSTITUTION_NAME` unset and no Units, no page shows a
  top line in Review Robin; set, every page does. An operator given a
  Unit sees it on the sessions they created, and so do those sessions'
  participants and co-owners; operators cannot edit it.
- In Review Robin, a page compared before and after differs only above
  the header's bottom line.
- The browser checks: both menus by keyboard, light and dark, at 390 px
  and at desktop width.
