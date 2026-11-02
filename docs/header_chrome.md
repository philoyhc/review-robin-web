# Header chrome: one top bar across Cordware's applications

**Functional spec, proposed** (author, 2026-11-02). Not built. It sets
what the top bar does in Review Robin, Residential Operations, Support
Logs and the envisioned ApplyDesk, so a segment plan can cut it into
slices. Mock-ups were reviewed in the session that wrote this. When it
ships, the settled parts move into `spec/visual_style_rrw.md` ("Top bar",
both of them) and `residentialapps/spec/residentialops_ui.md` §2, and this
file is retired.

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
  (`app/web/templates/reviewer/_top_bar.html`).

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
   - Residential: Sys admin, where it is a menu entry today; Guide and
     About when they exist.
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

## 6. The institution name

**One name per workspace, set by Cordware, overridden where an
application serves a neighboring unit** (author, 2026-11-02). One
deployment may host a department next door that has no deployment of its
own; its people should see their own name, not the host's.

### Where it is set

| Layer | Set by | Holds |
|---|---|---|
| **Workspace default** | The deployer: a Cordware platform setting, `CORDWARE_INSTITUTION_NAME`, read by every application through Cordware's settings as `APP_ENV` is today | The hosting institution, e.g. "Example University". Empty means no top line |
| **Review Robin, per operator** | An admin, on the account's row in Accounts Management | A neighboring unit's name, for that operator. Empty means the default |
| **ApplyDesk, per operator** | As Review Robin | As Review Robin |
| **Residential, per deployment's data** | Rosters and setup, where the top-level Unit is named | The top-level Unit's name |

- **Admins edit overrides; operators don't.** An override names who
  people see the operator as working for, so it is an admin's call. An
  operator sees theirs, read-only, on Settings.
- **Every change is audited**: the override as a `changes` envelope on the
  user, under a new event type registered in `EVENT_SCHEMAS`.
- **Length**: at most 80 characters, trimmed; the bar truncates it.

### Which name a page shows

Review Robin and ApplyDesk resolve per page:

| Page | Name shown |
|---|---|
| A session's pages, operator or participant | The override of the session's creator, else the default |
| An operator's other pages (lobby, Settings, Admin, Create session) | The viewer's own override, else the default |
| A participant's Your reviews | The default, unless every session listed resolves to the same override |
| About, Guide, Sign-in details | The viewer's own override if an operator, else the default |

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

## 8. Open questions

1. **A session's name when its operators disagree.** The creator's
   override is proposed. The alternative, the name stamped on the session
   at creation and editable on Session Home, is steadier but adds a
   column and a control.
2. **Should an operator edit their own override?** Proposed no (§6).
3. **Residential's share of the work.** The icon swap and Sign out are
   Residential's; whether they land with Review Robin's slices or on
   Residential's own plan.
4. **ApplyDesk.** It does not exist yet; this fixes its bar and its
   override only so it is born matching.

## 9. Done when

- Every page of the three applications renders the bar of §2, with its
  own icon.
- Review Robin's bar shows no version, no "Signed in as", no inline
  links; everything they offered is in the account menu.
- With `CORDWARE_INSTITUTION_NAME` unset, no page shows a top line in
  Review Robin; set, every page does; an operator with an override sees
  it on their sessions, and so do those sessions' participants.
- In Review Robin, a page compared before and after differs only above
  the header's bottom line.
- The browser checks: both menus by keyboard, light and dark, at 390 px
  and at desktop width.
