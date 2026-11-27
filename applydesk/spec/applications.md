# Apply Desk as the host sees it

> **Built:** every page below, as a working scaffold on sample data and stored applications, behind
> a real check of who may reach it. Every move works on screen. An
> exercise's own settings (Details, the Lobby's name, code and tags, its
> archive), its Process (stages, gates, outcomes, rules, the form's state),
> its Form, its Panels, its Emails, its Candidates and its applications are
> stored in the database; the rest of a sample exercise saves nothing until a later AD2
> segment, and nothing is sent to Review Robin until AD6. A made exercise
> ("Ordinary exercises") is a row in the database like any other.

Apply Desk's contract with the Cordware host. The host's side is
`cordware/spec/host.md`; this file states only what Apply Desk adds. The
rulings behind it are `applydesk/guide/todo_master.md`.

## The registry entry

| | |
|---|---|
| Registry name | `applydesk` |
| Mount path | `/applydesk` |
| Factory | `applydesk.main:create_app` |
| Logger prefix | `applydesk` |
| Landing-page title | `Apply Desk` |
| Icon | A white application sheet on a rose (`#be123c`) tile, running off the bottom-right, a tick cut in rose (author, 2026-11-02). The source is `applydesk/templates/applydesk/base.html`, copied to `cordware/web/app_icons.py` |

- The registry lists it second, after Review Robin and before
  Residential's two applications and Utilities: the landing page's
  order (author, 2026-11-13; `cordware/spec/host.md`).
- The factory is a zero-argument callable returning a new `FastAPI`
  application with no schema pages (`/docs`, `/redoc`,
  `/openapi.json`). It reads no setting and opens no database.

## Health

`GET /applydesk/health` returns `{"status": "ok"}`, route name
`applydesk_health`, with no sign-in, setting or database. Excluding it
from Easy Auth is a deployment step.

## Running alone

`CORDWARE_APPS=applydesk` starts with Apply Desk alone; an unset value
mounts it beside every other application. Its records are stamped
`application: applydesk` in the host's logs.

## The URL map

Paths are under `/applydesk`: operators under `/operator/exercises`,
participants under `/me`. `<id>` is an exercise's public ID, `<app>` an
application's, `<dossier>` a dossier's and `<gate>` a gate's key (`g1`…).
Every page is a `GET`; the operator's are `applydesk/routes_operator.py`, the
participant's `applydesk/routes_me.py`, the Admins' (and the super-admin's)
`applydesk/routes_admin.py`. The few `POST`s are named where they belong.

| Path | Page |
|---|---|
| `/health` | Health (above) |
| `/`, `/operator` | No page: they land by role (below) |
| `/operator/exercises` | The Operator Lobby: the exercises the viewer owns or operates, in two cards over one table |
| `/operator/exercises/archived` | The Archive: the archived exercises, each with *Restore* |
| `/operator/exercises/<id>` | Exercise Home: the timeline and Details |
| `…/<id>/process` | Process: stages, gates, outcomes, their rules, and which items email whom |
| `…/<id>/form` | Form: the application form builder |
| `…/<id>/form/preview` | The form as an applicant sees it, in its own tab |
| `…/<id>/panels` | Panels: the exercise's rosters in one table |
| `…/<id>/emails` | Emails: every template the exercise owes |
| `…/<id>/dossiers` | Dossiers: a row per dossier, the exercise's control surface |
| `…/<id>/dossiers/<dossier>` | A dossier as the operator sees it; 404 for no such dossier |
| `…/<id>/evaluations` | Evaluations: each gate's state, progress and assignments |
| `…/<id>/evaluations/<gate>` | A gate's pairs, a row each; 404 for a Draft exercise, no such gate or a removed gate's key. An old `gate_<n>` path redirects (302) to the gate it numbers now |
| `…/<id>/extract` | Extract data: the download cards |
| `…/<id>/extract/<file>` | One download (see Extract data, "The route") |
| `/admin/exercises` | Admin → Exercises Diagnostics: the exercises, a scaffold (Admins and the super-admin) |
| `/admin/exercises/<id>/manage` | Post: *Manage*, adopting the exercise first where the viewer holds no role, then opening Home |
| `/admin/operators` | Admin → Accounts Management: Workspace users and the Add card (Admins and the super-admin) |
| `/admin/operators/suggest` | The Add card's typeahead: JSON |
| `/admin/operators/admit`, `/admin/operators/bulk` | Posts: admit one pick; admit, revoke, promote or demote the ticked rows (promote and demote only for whoever may make Admins) |
| `/admin/system` | Admin → System Status: a scaffold |
| `/me` | The User Lobby |
| `/me/exercises/<id>` | An exercise as an applicant sees it: its timeline and *Apply* |
| `/me/exercises/<id>/applications/<app>` | The applicant's application |
| `/me/exercises/<id>/dossiers/<dossier>` | The dossier an evaluator opens |

Any other page under an exercise is a 404. The `/me/exercises/<id>` pages
answer only for a Published or Closed exercise.

- **Public IDs** (`applydesk/ids.py`): 10 symbols from RRW's alphabet,
  `23456789abcdefghjkmnpqrstuvwxyz`, drawn at random. A path whose ID has
  any other shape, or names nothing, is a 404 before anything is read. A
  person's row ID (`ids.row_id`) is a whole number from 1 to 2³¹−1: out of
  range in a path it is a 422; a form's malformed one is never looked up
  (the post is refused, 400, unless it names a directory pick instead).
- **The dossier**, what an evaluator opens, one per application
  (`/me/exercises/<id>/dossiers/<dossier>`), is named by its own ID, never the
  application's, and shows only the *Shown to evaluators* section. In a blind exercise it
  redacts the applicant's name and identifiers. It and the applicant's own
  application page read the Form's questions (text blocks aside), grouped
  by visibility in the Form's order, with the answers Extract writes, *—*
  where there is none (`extract.form_answers`); the title is the page's
  heading alone.
- **The chrome** is the shared bar (`cordware/spec/header_chrome.md`): the app
  icon, the workspace's top line over *Apply Desk* (the app's name, as
  Review Robin's bar names Review Robin; author, 2026-11-13), a switcher of the
  *Operator Lobby* (`/operator/exercises`, operators only) and the *User
  Lobby* (`/me`) then *All applications*, the Light/Dark toggle and the
  account menu, which carries *Admin* for Admins and the platform super-admin
  (`cordware/spec/header_chrome.md` §4) and, under the name, a line reading
  *super admin* or *admin*. Each lobby's H1 and tab read its name, as Review Robin's
  do (author, 2026-11-13). An exercise's operator pages add Review Robin's chrome
  under a breadcrumb (ruling 14, segment AD1D): *Exercise Home*
  double-height on the left; a Setup row (Process, Form, Panels, Emails)
  and an Operations row (Dossiers, Evaluations, Extract data); and a
  status row of the exercise, its form, gates, outcomes, emails and
  applications.
- **Layout**: the operator's pages, `/operator/…`, take Review Robin's: a
  fixed 40 px left margin and up to 1400 px wide, desktop work surfaces.
  The participant's pages, `/me/…`, keep a centred column of 1232 px
  (author, 2026-11-13). The bar's icon sits 24 px under the browser's
  edge, and an exercise's breadcrumb just under the bar with no line
  between, as in Review Robin.
- **`/` and `/operator`** have no page of their own: they land an
  operator on the Operator Lobby and anyone else on the User Lobby, as
  Review Robin's do. An operator is the platform super-admin or someone
  on the operator list (`gate.is_operator`; an Admin is on it), whether or not
  they operate an exercise yet, so they can reach the Lobby to make one.
- **Who reaches what** (`applydesk/gate.py`; the target model, Owners and operators, is `applydesk/spec/permissions.md`). Anyone else, signed in or not,
  gets a 404 on a local run too, so a page does not say it exists.

  | Pages | Reached by |
  |---|---|
  | `/operator/…` | The platform super-admin, or someone on the operator list (Admins included) |
  | An exercise's pages, `/operator/exercises/<id>/…` | Whoever holds a current grant on that exercise, the super-admin and Admins included: one they hold none on, they adopt from Exercises Diagnostics |
  | `/admin/…` | Admins and the super-admin; an operator is not enough |
  | The landing, `/` and `/operator` | Any operator (so a deployed operator lands on the Lobby); anyone else the placeholders' gate |
  | `/me/…` | The placeholders' gate (`gate.placeholders_only`): anyone on a local run, deployed only the super-admin, until a later AD2 segment |

  A link to `/me/…` (the switcher's *User Lobby*, a dossier's *View as
  evaluators see it*) is offered only where that gate admits the viewer
  (`gate.reaches_placeholders`, `participant_pages` in the page context), so
  none leads to a 404.

  Taking someone off the operator list ends their access at once and keeps
  their grants. The super-admin has no implicit reach to exercises: their
  reach is their grants, as anyone's. An unbound super-admin (a sign-in naming
  no tenant or object ID) reaches the Admin pages and the Lobby but no
  exercise, since adopting one needs a person.
- **The people** behind the check are bound by tenant and object ID, as
  Residential's are (`residentialapps/docs/residentialapps_email_identity_matching.md`):
  - A sign-in finds its person by (tenant, object ID). Failing that, a
    *pending* person, known only by address, whose address matches the UPN or
    the mail is bound. Failing that, a new person is made. A bound person's
    address is a snapshot and never matched again; only a pending person is
    matched by address.
  - Two different pending people matching one sign-in fail closed: neither is
    bound, and the new person has no access until the super-admin settles it.
  - A pending person has no access until bound. A person found in the
    directory is stored bound, so pending people are rare: an address the
    directory did not find.
  - A sign-in with no tenant or object ID cannot be bound and has no access
    (the super-admin excepted, who reaches the Admin pages and the Lobby but can
    make or adopt an exercise only once bound).
- **Admin** (`/admin/…`): the pages of Admins and the super-admin, laid out as Review Robin's
  Admin and reached, as it is, from the account menu's *Admin* (which opens
  *Accounts Management*), not the switcher. Every page has *← Back*, the
  *Admin* heading and one tab strip (`admin/_tabs.html`): *Exercises
  Diagnostics*, *Accounts Management*, *System Status*. *Back* returns to the
  page *Admin* was opened from (`return_to`, which every tab and redirect
  carries): a page path alone, never a query, fragment or dot segment, and an
  Apply Desk page; else *Back to Operator Lobby*.
  - **Exercises Diagnostics** and **System Status** are scaffolds: static
    copy and layout, no data wired but the Owners. Exercises Diagnostics lists
    the ordinary exercises and the samples (columns *Exercise*, *Exercise code*, *Owners*,
    *Opens*, *Applications close*, *Timezone*, *State*), with *Manage*, and
    *Outbox* and *Audit log*, disabled with a title saying each is not built
    yet. *Owners* is every current Owner on record, comma-separated
    (`operators.owner_labels`), each named as pages name a person; *—* where
    there is none, as before the local seed has run.
  - ***Manage*** is a plain link to the exercise's Home where the viewer
    owns or operates it. Where they hold no role it is a post
    (`/admin/exercises/<id>/manage`) that asks first, saying they will become
    an Owner, adopts the exercise (`operators.adopt`) and opens Home. A refusal
    redirects back with a status line chosen by key (`said`): `not_loaded` for
    an exercise with no database row (a sample not yet seeded: load the samples
    with `python -m applydesk.seed`), `not_admin` for a viewer who cannot adopt
    (not an Admin or super-admin, or with no person row), `changed` for a lost
    race. A localhost run needs the seed for anyone to reach the samples, the
    super-admin included.
- **Admin → Accounts Management** (`/admin/operators`): who may operate, and
  who is an Admin. Admins and the super-admin admit and revoke operators; only
  whoever may make Admins (the super-admin, or any Admin when no super-admin is
  configured) promotes and demotes. Only
  someone on the operator list may make an exercise, be added as an
  exercise's operator or take its ownership. The page has:
  - Side by side, an *Add an operator* card and an *Accounts Overview* card
    (counts: operators, *not yet signed in* by `first_signed_in_at`, revoked).
  - *Add an operator*: one *Name or email* box, as Review Robin's *Invite by
    email*, with *Cancel* and *Add* on the row below and no *Search* button
    or results table. From 2 characters it offers matches as one types
    (`/admin/operators/suggest`, JSON, never cached): at most 20 of each
    kind, people on record first (*On record*), then the directory
    (*Directory*; Graph on the super-admin's delegated token, the fake
    directory on a local run). People already on the list are left out
    before the limit, and so are their directory entries, so they cannot
    crowd the offers out; a directory person already on record by object ID,
    or by a pending address, is not offered twice. Each offer's label,
    "Name <address>", is unique: repeats are numbered, because the box finds
    a pick by its label. When the directory does not answer, the box says so
    and offers people on record only.
  - *Add* is live only for a pick and posts the pick, never the typed text;
    *Cancel* clears the box. A post with no pick is refused with a status
    line saying to pick someone from the suggestions (`said=pick`).
  - *Admit* on a directory pick looks the account up again by address,
    matches its object ID and stores it bound in the super-admin's tenant;
    nothing about the person is taken from the form. A sign-in naming no
    tenant refuses it.
  - *Workspace users*: everyone on record, as Review Robin's table. Above it,
    two panes: the title and *Show:* chips on the left; *Exercise role* and a
    *Search:* box (email or name), with *Clear* (when a role or search is
    set) and *Search*, on the right. Seven columns: a checkbox, *Email*,
    *Name*, *Unit*, *First sign-in*, *Operator*, *Admin*. Empty, the table
    says nothing matches.
  - **Chips**, each with its count; every person is under exactly one, the
    first that applies: *Admins* (Admins, and the super-admin's own row), *Operators* (on the list
    and not revoked), *No role* (neither, but ever admitted, ever granted an
    exercise, or ever the actor of an audit event), *Unused* (none of that,
    an application is not history, so an applicant with none of the
    above is here).
    *Operators* and *Admins* are on by default. A chip is a checkbox label
    that submits the filter form without script. Counts take the role and
    the search but not the chips.
  - **`show`** is the chips on: absent altogether means the defaults; present
    but empty means none; an unknown value is ignored.
  - **Exercise role**: *Any*, *Owner of an exercise*, *Operator of an
    exercise* (a current grant, the Owner included), *No exercise* (no
    current grant).
  - *First sign-in* is `first_signed_in_at`, the date of the person's first
    sign-in (a directory pick is bound without one); else *Not yet signed
    in*. *Unit* shows the workspace's top line as a default pill for an
    operator, else blank. *Admin* shows *Super-admin* for a super-admin's row,
    *Admin* for an Admin, else *no*.
  - The signed-in viewer's own row is marked *(self)* in place of its
    checkbox and is never tickable. With no person row they are a row of
    their own, first, shown under *Admins* when it matches the role (*Any* or
    *No exercise*) and the search. Their *Operator* reads *yes*, listed or
    not, titled *The super-admin may operate, as every Admin may*, and their
    *Unit* the workspace default.
  - **The bulk bar**: *Admit* and *Revoke* act on every ticked row, live once
    one is ticked; *Revoke* asks first. *Promote to Admin* and *Demote from
    Admin* sit beside them, shown only to whoever may make Admins; *Demote
    from Admin* asks first. The header box ticks every row shown.
    The post (`/admin/operators/bulk`) runs each person once, in ID order,
    through `allowlist.BULK_ACTIONS` (`operators.admit`, `revoke`, `promote`,
    `demote`), audited there, in one transaction. A refusal (already so, not
    listed, gone; for *Revoke*, an Admin; for *Promote*, someone not yet signed
    in or a super-admin's row; for *Demote*, a non-Admin, the last Admin or a
    super-admin's row) or the viewer's own row skips that person, not the
    batch. The guards are `applydesk/spec/permissions.md` §8. Nothing ticked is refused
    (`said=none_ticked`); more than 1,000 is refused (`said=too_many`). The
    redirect keeps the chips, role and search.
  - A change that loses a race with another (a unique clash, or a busy
    SQLite file on a local run) says the list changed and to check it.
  - The status line is chosen by a key (`said`), never by text from the URL.
    The one exception is the bulk line, built from the redirect's `done`
    (`admit`, `revoke`, `promote` or `demote`) and its counts, changed and skipped, which are read
    as bounded whole numbers: it says what changed and how many were skipped,
    and no other text from the URL reaches the page.
- **An exercise's *Owners and operators* card**, on Home under Details: each
  current operator, Owners first and marked *Owner*, the rest *Operator*; a
  pending person carries *Not yet signed in*, and the viewer's own row *(you)*.
  - **Owner rules.** Every exercise has one or more Owners, each one of its
    operators. Whoever makes an exercise is its Owner; an Admin or the
    super-admin who adopts it becomes another. Other operators do
    everything on the exercise; only an Owner adds and removes operators,
    makes Owners and transfers ownership. The moves, and the rule that an
    exercise keeps an Owner who can act, are
    `applydesk/spec/permissions.md` §3 and §8. A person made an Owner or
    transferred to must be on the operator list. Adding someone already an
    operator, or yourself, is refused; re-adding a removed operator restores
    them.
  - **For an Owner**: *Add operator* opens a
    *Name or email, on the operator list* search over the operator list only
    (no directory; current operators left out), each hit with *Add*. On
    another operator's row: *Make Owner* (Secondary), *Transfer ownership*
    (Outline-amber) and *Remove* (Destructive); on another Owner's: *Make
    operator* (Secondary); on their own: *Step down to operator*
    (Secondary), or, while they are the only Owner who can act, a note saying
    to make another Owner or transfer first. *Transfer ownership*, *Remove*
    and *Leave* ask first.
  - **For an operator** the card is read-only except *Leave* (Destructive),
    on their own row, which returns them to the Lobby; it says only Owners
    change who.
  - Each move posts to its own route under
    `/operator/exercises/{id}/operators/{person_id}/` (`owner`, `make-owner`,
    `demote`, `step-down`, `leave`, `remove`;
    `routes_operator.operators_*`), `owner` being *Transfer ownership*. The
    result is a status line chosen by key (`routes_operator.OPS_SAID`), never
    text from the URL. An archived exercise refuses every move.
  - An exercise with no row in the database (a sample not yet seeded) shows no
    operators and says so; a localhost run loads it with
    `python -m applydesk.seed`.
  - A change that loses a race with another is refused and says to look
    again.

## One look across pages

Apply Desk's pages share Review Robin's look and vocabulary (`spec/ui_elements.md`).

- **One state-to-tone map** (`applydesk/tones.py`) colors every chip, so no
  page names a state in another color, Home's outcome rows included. Amber: Draft, Not ready, Withdrawn,
  Pending. Info: Published, Open, Ready, Sent. Green: Completed, Results in,
  Submitted, Entered, Released, Done. Red: Overdue, Closed. Grey: Archived,
  Detached, Next, Not entered. Chips are uppercase, an outline marking a
  clickable one; a panel's name chip is no exception. A field's type summary
  is muted text, not a chip.
- **A gate** is named `Gate N · label` wherever it is listed or chosen (Home's
  timeline rows too), an outcome `Outcome N · label`.
- **Controls.** *Required* and *Released* are checkboxes, not pills. An add
  button reads `+Noun` in a builder (*+Panel*, *+Gate*, *+Question*),
  *Add new* in a table's toolbar. Creating a panel is *+Panel*, Secondary,
  wherever it is made. CSV files are *Upload CSV* and *Download CSV*, both
  Secondary. A cross-page link reads `Verb on Page →` (*Open Gate 2 →*,
  *Review Robin card →*, *Pairs (n) →*); `↓` jumps within a page.
- **No citations on a page.** A page's copy carries no ruling, segment, AD
  or gate citation. A control not built yet is disabled and its title says
  *… is not built yet* (*Applying is not built yet*), never *comes with AD4*.
- **Buttons** take Review Robin's roles and hovers (`spec/ui_elements.md` §6):
  each of Primary, Secondary, Outline-amber and Destructive has its own hover,
  none while disabled. A page context never reshapes `.btn`. A small button is
  `.btn-short` (`spec/ui_elements.md`); the two exceptions are a field and its
  button side by side, which meet at 40px, and Process's one-glyph source
  buttons (▲ ▼ + × All), which keep `.btn`'s 38px and trim only their sides.
- **Counts** read `Showing N of M <noun>` (*dossiers*, *pairs*), as Review
  Robin's, a page's range as `Showing a–b of M pairs`.
- **An intro** (`pc-intro`, muted) sits under the h1 of every operator section
  page and says what the page is.
- **Empty states.** An operator page with nothing to show draws one block
  (`_empty.html`): a title, one line saying why and a link to the page that
  fixes it. A control over nothing is disabled with the reason in its title,
  and keeps its place, so the page does not reflow when data arrives.
- **Locks.** One pattern on Details, Dossiers and the gate page: *Discard
  changes*, then *Lock*, with one unsaved note. Where a whole page or card is locked the reason shows as a
  line; one blocked control is disabled with the reason in its title.
- **The unsaved marker** is one class, `.fb-unsaved` (amber, 13px, weight 600),
  on every page: its text is *Unsaved changes*, or Dossiers' change count, or
  Panels' per-panel *not saved yet* notes.
- **Tables** (Dossiers, Evaluations' pairs, the lobby, Panels) take Review
  Robin's (`spec/ui_elements.md` §7): row borders in `--border-default`, a muted
  header band with `↕` badges, a muted row hover (a table of filled cells, as
  Dossiers', hovers its cells); no sticky header. A click on a header cycles
  its column up, down and off, and shift-click adds it to a cascade (`1↑`,
  `2↓`), as Review Robin's.
- **Dates** are worded by `applydesk/clock.py`, and no page words one itself.
  Applicant pages and a dated context keep friendly dates: `short` (*4 Dec*)
  and `span`, a range with its year said once (*1–30 Sep 2026*, *1 Sep – 4 Dec
  2026*). Operator pages print a stored moment as `YYYY-MM-DD HH:MM` in the
  exercise's own timezone (`stamp`). Today is `clock.today`'s: the sample's
  fixed day while the sample's stages stand, since they are dated around it,
  and the wall clock's in the exercise's timezone once stages are stored.

## The lobbies and the applicant's application

- **The Operator Lobby** (`applydesk/templates/applydesk/operator/exercises.html`,
  `routes_operator.exercises`), laid out as Review Robin's Sessions lobby: two
  cards over one table of the exercises the viewer owns or operates (the
  super-admin and Admins included; the others are on Exercises Diagnostics),
  newest *Created* first by default (`sample_data.newest_first`). One not
  recorded goes last. The rows come from the database: an archived or deleted
  exercise is not in the Lobby.
  - **Cards.** *Exercises*: a chip for the total, then one per status in
    `locks.STATUS_ORDER` (`locks.status_counts`, empty ones kept, so the chips
    add up to the total), then *Show exercises tagged with:* the tags shown
    (`sample_data.all_tags`), *OR* and *Clear*. *Filter*: a box (name, code
    or tag), *Clear*, *New exercise* (Primary; opens the name form, "Ordinary exercises")
    and *Go to Archive* (the Archive, below).
  - **Columns**, in order: *Exercise* (its name, linking Home), *Exercise
    code* (*Not set* when none; the public ID shows only in the link), *Your
    role*, *Created*, *Timezone*, *Status*, *Tags*, and a tick box. Every
    column but *Tags* and the tick sorts; *Created* carries the descending
    arrow by default.
    - *Created* is `YYYY-MM-DD HH:MM` in the exercise's own timezone
      (`sample_data.created_label`, `clock.stamp`); the stamp holds its UTC
      offset, so it follows a timezone Details sets.
    - *Timezone* is a chip of the offset now (`GMT+8`, `GMT+5:30`, `GMT`),
      the zone's name as its title (`sample_data.utc_offset`).
    - *Status* is the state chip (`locks.exercise_status`) over *Stage N of
      M*, then ` · <stage name>` when the stage has one
      (`workflow.stage_position`); omitted when the exercise has no stages. N
      is the number of the stage holding the next step, or the last once
      every step is done; M counts the exercise's stages.
    - *Your role* is an *Owner* or *Operator* chip for the viewer on that
      exercise (`gate.owns`); it sorts Owner first, then Operator (`role`,
      `applydesk/lobby.py`). The exercise's Owners are named on Home's
      *Owners and operators* card.
    - *Tags* are the exercise's stored tags (*No tags* when none).
  - **The tick panel**, Review Robin's. Ticked rows are highlighted and one
    panel sits under the most recently ticked row still ticked; unticking
    every row closes it. The header box ticks every row shown and shows a dash
    when only some are ticked.
    - **One row ticked**: *Name*, *Exercise code* and *Tags* (filled from the
      row), *Yes, delete*, *Archive after purging* with Applications,
      Dossiers and Audit log (disabled: purging waits for AD2D); buttons
      *Save*, *Cancel*, *Duplicate*, *Duplicate settings only*, *Purge and
      archive* (Outline-amber), *Delete* (Destructive). There is no deadline field: an exercise's dates
      are its stages', set on Process.
    - **Several**: *Tags*, the same delete and purge controls; buttons
      *Cancel*, *Unselect others*, *Unselect all*, *All tags to all*, *Remove
      from all*, *Purge and archive all*, *Delete all*.
    - ***Cancel*** unticks the row the panel sits under, so the panel moves
      back to the row ticked before it (the tick order is kept). *Unselect
      others* keeps only that row ticked; *Unselect all* unticks every row.
  - **Sorting, tags and the filter** ride the query string (`sort`, `dir`,
    `tag`, `any`, `q`; `applydesk/lobby.py`), so a reload or a shared link
    keeps them. A header sorts by its column, ascending (*Created*: newest
    first), and again the other way; a row with no value in the sorted column goes last either way, ties keeping
    *Created*, newest first. Each `tag` chip narrows to exercises carrying
    every chosen tag; *OR* (`any=1`) shows those carrying any. The filter
    keeps exercises whose name, code or a tag contains the text, ignoring
    case. The filter's *Clear* drops the text, the chips' *Clear* every
    chosen tag, and a chip pressed again drops its tag.
    An unknown value is ignored, never echoed. A panel post returns to the
    Lobby with the query kept.
  - **The panel posts** to `/operator/exercises/panel` (`routes_operator.exercises_panel`):
    a same-site form post of at most `web.MAX_BODY`; it ends on the
    Lobby with a status line chosen by key (`routes_operator.SAID`). Every
    ticked exercise must be one the viewer operates, and at most 500
    (`routes_operator.MOST_TICKED`) are taken.
    - *Save* (one row): name, code and tags, revision-guarded: the Lobby
      names the revision each row was drawn at, and a save over a newer one
      is refused and saves nothing. The name is 1–200 characters and the code
      at most 40, held by no other live exercise, ignoring case; a blank
      code stores none. A published exercise's code is fixed here as on
      Details (G2): the panel shows it read-only and the server refuses a
      change, while its name and tags still save.
    - *All tags to all* and *Remove from all* (several rows): the typed tags
      added to, or taken from, each ticked exercise; an exercise that would
      pass 20 tags refuses the lot.
    - *Duplicate settings only*: a new Draft exercise with the source's
      settings and tags, named *Copy of <name>* with no code, its Owner the
      viewer. It is made as *New exercise* makes one (`exercises.make`: the
      same refusals and the same cap, "Ordinary exercises"), and lands on its
      Home. *Duplicate*, which would copy
      the whole setup, stays disabled: it waits for stages, forms and
      applications to be stored (AD2C–AD2F).
    - *Purge and archive* **archives only**: purging waits for AD2D's stored
      applications, so the Archive after purging boxes stay disabled and the
      button's title says so.
    - *Delete* asks first (*Yes, delete* must be ticked, else *Not
      deleted*). The exercise leaves every page, and its row, grants and
      audit trail stay (nothing is hard-deleted).
    - *Archive*, *Restore* and *Delete* are Owner-only
      (`applydesk/spec/permissions.md` §3): the server refuses an operator,
      saying so, and does nothing for any of a ticked set when one is refused.
      The panel disables *Purge and archive* and *Delete* (and their *all*
      forms) while a ticked row is one the viewer only operates, and a note
      names those exercises; the server's refusal stands whatever the page
      shows.
    - Each change is audited (`applydesk/spec/architecture.md` "Audit").
  - **The Archive** (`/operator/exercises/archived`,
    `routes_operator.exercises_archived`): the archived exercises the viewer
    operates, newest archived first, as the Lobby's table, with *Your role* and an *Archived* column (the
    moment, `clock.stamp`, the fixed sort) and a *Restore* button on each row, filtered by
    tag and text as the Lobby. *Restore* posts to
    `/operator/exercises/archived/restore`, an Owner's: it returns the
    exercise to the Lobby, unless another live exercise has taken its code
    since, when it is refused saying so and the exercise stays archived. An
    archived exercise frees its code. With none archived the page says an
    Owner archives one from the Lobby's panel.
  - **An archived exercise is read-only** until restored (the author,
    2026-11-22), as Review Robin's archived sessions are. Its pages open, and
    Home says it is archived, linking to the Archive, with Details' *Unlock*
    disabled. Every post to its pages is refused with a 409 by the operator
    router's gate (`gate.require_exercise_operator`). The Lobby panel's
    *Save* and tag actions refuse it too. Review Robin also offers *Delete*
    on its archived page; Apply Desk deletes only from the Lobby, so an
    archived exercise is restored before it is deleted.
  - **Still inert**, each disabled with a "… is not built yet" title or one
    saying what it waits for: *Duplicate* and the purge boxes (above).
    *Cancel*, *Unselect others* and *Unselect all* only untick rows in the
    browser. *New exercise*, the tick boxes and the panel's opening work.
- **Ordinary exercises.** Every live `exercise` row that is not a sample
  (`sample_data.is_sample`, `SAMPLE_IDS`) is an ordinary exercise, however it
  was made. An operator sets one up end to end: every page of it saves to
  the database, as any exercise's (Details; "The Process page"; "The Panels
  page"; "The Form page"; "The Emails page"). A sample stays a fixed fixture, and `sample_data.sample` reads one with no
  database read.
  - **Making.** *New exercise* opens a form asking for a name (1–200
    characters); *Create* makes a blank Draft and lands on its Home.
    *Duplicate settings only* makes one too. Both go through
    `exercises.make`, which makes the row and its Owner, the viewer, in one
    transaction. A refusal returns to the Lobby saying why, by key
    (`exercises.MAKE_REFUSALS`): `name_needed`, `name_long`, `not_listed` (the
    viewer is not on the operator list, or not bindable: nothing is made) and
    `full`. The super-admin needs no list membership, only a person row, and
    is the Owner. The Lobby's status line shows only its own messages: the
    redirect carries a key (`routes_operator.SAID`), never the text, so a link
    cannot put words on the page.
  - **The cap.** A person may hold at most 50 live exercises of their making
    (`exercises.MOST_MADE`): archived and deleted ones, and the samples, do
    not count. The allowlist is checked before the cap. The count is taken
    under `FOR NO KEY UPDATE` on the person's row, so two makes at once cannot
    both pass.
  - **What one reads.** `exercises.from_row` builds it: a blank Draft named
    by its row (*Untitled exercise* when the name is NULL), its *Created* the
    row's `created_at`, no code, no tags, one stage holding the form, a blank
    form and blank emails (every template *Owed*), no applications, so
    Dossiers and Evaluations show their empty states. `sample_data.exercise`
    and `exercises()` return a sample, else an ordinary exercise's row;
    `exercises()` lists the ordinary ones newest first, then the samples.
    Stored settings overlay it as they do a sample's. Its first change marks
    its revision recorded; it is not recorded as a sample.
  - **Who sees one.** The grant gate decides ("The Lobbies" above;
    `applydesk/spec/permissions.md` §3), so a co-operator sees it.   - **Deleting.** *Delete* on the Lobby's panel (above) is the only way, and
    an Owner's alone: the row and its grants stay, its code is free again.
    There is no second route and no exception for the person who made it.
  - **A save** is a same-site JSON post (403 for another site, 415 for
    non-JSON, 400 for malformed JSON) of at most `web.MAX_BODY` (256 KiB; 413
    past it). The page says *Saved.* or the reason it was refused, and a
    saved page's *Unsaved changes* marker clears. A page edited while its
    save was on the way stays unsaved. Shapes are checked, not the plan: what
    a page flags itself (dates out of order, weights not adding up) is kept as
    left and flagged again; only what has no shape to be kept in is refused.
    The Setup pages' save script is `_page_save_js.html`.
  - **Details** (*Lock*, to `…/details`) saves to the database for every
    exercise ("Details").
  - **Form** (to `…/form`, `applydeskFormSnapshot`): at most 200 cards, a
    title of at most 200 characters, a description of at most 4,000; each
    card of a known kind, a field of a type offered, its text within its
    length, its toggles true or false, and a question choosing from a panel
    the exercise has (blank reads *Institution-wide*); a refusal names the
    card's number. A new form is empty (one blank question), not the
    sample's. `sample_data.form_cards` and `form_heading` read it back.
  - **Process**, **Panels** and **Emails** save to the database for every
    exercise, a panel made with *+New panel…* on Form or Process with the
    save that names it; their checks are in "The Process page", "The Panels
    page" and "The Emails page".
  - **Reload.** A save that keys something anew (a panel) reloads the page
    so it holds the keys kept, and says it saved once back.
- **The User Lobby** (`applydesk/templates/applydesk/me/home.html`), three
  cards: *My applications*, each of the applicant's own with its state,
  linking its page, a draft included; *Open to me*, each Published or
  Closed exercise, saying *Applications open*, *Applications closed* or
  *Closed: its released results stay here*, and *You are invited* for an
  invitation-only one; *Dossiers I am asked to evaluate*, each linking its
  dossier, *An application* in place of the title in a blind exercise. An
  empty card says so (*No applications yet.*, *No exercise is open to you
  yet.*, *None to evaluate yet.*).
- **The applicant's application**
  (`applydesk/templates/applydesk/me/application.html`): the crumb *User
  Lobby / exercise / Your application*; the title with its state; *Shown to
  evaluators* and *Not shown to evaluators*, each a card of the Form's
  questions with the answers (`extract.form_answers`) as one fact list, *—*
  where there is none and *None* for a card with no question; *Your
  results*, a card likewise, on the applicant's own application only, once an outcome is
  released to applicants. Then a draft's *Save draft* and *Submit*
  (disabled until AD4), or *Applications closed on <date>* once the form
  has closed; a submitted application's *Withdraw* (Outline-amber, disabled
  until AD4) until a gate holding its dossier completes, then *You can no
  longer withdraw: your application has gone to <gate>*
  (`workflow.withdrawal_closed_by`).

## The Form page

The application form builder on the Form tab,
`/operator/exercises/<id>/form`. Every move works in the browser, and *Save*
keeps the form in the database for every exercise ("Saving
Form"). Until it is first saved, a sample exercise shows its sample form. A
blank exercise shows the form's own card and one empty String card, open.

- **Layout.** The form's own *Form title* and *Description* at the top: it
  cannot be deleted or moved, collapses like a card, and its title is
  larger than a card's. Then the cards, and the Outline beside them, kept
  in view: in the right third on a wide screen, a narrower fixed column on
  a middle one, below the cards on a phone.
- **Cards.** A question or text card (*field*), a *section* (a title) or a
  *page break*. A field's type, chosen in a menu at the card's top right,
  is one of:

  | Type | Settings | Collapsed summary |
  |---|---|---|
  | String | Min length, Max length | `String · 1 to 120 characters` |
  | Integer, Decimal | Min, Max, Step | `Integer · 1 to 6, step 1` |
  | List | Options (comma-separated), *Choose one* / *Choose any* | `List · choose one · A, B, C` |
  | Photo | Ratio width : height | `Photo · 4:5, kept 480 × 600` |
  | Select people | Min and Max people, *Chosen from* | `Select people · 1 to 3 people · Panel A` |
  | Title and Description | *Title* and *Description* in place of *Question* and *Help text*; nothing else | `Title and Description · display only` |

  Every type but Title and Description also has *Required*, a checkbox
  (ruling 64). An empty bound
  is left out of the summary (`Integer · up to 6`); both bounds equal read
  `exactly N`; a list with no options reads `no options yet`; a photo with
  no valid ratio reads `Photo · ratio not set`.
  A photo is kept as a JPEG 600 px on its longer side, the other side by
  the ratio, rounded half up (4:5 is 480 × 600; 1:1 is 600 × 600). *Chosen
  from* is a menu of *Institution-wide*, then the exercise's panels by name
  (`sample_data.Panel`), then *+New panel…*. That choice opens a box under
  the row: *Panel name* and *Members*, a token box as Residential's people
  boxes are (names or emails, comma-separated, each found in the directory
  a pill with ×; one not found stays in the box with the reason), then
  *+Panel* (Secondary, as on Panels) and *Cancel*. A panel created joins every *Chosen from*
  menu on the page and Preview's lookup, and is selected; it is stored, as a
  panel of the exercise, with the page's *Save* ("The Panels page"), under
  the exercise's lock, or not at all. *Edit on Panels →* beside the menu links to the chosen panel
  on Panels, hidden for *Institution-wide* and for a panel made here and not
  yet saved. A
  panel the exercise lacks reads as *Institution-wide* on the card, in its
  summary and in Preview. Help text and descriptions grow to fit what is typed, with no
  resize handle, as does a long answer's box in Preview. Changing the type
  keeps the question, help text, *Required* and visibility, and empties the
  new type's settings: a photo's ratio starts at 4:5, a list at *Choose
  one* and Select people at *Institution-wide*.
- **Visibility** is per card: *Shown to evaluators* or *Not shown*; a new
  card is *Not shown*, the side that hides.
  *Ruled, not built (ruling 79, `applydesk/guide/todo_master.md`; segment
  AD2V):* who sees a dossier item is set where people read: each gate ×
  panel for its evaluators during the gate's window, each outcome for
  candidates and past evaluators from its release (continuing, adding to or
  resetting the last). A candidate always sees their own form; a new item
  starts hidden; each field keeps a ceiling; operators see every item. The
  per-card and per-section *Shown* / *Not shown* go.
- **Collapsed**, a card shows its question and help text (a text card's
  title and description), the summary of its settings, and chips: *Required*
  or *Optional* (a text card has none) and its visibility. Expanded, it
  shows its fields and its buttons. Cards load collapsed, the form's own
  card too; a form with one card opens both. Several can be open at once.
  No card shows a number. A card with no question reads *Untitled
  question* (*Untitled text*, *Untitled section*).
- **Buttons** along each card's foot, flush right, in this order:
  *Replicate* (a field card only), *+Question* (an empty String card),
  *+Section*, *+Page break*, *Delete*. Each insert lands right after the
  card, and a new card opens. *Delete* has no confirmation and is disabled,
  with a reason in its title, on the form's last question or text card.
  Sections and page breaks never count toward the last card. A page break
  has *Remove* only.
- **Reordering** by dragging a card's handle, or by focusing the handle and
  pressing ↑ or ↓, which announces the new position. Sections and page
  breaks move too; the form's own card stays first.
- **The Outline** lists sections, cards and page breaks in order, each
  card's visibility as a chip, and the counts of pages, sections, questions
  (a text card is no question) and required ones; a click goes to the card
  (leaving Preview if it is showing). Nothing in it is numbered. It follows
  every change.
- **Keeping an edit** (ruling 23). One *Save*, in the Outline, live on every
  exercise ("Saving Form"); an *Unsaved changes* marker beside it once anything is edited
  (a move, a toggle, an added, replicated or removed card; opening a card or
  the preview is no edit), and a warning on leaving the page with it showing.
- **Preview**, at the foot of the Outline with *Save* beside it, shows the form in place of the cards, as an applicant sees it,
  page by page, built from the cards on screen; the button reads *Back to
  edit* meanwhile. *Open the preview in a new tab →*, under them, shows the
  same at `/operator/exercises/<id>/form/preview`, with *Submit* disabled.
  The tab reads the builder that opened it, so a reload picks up later
  edits; opened on its own, or once the Form page has gone to another
  exercise, it shows the sample form and says so. Both are drawn by one
  renderer. A string with a maximum of 200 characters or fewer previews as
  one line, longer or unbounded as a box; a number as a field with its
  bounds; a list as radio buttons (*Choose one*) or tick boxes; a photo as
  a frame at its ratio; "Evaluators see your answer." appears under a shown
  question. Select people previews as a box of pills, after Residential's
  Staff box: each comma-separated name or email found in its pool becomes a
  pill, one not found (or matching more than one person) stays in the box
  with the reason, a repeat is declined, and the box takes no more at the
  maximum, naming what it dropped. The pools are sample rosters;
  looking people up in Entra ID through Graph comes with the applicant's
  form (AD4). Nothing typed in a preview is kept.
- **Read-only once its stage is published** (`locks.form_lock`). Every control
  but each card's toggle is disabled with the reason in its title, a line says
  so, and the cards still open and shut to be read; the Outline and Preview
  still work.
- **Conditional questions** (branching) are not built: deferred, see
  `applydesk/guide/todo_master.md`.
- **Saving Form** (`applydesk/form_store.py`; the post is
  `routes_operator.exercise_form_save`, a same-site JSON post of at most
  `web.MAX_BODY`). *Save* replaces the form, its title, description and
  cards, in one transaction under the exercise's lock, guarded by
  `exercise.form_revision` (0 until Form is first saved). The post names the
  revision the page opened at, and a save returns the new one. A sample's
  form is recorded at its first save. Nothing is deleted: a card a save
  drops is retired.
  - **Refused**, each a 400 naming why, bar the stale one:
    - a post with no revision (malformed);
    - an archived exercise;
    - a published form (`locks.form_lock`);
    - a revision older than the stored one, a 409 (*Form was saved since this
      page opened. Reload to see it.*); a concurrent first save losing the race
      is a 409 likewise;
    - a card or field malformed, of an unknown kind or type, or past its
      length caps, more than 200 cards, or a *Chosen from* naming a panel the
      exercise lacks;
    - a save that drops, or makes another type, a question a rule on Process
      reads (a choose-one *List*) or a nominated source reads (*Select
      people*). Both are read under the lock, so a Process save landing first
      is seen.
  - **Keys.** Each card (a section and a page break too, so the order is one
    list) has a `key`, `q<n>`, minted by the server past every key the
    exercise has held, retired ones and the sample's included, and never
    reused. A card keeps its key through a rename and a move; a new card, a
    replicated card and a page's placeholder are given a fresh one. A removed
    question keeps its key, so a rule naming it is refused, not re-pointed. A
    sample's cards take `q1`… in order at the first save.
  - **Reload.** A save that keys a new card, or a panel made with *+New
    panel…* ("The Panels page"), answers that the page must reload to hold its
    keys, and edits made while it was on its way cannot be saved before then
    ("strict").
  - **Audit.** `exercise.form_saved` (`applydesk/spec/architecture.md`).

## Exercise Home

Home, `/operator/exercises/<id>`, is two columns: the **Timeline** card
(two-thirds) and the **Details** card (one-third), one column from 899px down,
Details below. The status row (`workflow.status_row`) opens with the exercise's status,
derived from its stages ("Stage status"), and carries *Applications: N
submitted · M drafts*. The stage under way's marker reads *Now · until
<end>* ("The timeline"); on Home each gate's row in its operator part links
the gate's page. A line under the timeline (`timeline.next_step`) shows only
for a draft (*A draft: the timeline is what participants will see once it is
published.*) or when no stage is under way. Home has no Publish card: publishing is per stage,
on Process, and the timeline's operator part says what blocks each stage.
Cards side by
side share a height only when within a fifth of the taller; a short card
beside a much taller one keeps its own.

### The timeline

Drawn from Process's stages by `applydesk/timeline.py` (the participant-safe
adapter) through the partial `applydesk/templates/applydesk/_timeline.html`,
which Home and the applicant's exercise page (`/me/exercises/<id>`) both
include.

- **Stage**: name, dates and a state. On Home the chip is the stage's status
  (Draft, Published, Overdue, Completed: "Stage status"); the applicant's page
  says where it stands: *Done* when its last date has passed
  (*Closed* for the stage holding the form), *Now* when today falls within it,
  *Next* otherwise (the calendar's, apart from the stage's status); a stage with no (or impossible) dates is *Next* and reads
  *Dates not set*. Today is `clock.today`'s (the sample's fixed day until stages are stored), marked on the current
  stage at its share of that stage's days. The marker reads *Now · until
  <the stage's last date>* (*Now* when it has none); between stages the
  line under the timeline says where today falls.
- **Items**: the form as *Applicants* (items name their audience, never
  *you*), its close as a *Milestone*, each gate as a
  *Step* by name (*A step.* unnamed), each outcome by name with *released
  <date>* or *expected <the exercise's expected outcome>*. In the stage
  under way, its first outcome due replaces its place in the list as a
  *Next:* item, in the outcome's tint. Outcome values
  appear only once released to applicants. Nothing operator-only (panels,
  rules, pairs, modes) is in this shape.
- **Layouts**: *Horizontal*, a bar of equal-width segments each heading its
  stage's column, the current one filled to today; *Vertical*, a date gutter
  and a spine through each stage's node, items beside it. The switch is per
  viewer, operator or applicant, in `localStorage` `applydesk-timeline`
  (`h` / `v`), one choice for every exercise. With no stored choice it starts
  Vertical on a phone (max-width 639px) or past four stages, Horizontal
  otherwise; storage blocked, that rule applies.
- **The operator's part** (`applydesk/home_ops.py`), only where the page
  passes `ops`, which is Home alone. Below a rule (Horizontal, aligned across
  stages, under one visible *Operator only* label: every stage keeps its
  label for screen readers, only the first is seen, and each stage's rows
  share one grid row), to the right of each stage (Vertical), under the items on a phone,
  each stage leads with its status chip (`locks.stage_rows`):
  - a Draft lists *Blocking publication*, each one `locks.publish_problems`
    names, or says *Ready to publish.* The first stage's missing setup is
    linked to where each is set (Home's details, Process, Form), in place of
    the problem that repeats it;
  - an Overdue stage says *Waiting on:* what is outstanding;
  - each row links to Process.

  Then the form's state with submitted and draft counts; each gate's state, mode,
  evaluators, pairs and progress, linking to its Evaluations gate page (no
  link for a Draft); each outcome's Dossiers tally and *Released* /
  *Pending*, linking to Dossiers. It never appears on the applicant's page.
- **The applicant's page** draws the same partial beside *Apply*, without the
  operator's part or the Next step line, for a Published or Closed exercise.
  *Apply* links each of the applicant's own applications there (*Your
  application*), as the User Lobby's *My applications* lists them all
  (`sample_data.my_applications`, which reads the stored applications the sample applicant owns).
  Under each, every outcome released to applicants gives *Your result*
  with the applicant's own value and when (`stages.released_results`; the
  application page lists them as *Your results*); AD7 sends them. `/me`
  shows Published and Closed exercises (ruling 41): a Closed one stays,
  read-only, its *Apply* saying it is closed; Draft and Archived do not,
  and their application and dossier pages answer 404 (author, 2026-11-18).
  *Your results* is the applicant's own: another application's page shows none.
  A submitted application may be withdrawn (*Withdraw*, Outline-amber, with a
  confirm, AD4) until a gate holding its dossier completes (ruling 49); then the
  page names the
  gate it has gone to (`workflow.closed_by`, rulings 45, 49).
  Closing and archiving themselves are not built (AD3).
  A stage left unticked in Process's *Shown to applicants* is not on it
  (`Stage.shown`, ruling 46); the operator's Home shows every stage.

### The form's state

The application form is `draft`, `open` or `closed`, kept on the stage that
holds it ("Saving Process"), and moves only forward. Home's next step carries
the move as a Primary button, *Open form* then *Close form*
(`workflow.form_action`, posting to `…/form/move`,
`routes_operator.form_move`): *Open form* is disabled, with its reason, while
the exercise is a draft (published as its stages are, `locks.exercise_status`),
and nothing is offered once the form is closed or when no stage holds one.
Reopening a closed form is not built.
- A move is a same-site form post, from the state before it only, and is
  refused, with the reason in a line on Home, for a form that has moved
  meanwhile, an exercise with no form or an archived one. A timeline Process
  never saved is recorded first, as its save would. Each move stamps when it
  happened and is audited (`exercise.form_opened`, `exercise.form_closed`).
- `workflow.form_state` reads the stored state once Process has saved the
  exercise, else the exercise's: Home's operator part, the applicant's exercise
  page, a stage's completion (`locks`) and `workflow.steps` follow it.

### Details

Name, Exercise code, Description (`Exercise.summary`), Help contact,
Timezone and Blind review, locked until *Unlock*. A Help
contact or Timezone left unset reads the operator settings' default
(`DEFAULT_HELP_CONTACT`, `DEFAULT_TIMEZONE`) followed by *· the default*
(`help_contact(e)` / `timezone(e)`, template globals in `applydesk/web.py`).
Unlocked, each is a field with a line saying where it is used.

- *Discard changes* then *Lock*, as Review Robin orders them: *Lock* keeps
  the changes on the page; *Discard changes*, or Esc, restores
  the last kept values, saying *Changes discarded.* only when something
  changed. *Unsaved changes* shows, and the browser warns on leaving, from
  any change since load.
- *Lock* refuses an empty Name (at most 200 characters), an Exercise code of
  more than 40 characters or one a live exercise holds (any case), a Description of more than 2,000 characters, and a Help contact that
  is not an email address. The Timezone is chosen from `sample_data.TIMEZONES`,
  the default first. A refusal points at the field it names. The page's own code check lists
  only exercises the viewer operates; a clash with any other is the
  server's to refuse, saying *<code> is already another live exercise's
  code* and naming no exercise, and *Restore* on the Archive likewise says
  the code *is now another live exercise's code*.
- A published exercise's Exercise code is fixed, saying so; changing it
  waits for re-publishing (G2). Who may apply is not Details': the Form's
  item holds it ("The Process page").
- **Blind review** is fixed, with its reason, once the first stage holding a
  gate is published (`locks.blind_lock`).
- **The server refuses what the page locks**: a changed Exercise code on a
  published exercise, and a changed Blind review once it is fixed, are
  refused whatever the post says. A post's `eligibility` is not read.
- **Saved to the database**, for any exercise the viewer operates, sample or
  ordinary: *Lock* posts JSON to `…/details` (`routes_operator.exercise_details`;
  415 for non-JSON, 413 past `web.MAX_BODY`), and a reload or a restart
  shows the saved values. The post names the revision the page opened at;
  one older than the stored revision is refused with a 409 saying someone else
  changed the details, saves nothing, and the page keeps the unsaved values.
  An accepted save returns the new revision, which the page then names; a save
  that changes nothing leaves the revision alone. A change is audited
  `exercise.details_changed`.
- **Unset is NULL**, never the text *Not set*, which the page prints: a Help
  contact or Timezone left unset, or chosen as the default, is stored unset
  and reads the operator settings' default followed by *· the default*.
- Process shows Help contact and Timezone read-only.

## The Process page

The exercise's timeline as a stack of stage cards, on the Process tab,
`/operator/exercises/<id>/process` (rulings 13–16). Process sets up the whole
flow and every rule Dossiers applies; Form, Panels and Emails flesh out its
nodes. Every move works in the browser, and *Save* keeps the timeline in the
database for every exercise ("Saving Process"). A blank exercise shows one
open card, *Stage 1*, holding the form. The cards are drawn from
`stages.plan_of`, which reads the stored timeline once Process has saved the
exercise and the sample before then, so Process, Dossiers and the status row
agree on load. There is no Workflow card:
ruling 14's was removed (author, 2026-11-15: derivative of the other
pages, it can wait). Its steps stay as a contract, which no page draws
but the lobby's *Stage* column reads:

- `workflow.steps` is the timeline a step at a time: each stage's
  *Application form*, gates and outcomes in their set order, then *Close
  and archive*. A step carries its stage, state, dates, a line (the form's
  submitted count or *Not open yet*; a gate's progress or why it is not
  ready; the close's *Extract data first*), the action it would take
  (*Open form…* or *Close form…*, *Send…* for a gate not sent, *Release…*,
  *Close…*; none once done, and a sent gate links to Evaluations instead)
  and whether it is done. An outcome not yet released whose emails are
  owed is blocked: *Not ready: its email to applicants is not written*, or
  *its emails to applicants and evaluators are not written*.
- `workflow.next_step` is the earliest step not done;
  `workflow.current_stage` is the stage holding it, else the last stage.

- **Layout.** The cards in timeline order, the Outline beside them (as
  Form's), *Save* at its foot.
- **A stage card.** *Stage name* (an empty name reads *Stage N*, by position),
  *Starts* and *Ends*, and *Shown to applicants*. Collapsed, it shows its
  name, dates, status chip and a summary (`Form · Outcome: Shortlist`,
  `2 gates`, `No gates`). Cards load collapsed; a lone card is open. At its
  head, its status box ("Stage status"); below, its items in order: *Create dossiers*, the form,
  gates, the outcome ("Items reorder within their stage").
- **Dates are typed** (author, 2026-11-18). A stage's *Starts* and *Ends* are
  date-time inputs (`stages.StageDates`, in the exercise's time zone; a bare
  day's end is its last minute, 23:59). An empty pair is unset: stored NULL,
  printed *Dates not set*. A pair with one end alone, or ending before it
  starts, is refused at save.
  Each item carries its own, inside its stage's: the form's *Opens* and
  *Closes*, a gate's *From* and *To* (its review window), an outcome's *Due*.
  Left blank, an item runs on its stage's dates and an outcome is due at its
  end (`stages.window`; `Stage.form_when`, `Gate.when`, `Outcome.due_at`). An
  outcome is due no sooner than the gates it reads close, those of an earlier
  stage included. `stages.date_problems` words what breaks this: an item
  outside its stage, reversed, or an outcome due before its gate closes. The
  stage's end is what completes it, whatever its items' dates.
- **Ruling 15, enforced as it is edited.** One stage holds the form, anywhere;
  never the form and a gate together; one outcome at most per stage; an empty
  stage is allowed. A button that would break it is disabled with the reason in
  its title: *+Gate* on the form's stage, *+Form* on a stage with gates or
  when another holds it, *+Outcome* on a stage with one. `stages.problems`
  words the same rules and the Outline names any breach.
- **The first item comes first** (ruling 84). Until a Form or a *Create
  dossiers* is in the process, every stage offers only *+Form* and *+Create
  dossiers*: *+Gate* and *+Outcome* are hidden, on the page and as items are
  added or removed. Storage is not touched: a timeline saved without one is
  still named by the Outline (`timeline_checks.NO_FIRST_ITEM`).
- **Buttons.** Along a card's foot, flush right: *Replicate*, *+Stage*,
  *Delete*. Each insert lands after the card and opens. *Delete* has no
  confirmation and is disabled on the last stage. A replica leaves the form
  behind; its gates and outcome take keys of their own, and its rules and
  weights read them. Its gates' lines say their pages wait for the save (ruling 61), and its
  ticked emails have no *Template →* until saved. Inside the card: *+Gate* (after the last gate, before the
  outcome), *+Outcome*, *+Form*; each item has *Remove the form* / *the gate*
  / *the outcome*.
- **Items reorder within their stage** (ruling 84), by the grip on an item's
  head, dragged or with ↑ ↓. The order is forced: *Create dossiers* first,
  the outcome last, the Form never before *Create dossiers*; only the gates
  between are free, and their order is saved as `gate.position`. No other item
  order is stored. A move that breaks the order is put back, the reason shown
  on the stage. A published stage keeps its items' order: the page refuses
  the move, and the server refuses a save that reorders its gates
  (`process_store.Refused`, key `published`). Items never move between stages
  (remove and re-add).
- **Links in** (ruling 65). A hash names a card: `#form`, `#gate-<key>` or
  `#outcome-<key>`. Process opens and scrolls to it, on load and on a hash
  change; a name it does not know opens the page as usual.
- **Reordering** by the card's handle, dragged or with ↑ ↓ (announcing the new
  position). A gate's or outcome's number is its place in the timeline, for display
  only, and follows as cards move; its key never changes, and the Outline and
  Dossiers' headers follow.
- **Items collapse.** A stage's items each have a head, always shown, with
  its kicker, name and chips, and a toggle for the body: a gate's state,
  results count and evaluators (*Nominated 0–2 · Panel A 1–3 · Total 3*, or
  *No evaluators*; amber on a problem); an
  outcome's release and emails; the form's state and emails. An open stage
  shows its items collapsed; an item alone in its stage, or just added, is
  open. The chips follow the edits.
- **The form item.** When it opens and closes (its own dates, else the
  stage's), a link to Form, its *Who may apply* and its *Emails* to applicants: *Receipt on submitting* and *Reminder
  to drafts*. A new form ticks the receipt only.
  - **Who may apply** (ruling 84) is a menu: *Anyone signed in*, *Invitees*
    or *Dossiers*. *Anyone signed in* and *Invitees* are stored in
    `exercise.eligibility` as `open` and `invitation`, saved with Process
    (`exercises.set_eligibility`, audited `exercise.details_changed`);
    unset reads *Anyone signed in*. *Dossiers* is derived, never stored or
    sent: while a *Create dossiers* is on the timeline the menu shows it,
    locked, and without one it is greyed out. Removing *Create dossiers*
    returns the menu to the stored value. Under the Form's lock, a changed
    value is refused by the server while its stage is published.
  - **Invitees** (`applydesk/invitees.py`): while *Invitees* is chosen the
    item shows the invite list, built as *Create dossiers*' list (search,
    *Upload CSV…* with *Email* and optional *Name* columns, *Remove*; no
    *Title*) with a row per person. Each add and removal is made at once,
    audited (`invitee.added`, `invitee.removed`), outside the Form's lock and
    not waiting for *Save*. Routes: `GET …/invitees/search`, `POST
    …/invitees` (`search`, `remove` and `csv` changes, as Create dossiers').
    A person is listed once; *Remove* retires the row and adding them again
    revives it. The list stays when another choice is picked, unused. An
    invitee may submit up to *Max dossiers per person*; their dossiers are made
    only as they submit. Checking the list when someone applies is not
    built (AD4). *Invitees* with no one on the list is an Outline warning
    (`timeline_checks.NO_INVITEES`), not an error.
- **A gate** is one Review Robin run (ruling 28), in four parts, in this
  order. The *Gate* and *Evaluators* cards are collapsible, start shut and
  say what they hold on their summary line (`stages.gate_summary`,
  `evaluators_summary`); a new gate, and an Outline jump to one, open the
  *Gate* card for its name. Its window is its own dates, else the stage's.
  The gate is *fixed* once its Review Robin session has opened
  (`workflow.gate_opened`: *Results in*, *Closed* in Review Robin and not
  yet pulled, *Detached* there, or *Sent* with its session under way): every control in it is disabled and a line says so, a revert of its
  stage leaving it so (ruling 29). Sent but unopened, it is still changed
  here, each change re-sent, unless its stage is published ("Stage
  status"). Before it is sent a gate is *Ready* only when its stage is
  published, it has a result and evaluators, every submitted row's entry
  is decided with at least one entered, every dossier entered is assigned
  with none short, and, under *Suggested, then approved*, every dossier's
  evaluators are approved; else it is *Not ready*, with the first reason
  missing (`workflow.gate_readiness`, rulings 24, 27, 34), shown beside
  the chip on Home, Evaluations and the gate page. They read what is
  saved: approvals made on the gate page stay the tab's until AD2.
  - **Its page** (rulings 61, 65): the gate's body opens, shut card or
    open, with a line saying its pairs, Review Robin session and progress
    are on its page under Evaluations, and *Open Gate n →*
    (`…/evaluations/<key>`). In a draft exercise the line says instead
    that the page is there once the exercise is published, and a new gate
    otherwise that it is there once the gate is saved.
  - **Gate**: *Name*; *Type* (`stages.GATE_TYPES`): *Review Robin Session*
    (`RRW`, the instrument fixed whole) or *Review Robin Session (custom)*
    (`RRW-custom`), whose instrument Review Robin may extend around the
    gate's response fields, which it holds (`spec/linked_sessions.md`
    `instrument_structure`). The menu is live until the gate's session
    opens and as wide as its longest choice. Process's Save writes it
    (`process_save` refuses any other value). It shows on a shut card's
    line, in Evaluations' *Type* column and in `process.csv`'s gate
    `detail` as `type=`; the handoff's `settings.csv` always carries
    `instruments[1].linked_mode`, `custom` or `locked`, so a gate switched
    back to the default sends the switch; *Description* (Review Robin's instrument description);
    *Confidential* (per gate: Review Robin shows each applicant as *Name
    redacted* with their Dossier ID); the *Entry rule*. The exercise's *Help
    contact* and *Timezone* show read-only, linking to Home, where they are
    set: they are Review Robin's for every gate.
  - **Evaluators** (ruling 27): a row per ranked **source**, in order
    (▲ ▼; a row's **+** adds the next, × removes; *+Source* shows only
    when there is none), each a *Kind*, its *Min* and *Max* per dossier:
    - *Nominated*, the people a applicant named in a *Select people*
      question of Form, picked by its label and kept by its key, offered only
      when the form has one; or
    - *Panel*, by the shared menu and *+New panel…* box Form uses (above)
      with *Edit on Panels →*; a panel's members are on Panels, not listed.
      After its *Min* and *Max*, **All** (a Toggle, ruling 62) gives each
      dossier the whole panel: *Min* and *Max* show the panel's size and are
      disabled while it is on, and `stages.sources_of` reads them as the
      panel's size when the gate is read, so the bounds, the filling and the
      handoff follow the panel as members join or leave. A sample gate
      naming only a panel reads as one such source. A *Nominated* source has
      no *All*. Source rows stack below a 640px card width.

    Then the **Total**: its *Min* and *Max*, with the bounds the sources allow
    (their mins together, their maxes together) beside it. A Total outside
    them is a problem on the Outline, never silently clamped
    (`stages.total_problem`). When any source takes *All*, the gate takes
    that whole panel whatever its size, and every other source gives as
    many as it has, up to its max (`stages.fill`): the Total is the
    sources' bounds, shown disabled and never flagged, so a member joining
    or leaving changes nothing to retype (ruling 62, amended). A candidate
    on their own *All* panel is not counted short. The Outline also names a gate with no source,
    a source with no panel or question, a min above its max and a missing
    number. **Assignment** is a menu: *Automatic*, *Suggested, then
    approved*, *Assigned by the operator* (what each does is "The
    Evaluations page"). The filling rule is `stages.fill`: sources in rank
    order, the first giving as many as it has up to its max, each lower one
    topping up to the Total's min and never under its own min, nothing past
    the Total's max; evaluators distinct by email, a person in two sources
    counted for the higher; the applicant never their own evaluator. A
    dossier it cannot fill is *Short*. A panel gives its least-loaded
    members first. Referees are not a source.
  - **Response fields**: what each evaluator answers in Review Robin, a row
    each, edited in place: *Label*, *Type* (Integer, Integer (scale), Decimal,
    Decimal (scale), List or String, with Min/Max/Step, Max length or
    Options; `stages.FIELD_CHOICES`), *Required*, and *Help* (shown under the
    field in Review Robin); *+Field*, *Remove the field*.
    A **scale** is stored as its number type plus a flag, as Review Robin
    keeps it; its Min/Max/Step line stays and a second line takes the
    optional *Start*, *Middle* and *End* labels (60 characters each; a typed
    `|` is kept as `¦`). Switching to or from a scale keeps the bounds;
    switching to List or String keeps no scale and no labels. The row reads
    *Integer scale 1 to 5, step 1, labelled Weak / Strong*, and a result
    collating a scale reads it as a number. A scale Review Robin would
    refuse (`stages.field_problems`, mirroring Review Robin's
    `scale_shape_error`: bounds or Step missing, Max not above Min, an
    Integer scale not whole, Max not Min plus a whole number of Steps; a
    bound is a plain decimal) is a problem on the Outline, blocks publishing
    (`locks.publish_problems`) and is refused by the Review Robin card's
    send and re-send.
    Each shows its **Key**, read-only: what Review Robin reports the field's
    answers under. A new field takes `f<n>`, the first not in use on the gate.
    A gate with none lists one per result.
  - **Results**: up to three (*+Result* disabled at three), rows that read
    as Form's card summaries and edit in place. Each has a *Name*, the
    response field it collates (*From*), *Derived as*, and *From at least*
    responses (default 1; fewer and the result is none yet). A result whose
    field was removed reads *No field chosen* and is a problem on the Outline.
    **The derivation fixes the result's type; there is no second
    definition:**

    | Field | Derivation | Result |
    |---|---|---|
    | Integer, Decimal | Mean, Median | Decimal |
    | | Lowest, Highest | the field's type |
    | | Sum | the field's type, n × its bounds |
    | List | Share choosing a value | Decimal, 0 to 100 (%) |
    | | Most common | List, the field's options |
    | String | All, joined | String, for reading |
    | any | Count of responses | Integer, from 0 |

    A List is never mapped to numbers: a numeric scale is a numeric field,
    its help text saying what the numbers mean. A Mean or Median offers
    *Ignoring 0 (no view)*, for a scale whose 0 means *no view*: the 0s are
    left out (`stages.averaged`), the result's line reads *Mean, ignoring 0*
    and the note under its chip says how many scores it took (*3.9 from 26
    of 30*). A dossier whose every score is 0 has no result (*No view from
    30*), and a rule reading it waits. Under the fields, *For Review Robin*
    lists what each evaluator answers, a required field saying so and a field
    with help carrying it (`(<type>, required; help: “…”)`). Result 1
    is the gate's headline.
  - **What Review Robin receives**: a line above that list, `Review Robin
    receives <name>: <description>, open <window> (<timezone>); help contact
    <contact>; tagged applydesk.` The window is the gate's own (`<From> to
    <To>`, `stages.window_text`), else its stage's. The description loses its
    trailing periods and is left out, with its colon, when empty; the window
    reads *when its stage's dates are set* while there is none valid. The
    page's script redraws it on every edit of the gate's name, description or
    dates, or the stage's. Once the gate's session has opened it is frozen as
    sent (`data-fixed`), though the dates may still change.
  - **Removing a gate set up in Review Robin** whose rosters are not sent
    asks first: the draft there is discarded once Process is saved, with any
    instrument built in Review Robin. Review Robin's discard
    (`spec/handoffs.md` §6b) refuses anything else, so a gate with rosters
    sent or an opened session is never discarded. Simulated in the tab
    until AD6 makes the call.
  - **Create Review Robin session** (*Secondary*) ends the gate's card, after
    *Remove the gate* and outside the gate's lock, so a published stage's
    locked gate is the one to set up. It is off, its reason in its
    title, until the exercise is published, the gate is saved and no field
    is one Review Robin would refuse (`stages.field_problems`); it is also
    off while the page holds unsaved changes, as the gate is set up as
    saved. A click sets the gate up as Evaluations' *Set up in Review Robin*
    does, with the gate's derived name and code (ruling 56), and opens
    `…/reviewrobin/operator/sessions/by-code/<code>` in a new tab; the
    button then gives way to *Open Review Robin session ↗*, as it does for
    a gate already set up or sent. A replicated stage's gates start off until
    saved. Simulated in the tab, sharing the store the Review Robin card
    reads (`applydesk-rr-setup:<exercise>`), until AD6 makes real calls.
- **The outcome.** *Name*, *Due* (a date-time, blank for the stage's end), *Values* (a row each, *+Value*, *Remove*; the list's order is the order of its values), *Rule*, and, when
  more than one gate is in scope, the *Combined result*: a weight per gate's numeric result, as
  percentages; weights that all sit at 0 are no combined result, flagged only when a rule reads one. Scope is the gates since the previous outcome (ruling 13); the
  weights follow as gates are added, removed or moved, a new gate takes what is
  left of 100, and the item says when the gates changed. *When released*, per
  audience, *Applicants* and *Evaluators* each with *Update timeline*
  (the timeline they see on signing in to their participant page) and *Send
  email*. Whether it is released is set on Dossiers.
- **The rule editor** (*Add a rule* / *Edit the rule*, on a gate or an outcome).
  A rule is **branches** (ruling 30): *if … then A; else if … then B; …
  else Z*. Each branch is a row per condition, joined by AND, with its own
  *+Condition* and *Then*; *+Else if* adds a branch, *Remove branch* drops
  one, and a branch whose last condition goes is dropped; the rule has one
  *Otherwise*. The first branch whose conditions all hold decides, none
  holding gives *Otherwise*; a one-branch rule is a single *if … then …,
  else …*. *Decide by hand* clears it. Conditions:

  | On | Kinds |
  |---|---|
  | A gate | Status; the applicant's last N submitted; an earlier outcome; a form answer |
  | An outcome | A named gate result (`≥` / `<` a number, or *is* a list's option); entry at a gate; the combined result; an earlier outcome; a form answer; the best N |

  - **A form answer** is the application's answer, as submitted, to a
    choose-one *List* question of Form, *is* one of its options.
  - **The best N** (`top`, an outcome's) ranks, by a gate's numeric result,
    the dossiers its branch reaches and keeps the N highest; a tie at the cut
    takes every tied dossier, and Dossiers' proposal says so (*21 at the cut
    of 20: tied*). Fewer than N take them all. A dossier not entered at the
    gate has no place in the ranking and falls to the next branch; while any
    dossier the branch could still take lacks a result, the branch waits and
    proposes nothing.

  A gate's *Then*s and *Otherwise* are *Entered* / *Not entered*; an
  outcome's are its values. The item's line reads as Dossiers' header does
  (`stages.rule_text`), *Decided by hand* for none. A rule names every target
  by key (gate, result, outcome, value, form question), so moving a stage or
  renaming a question keeps its meaning. A form condition and a nominated
  source name a question by its `q<n>` key ("Saving Form"); the editor offers
  the questions by label. One stored before keys may name a label, read
  through to the key of the question that carries it and written back by key at
  the next Process save.
  - **Checked on the server** (ruling 78; `rules.py` and `stages.rule_problems`
    are the only rule code; no page evaluates a rule). The page posts its
    snapshot to `…/process/problems` and shows what comes back; nothing is
    kept.
  - **Flagged**, on its item and in the Outline: a rule that reads a later
    outcome or a gate outside its outcome's scope; a form question gone from
    Form, or no longer asked as a choose-one *List* (shown "(removed)" in
    place of its label), or an answer not among its options; a best N that is not a whole
    number or ranks by a result that is not a number; deciding or comparing
    with a value its target lacks; a count or threshold that is not a number.
    It is saved as left and flagged again. Weights that are not numbers or do
    not total 100 are flagged likewise.
  - **Refused at save**, not flagged: a rule naming a gate, result or outcome
    the snapshot drops, a form condition naming a question the form no longer
    asks as a choose-one *List* ("Saving Form"), and a gate's rule reading a gate (a gate never reads
    a gate). The refusal names the rule and the target. A rule is never
    rewritten to match a removal: it means what it says.
  A rule or weight names a gate's *result* (`stages.result_label`, *Rating at
  Peer Review*), and Dossiers' headers say the same: a number (a mean,
  median, sum, count, share, or a numeric field's lowest, highest or entered
  value) is compared and weighed, a list matched, a string offered to
  neither (`stages.comparable`). Only numeric results take a weight.
- **Stage status** (ruling 35; author, 2026-11-18). Each stage is *Draft*,
  *Published*, *Overdue* or *Completed* (`locks.stage_status`); the operator
  declares only Draft and Published (`Stage.status`), the rest follow from its
  end and its items, against now (midday of `clock.today`, as `clock.midday` gives it, the sample's fixed day until stages are stored; the page's script
  derives them again as an end moves). The status box, in the card's body, and
  its chip carry it.
  - **Publish stage** takes a Draft to Published, and is disabled, saying why,
    while `locks.publish_problems` names anything, which the box lists: the
    stage has no start and end, or ends before it starts; an item's dates
    (above); the stage before it is not published (a stage is never published
    before the one before it); for the first stage, Home's details; a form with
    no questions; a gate with no evaluators, a source with none to give, a
    Total outside its sources' bounds; an outcome with no values; any rule that
    reads what no longer holds (`stages.rule_problems`). A stage added on the
    page waits to be checked until saved (AD2).
  - **Completed** and **Overdue** are derived, never set: once the stage's end
    has passed it is Completed when every item is complete (the form closed,
    each gate's results in, the outcome released) and Overdue otherwise,
    saying *Waiting on* what is outstanding (`locks.outstanding`). Items done
    before the end leave it Published until then. Moving the end, or an item's,
    past now makes it Published again: an **extension** is how a stage is kept
    open or reopened.
  - **Revert to draft** takes a Published stage back, with a reason (required;
    audited as `exercise.stage_reverted` with it), from the last published stage back, so no Draft precedes a
    Published one. Its confirm says an opened gate stays fixed and how many
    submitted applications stay submitted (`locks.revert_warnings`).
  - **The exercise's status** is derived (`locks.exercise_status`): Draft while
    every stage is, Completed when every stage is, otherwise Published. The
    lobby's *State* chip, the status row and Home read it; Closed and Archived
    stay `Exercise.state`'s (AD3).
  - **A published stage fixes**, each control disabled with its reason
    (`locks.stage_lock`, `item_lock`; one source, so no page disagrees): its
    name, *Starts*, *Shown to applicants* and its place in the order; adding to
    it and deleting it; and every setting of every item (the form's emails, a
    gate's name, rule, sources, fields and results, an outcome's name, values,
    rule and release emails, removing either), also an item's start date. Only
    ends stay editable (the stage's *Ends*, each item's end: *Closes*, *To*,
    *Due*), a stage's own fix being a revert. A gate whose session has opened is
    fixed whatever its stage's status. Draft stages stay fully editable.
  - **Elsewhere**, the same locks: Form is read-only ("The Form page"),
    Dossiers fixes an opened gate's cells and gates *Released* on owed emails
    ("The Dossiers page"), and Home fixes blind review ("Details").
- **The Outline** lists each stage by name and dates with its items beneath,
  the counts (stages, gates, outcomes) and every problem, among them a gate
  with no evaluators. A stage or item is a button: it opens its card and goes to
  it. *Save* and the *Unsaved changes* marker sit at its foot, kept as Form's
  are (ruling 23): a warning on leaving with changes pending.
- **Saving Process** (`applydesk/process_store.py`; the post is
  `routes_operator.exercise_process_save`, a same-site JSON post of at
  most `web.MAX_BODY`). *Save* is live on every
  exercise and keeps the page's whole snapshot in the
  database, replacing the draft (ruling 23); a reload or a restart shows it.
  - **One transaction**, under the exercise's row lock, guarded by
    `exercise.process_revision` (0 until the first save). The post names the
    revision the page opened at; an older one is refused with a 409
    (*Process was saved since this page opened; reload*), nothing merged.
    Two first saves meeting are refused likewise. An archived exercise is
    refused. Every refusal is a 400 naming why, bar the stale one.
  - **Checked** as before the store (the limits and shapes of the post:
    20 stages, 10 gates a stage, 50 in any list, at least one stage;
    refused as having no shape to be kept in: a date range with one end alone,
    a weight that is blank or not a whole percent, an evaluator count that is
    not a whole number, a result reading a field its gate lacks, a panel
    source the exercise lacks), then ruling 15's shape (`stages.problems`),
    dates that run backwards, two items sharing a key or an outcome two
    values of one label, and rules naming a removed target (above).
  - **Keys** (ruling 37). A stage, gate, outcome, gate field, result and
    outcome value keeps its key across saves, whatever its position; the
    server mints the key of a new one (`s<n>`, `g<n>`, `o<n>`, `f<n>`,
    `r<n>`, `v<n>`), and a key a page minted for it (`gnew1`) never reaches a
    row. A stage's, gate's or outcome's key is never reused within its
    exercise: what a save drops is retired, not deleted, so an old link
    404s rather than reaching a new gate. A field, result or value a save
    drops may be added back and takes its row again. A sample exercise's
    own keys count as held, and its timeline is recorded at its first
    save, its cells staying the sample's until Dossiers stores them.
    Evaluator sources and outcome weights are replaced by each save.
  - **Published stages** (ruling 35). The server refuses what the page
    disables on a published stage: removing it, changing its name, start or
    *Shown to applicants*, and adding a gate, outcome or form to it. Its end
    stays editable. Reverting a stage to draft goes with the save that
    records it, audited with its reason (`exercise.stage_reverted`). A
    rule or value edit on a published stage is not refused by the save.
  - **The form's window and state** are on the stage holding the form
    (`form_opens_at`, `form_closes_at`, `form_state`); that stage is their one
    source. A form moved to another stage takes its state with it, and the
    state it is first stored with is the exercise's (a draft's `draft`,
    a published one's `open` or `closed`).
  - **Audited** as `exercise.process_saved` with the counts of stages,
    gates and outcomes saved and retired, and the new revision.
  - **The emails it ticks** are recorded with the save, in its transaction,
    for every exercise (`email_store.save_sends`; "The Emails page"). A
    panel made with *+New panel…* is
    stored with the save, on a sample too ("The Panels page").
- **The outcome values editor.** An outcome's values are rows, each carrying
  its key; a renamed value keeps its key and the page rewrites the rules
  naming it, so a rename changes no stored rule. A value whose label no row
  carries a key for takes its old label's key if unclaimed, else a new key;
  carried keys are assigned first, so reordering rows hands no key to
  another value. A removed value's key stays on its retired row.
- **The *Create dossiers* item** (rulings 77 and 83, `applydesk/candidates.py`; *Candidates* in code): people
  kept by hand, shown as a stage item with a count, a search, *Upload CSV…*
  and a list (name, email, when added, *Remove*). A Form
  after it invites from its dossiers (the Form's *Who may apply*); feeding gates as dossiers is not
  built. At most one stage holds it, with the form, with gates or alone
  (`stages.problems`): *+Create dossiers* is disabled with its reason once an
  exercise has one, and *Remove Create dossiers* removes the item,
  not the list. A person is listed once, and each add and removal is made at
  once, audited, not waiting for *Save*.
  - **Search** is the people search of ruling 75 (`applydesk/directory.py`:
    people on record, then the directory; those listed left out; a failed
    directory search says so). A pick is added as `search`.
  - **CSV** has an *Email* column and, if given, a *Name* (any case, any
    order), one address a row, at most 2,000 rows. Each row's address is
    matched to a person on record, else made a pending person
    (`people.pending`; the directory is not searched per row); a name fills a
    pending person's blank name. The good rows are saved in one transaction
    and the rest reported back by row number, not saved: an address that is
    not one, or in the file twice. A person listed already is counted, not
    reported. A file with no *Email* column, an empty file or one that
    cannot be read is refused whole. Added as `csv`.
  - **Remove** retires the row; adding the person again revives it.
  - A Form after it invites from these dossiers; nothing checks the dossiers
    when someone applies yet (AD4).
- **Emails** (ruling 16). Process picks no template. Each email ticked, the
  form's receipt and reminder or an outcome's *Send email* per audience, is a
  template owed on the Emails page, named for its stage (*Review: Outcome ·
  Applicants*, *Call for applications: Receipt · Applicants*), one section each
  in timeline order with a *Written* or *Owed* chip (`workflow.emails`). Each
  saved tick is followed by *Template →*, to its card on Emails (ruling
  65); a tick not yet saved has none until Emails lists it. An
  outcome with an owed email is not ready to release. `workflow.steps`
  records which audiences' emails are not written, but no page shows it
  until a Workflow card returns; meanwhile the *Owed* chips and the status
  row's Emails pill do. Template text is written on Emails; sending comes
  later (AD6, AD7).
- **Preview** of the timeline the cards describe is not built.

## The Panels page

The Setup tab for everyone on the exercise's panels (rulings 19, 20, 22, 23),
`/operator/exercises/<id>/panels`. A **panel** (`sample_data.Panel`: key,
name, members) is a named roster Apply Desk keeps: an assessment panel, the
evaluator pool, the interviewers. Every panel is generic (ruling 39): what
it does comes from where it is used (a Select people question, a gate's
evaluator source), never from its key. Form and Process hold a panel's
*key*, not its name, so a rename follows everywhere. Panels laid out as Review Robin's
roster pages: a roster card, then one full-width table. Every move works in
the browser; nothing is kept until the page's *Save* (below).
A panel made on Form or Process appears here once that page is saved.

- **The roster card.** *People* (the count of rows), a pill per panel with its
  count, how many panels are in use, and *Manage panels*. Problems list under
  it: an email not found in the directory, one listed twice, a panel in use
  with nobody on it.
- **Manage panels** opens a card of actions (ruling 23), where Review Robin
  has *Unlock*:
  - *Panels*: each panel's name edited in place, *Copy emails* (its addresses,
    comma-separated, to the clipboard) and *Retire*, disabled with its
    reason while a question or gate uses the panel. Each shows its count and
    *Used by* (*Gate 1: Peer Review*) or *Not used yet*; a panel an opened
    gate uses says that gate keeps it.
  - *Add new panel*: *Name*, then *People* (*None: a blank panel* or *Copy
    from* a panel). A blank panel takes *Members* in the token box Form's
    *+New panel…* has; a row is added for anyone not yet in the table.
    *+Panel* is Secondary.
  - *Upload*: *Upload CSV* and *Download CSV*. The CSV has `Name`, `Email` and
    `Note` and a column per panel by name, marked for each member; people not
    found in the directory are left out and named.
  - *Cancel*, *Save* and *Close* at the card's bottom right. A rename, a
    panel added and a panel retired wait for *Save*: each is marked *not
    saved yet* (a retired panel's heading and chip struck through), and the
    columns, pills and menus follow at once. *Cancel* takes them back, with
    the rows an added panel brought (a row kept with its own ✓ stays); neither
    closes the card. Enter in a name box is *Save*, Esc puts that name back.
    *Close* asks first while any waits. *Copy emails* and the CSV act at once.
  - Whatever ✓, ×, *Save* or an import changes is on the page only until the
    page's *Save*: ✓ says *kept on this page* (*nothing changed* on an
    untouched row), *Unsaved changes* shows beside the page's *Save*, and
    leaving asks first, as it does while a ticked row holds changes ✓ has not
    kept. ×
    on a member of a panel an opened gate keeps (as kept, not as ticked
    while editing) asks before removing them.
- **The table.** Above it, in two columns (ruling 65): on the left, *Show
  columns:*, a chip per panel, pressed while its column shows; on the
  right, *Filter* (matches name, email, note and the names of the panels a
  row is on; a row being edited stays in view) with *Add new* under it,
  which opens a blank row at the top (an imported row joins the end). Columns:
  a select box, *Name*, *Email*, *Note*, one per panel and a ✓ and × column;
  *Name*, *Email* and *Note* sort with ↕, three-state with shift-cascade, as the gate page's; an
  empty roster shows the empty-state card in the table's place. A panel's heading carries its count
  and an *Opened* chip once a gate it feeds has opened (`workflow.panels_sent`),
  the chip's tooltip naming those gates; the heading's tooltip says *Used by*
  or *Not used yet*.
  Widths are fixed, so selecting a row moves nothing.
- **Editing a row** (ruling 22; how Panels keeps an edit, ruling 23). A row
  is inert until its box is ticked: then its cells are edit boxes and its
  panel ticks live. Several rows may be ticked at once. ✓ at the row's end
  (Enter too) keeps its changes on the page; unticking without ✓ puts the row
  back, and a new row never kept goes. A verified email, found in the
  directory, is a pill, clicked to change it; unticked it reads as text, red
  when the directory has no such person.
- **Checks.** An email is required, found in the directory and listed once.
- **Save** (`routes_operator._save_panels`; `applydesk/panels_store.py`),
  for every exercise: the page's panels and roster are
  kept in the database, and a page saved says *Saved.*.
  - **Revision.** The page carries the `exercise.panels_revision` it opened
    at (read before its panels). A save from an older one is refused whole
    (409; *Panels was saved since this page opened*): nothing merges. A save
    returns its new revision, which the page keeps, so edits made while it
    was on the way can be saved next.
  - **One transaction** under the exercise's lock, audited as
    `exercise.panels_saved` (`spec/architecture.md`, "Panels"). Refused on an
    archived exercise.
  - **Refused** by the page when a row or a *Manage panels* change is still
    open (✓ or *Save* or *Cancel* it first). Refused by the server (400):
    - a panel with no name, a name over 80 characters, a name a CSV column's
      (`Name`, `Email`, `Note`; any case) or two panels with one name (case
      ignored);
    - a row with no email address, or an address on two rows;
    - a tick naming a panel not on the page;
    - retiring a panel a Form question or a gate uses;
    - more than 50 panels or 2,000 people (the author's ruling).
  - **Keys** are `panel-<n>`, minted by the server for a panel the page made
    and never reused: a retired panel keeps its key, so a question or gate
    naming it reads as missing, never as another panel. A page's own
    placeholder key (`made-1`, `new-1`) never reaches a row.
  - **People.** Each address is matched to a person on record, else made
    pending (`people.pending`), as Candidates' CSV is; the directory is not
    searched per row. The note belongs to the person's row, not to each panel.
    A name left blank is stored blank and shown as the address. A row ticked
    on no panel stays on the roster; a row removed retires its entry and
    memberships, and adding the person again revives them.
  - **Sample exercises.** The sample's panels stand until the first save,
    which records them with the page's changes and keeps their keys.
  - **After a save** the page reloads to hold the keys kept.
- **A panel made on Form or Process** (*+New panel…*) is stored with that
  page's own save, for every exercise (a sample's included), in the same
  transaction and under the
  exercise's lock, so a refusal of either keeps neither. It is minted a key,
  named and capped as above, its members join the roster, and a panel the
  exercise already holds by that name is that panel, not a second one. A
  save naming no new panel writes no panels save.
- **An opened gate** (`workflow.gate_opened`: its Review Robin session has
  opened, ruling 29) keeps the roster it opened with: its panel says so here,
  with an *Opened* chip, and on Process. Every panel source of a gate counts
  (`stages.gate_panels`), for *Used by* and the *Retire* guard too.

## The Dossiers page

At `/operator/exercises/<id>/dossiers` (the Applications page until ruling
25): a row per dossier, an application's where it has one; until dossiers
are made (*Create dossiers*, ruling 26), the rows are the sample's
applications. A row is named by its *Dossier* ID, linking a submitted one
to its operator page (below), with its *Application* ID under it; a draft has no
dossier yet (ruling 32) and says so. Search reads both IDs, the cells,
proposals and messages name the row as it shows, and the CSV keys rows
by Application ID. The dossier page shows its
Dossier ID, as Review Robin does for a confidential gate.

**A dossier's operator page** (`…/dossiers/<dossier>`, ruling 64): under
Dossiers, its breadcrumb back there, as Review Robin's drill-ins. Read
only: its *Application* (applicant, email, status, Application ID), its
row's *Gates and outcomes* (each column's chip and note, as Dossiers
holds them) and what is *Shown to evaluators*. *View as evaluators see it
↗* opens the dossier's `/me` page, the one evaluators open, in a new tab,
as Review Robin's *Open reviewer surface*. A draft has no dossier (ruling
32): its page is a 404; a withdrawn application's still answers.
A control surface (ruling 23), worked down its columns. The whole table is
locked until *Unlock*; then every cell, *Set ticked rows*, *Apply rules…*,
*Upload CSV* and each outcome's *Released* are live, but for the fixed ones
below. *Discard changes* puts the table back as it was when unlocked, then
*Lock* keeps what changed; meanwhile a count of the changes shows. Locked, what differs from the page as loaded
stays marked (*N changes on this page, not saved*), and leaving the page with any pending or
kept asks first. *Return to draft* is a submitted row's own (Outline-amber)
until a gate holding its dossier completes, as withdrawal is, and *Return
ticked to draft* the ticked rows', gates or none (rulings 45, 49; both disabled until AD4). Ticks
only choose rows; the *Dossier* header's tick ticks every
row in view, or clears them, and *Set ticked rows* with none ticked says *No
rows ticked*. *Download CSV* writes the rows in view in the shape *Upload
CSV* reads, a cell a spreadsheet would run as a formula guarded with `'` (a
lone `-`, no status, is not), named `<code>_dossiers_<date>.csv`; *Upload
CSV* undoes the guard. The page has no *Save*; nothing is kept until AD2.

- **The header** (ruling 52). Under the stages, an information row holds
  each column's kind, counts, rule, lock and *Released*, top-aligned; under
  it the column headers stand on one line, each name a sort button with a
  `↕` badge (`1↑` / `1↓` once sorted). A rule's text clamps to two lines, in
  full on focus and in its title.
- **Sorting** (ruling 52). A column's name sorts the rows by it:
  ascending, then descending, then the page's own order. *Dossier* by ID,
  drafts last; *Applicant* by name; *Status* as Submitted, Draft,
  Withdrawn, then date; a gate by its chip (Entered, Not entered, —), then
  its headline result, highest first; an outcome by its values in
  Process's order, then *Pending*, then —, then date; descending
  reverses the whole order. Ties keep the page's order. It moves rows, never a cell, so it works while the table
  is locked; the CSV follows it; the tab keeps it (`sessionStorage`).
- **Finding rows.** The filters stand together at the top, each labelled
  (ruling 64): *Search* matches, in any case, a row's Dossier ID (a draft
  has none), Application ID, applicant's name and email; *Status* is *All
  statuses*, *Submitted*, *Draft* or *Withdrawn*; *Rows* is *All dossiers*
  or *Last applications*: per applicant, by email, the latest submitted,
  else the latest started of any status (`stages.last_submitted`), latest
  by time in UTC, ties by Application ID (segment AD2J); a gate rule's
  *last N submitted* ranks the same way (`stages.submitted_rank`). The three
  combine, and *Showing N of M dossiers* beside them counts the rows in view. The
  ticked rows' actions (*Set ticked rows*, *Return ticked to draft*) and
  *Download CSV* stand in a row above the table.
- **The CSV.** *Download CSV* writes `Application ID`, `Applicant`, `Email`,
  `Status`, then a column per gate and outcome headed by its label, UTF-8
  with a byte-order mark; no status yet (*—*) is written `-`. *Upload CSV*
  needs an `Application ID` column, matched in any case; any other column
  is matched to a gate or outcome by its label, `Gate N: label` or
  `Gate N`, and `Applicant`, `Email` and `Status` are read past. A cell `-`
  reads as *—*, a blank cell leaves it as it is, and a value must be one of
  the column's, in any case. The upload is a proposal, as *Apply rules…*'s:
  it lists what would change and, left alone, unknown IDs, columns not on
  the page, values not the column's, cells that cannot be set (a draft's,
  one never admitted, a fixed one) and a cell given two values; nothing
  changes until *Apply*. A file downloaded and uploaded back changes
  nothing.
- **Released** asks first. Turning it on names how many dossiers it reaches
  are still undecided or *Pending*, then asks *Release <outcome>?*, saying
  Process sets what a release does and nothing is sent; turning it off asks
  *Withdraw the release of <outcome>?*. Cancelled, the checkbox goes back;
  confirmed, the note under it reads today's date *· as Process sets*, or
  *Not yet*. *Ruled, not built (2026-11-18, ruling 38):* release is to be
  recorded per audience (applicants, evaluators), each with its own time,
  and an outcome's *Decided* derived from every reached cell having a
  value, never stored; today one checkbox releases to every audience
  Process sets.

*Apply rules…* proposes each outcome and gate cell from the rule Process
holds (branches in order, a form answer from the application's answers, the
best N), as a proposal the operator approves (Esc is its *Cancel*). The
proposal is the server's (`applydesk/rules.py`, ruling 78, posted to
`…/dossiers/proposal`: a same-site JSON post, 415 for non-JSON, 413 past
4 MiB): the page sends the cells as it holds them, hand changes included, and
the engine answers for them under the timeline as saved, so an unsaved Process
edit is not seen until saved. The page waits on the answer and, past about
two seconds, says it is working. Nothing changes until the operator approves.
A hand-set cell is kept unless
*Also replace cells set by hand* is ticked. An outcome whose gates a dossier entered none of is not reached
and stays as it is, unless its cell is already open (*Pending* or decided) or
a branch of its rule reads earlier outcomes' values alone and they hold, set
by hand or by the same run: re-appointment skips the interview and still
reaches *Selection*. An outcome's **going-on values** are every one but its
last (`stages.going_on`; *Re-appointment* and *Interview*, not *Not
shortlisted*): each is counted in its column head and toned green, the rest
muted, undecided amber. A mean's note under its chip says how many scores it
took (`stages.mean_note`); where a branch left a field unasked it also
says how many were not asked, kept apart from those who left it blank
(*4.1 from 26 of 30 · 4 not asked*). The sample exercise's Gate 1 is
custom.

- **A gate's cells are fixed once its Review Robin session has opened**
  (`locks.cells_lock`; entry flips there change who the results cover). The
  column says so, its cells stay disabled when the table is unlocked, and
  *Set ticked rows*, *Apply rules…* and *Upload CSV* skip them, naming what
  they skipped. A gate whose stage is published but not yet opened keeps live
  cells: entering applications is that stage's work while it runs.
- **Released waits on its emails** (`locks.release_lock`): the checkbox is off,
  with the reason, while an email the release sends is owed on Emails, and a
  release withdrawn waits on them to be made again. Before a release, the
  dossiers it reaches that are still undecided or *Pending* are counted; a
  row none of whose gates entered it is not reached, unless a branch of the
  rule reads earlier outcomes alone and they hold.

## The Evaluations page

At `/operator/exercises/<id>/evaluations`: the **Gates** table (gate, type,
state, progress, and a link to the gate's Review Robin card, *Review Robin card
→*, ruling 64, flush right, ruling 65), then **Assignments**, one card with a row per gate:
its mode, its counts (*42 dossiers · 40 filled · 2 short*, over every pair),
its load line per panel source (*Ana 6 · Ben 5 …*) and a link, *Pairs (n)
→*, to the gate's own page. A draft exercise shows neither. Nothing is
saved until AD2; a reload restores the sample.

**The gate page**, `…/evaluations/<key>` (`routes_operator.gate_evaluations`),
the gate's own key, 404 for a gate the exercise lacks (a removed gate's key
included: it is never given to another gate) or a draft exercise. An old
`gate_<n>` link, which sent emails and bookmarks hold, redirects once (302,
not cached, its query kept) to the gate numbered so now; the same holds for
its `<kind>.csv` files. A number naming no gate is a 404. Its breadcrumb runs
Exercise / Evaluations / *Gate n · label*. Under its banner, a line says its name,
dates, evaluators and rules are set on Process, and *Set on Process →* opens
its card there (`…/process#gate-<key>`, ruling 65). The gate's head (its
state chip, as Evaluations' Gates table, its mode and counts, and *Review
Robin ↓* to the card below), the **Review Robin card**, its load lines and a table with **a row per pair**,
*Applicant*, *Evaluator*, *Source*, *State*; a dossier with no evaluator yet
is one row, *None yet*. A blind exercise, or a confidential gate (ruling 42),
shows the dossier ID as the applicant, and is searched and sorted by it. The pairs are `stages.assignments`, drawn as the gate's mode and
sources fill them. A gate can pair 30 evaluators with 100 dossiers, so the
table is paged and queried in the URL (`offset`, `q`, `sort`), and a link
keeps all of them.

- **The Review Robin card** (ruling 55), laid out as ruling 65. The whole
  card folds, shut as the page loads (author, 2026-11-20), its heading line
  keeping the counts of evaluators, dossiers and pairs; a link to it (the
  head's *Review Robin ↓*, Evaluations' *Review Robin card →*) opens it.
  Open: at the
  top, two columns. On the left are the session's name and code, derived
  as *exercise name — gate label* and *public ID*`-g`*n* (ruling 56). On
  the right are the link (*Not linked: nothing sent yet*, *Linked; set up, its rosters not
  yet sent*, *Linked; sent,
  its session not yet open*, *Linked; its session is open*, *Linked; its
  session has closed, its results not yet pulled*, *Detached: unlinked in
  Review Robin, so neither re-sent nor pulled*, *Linked; its results are
  in*), the last send, *Invited* and *Reminded*. Then *What is sent*, four
  tiles 2 × 2, each a title, a line and *Download*. Then *Progress*, a
  full-width panel: its line, then *Set up in Review Robin* (*Secondary*),
  *Send rosters* (*Primary*), *Re-send*,
  *Pull results*, *Invite evaluators* and *Remind those not done*, then
  a progress row per paired evaluator, in an *Evaluators* section shut
  until opened (author, 2026-11-20): the actions stay in view, and a pull
  opens it. All are simulated in the tab
  (`_rr_js.html`). At a phone's width each pair of columns stacks.
- **Set up in Review Robin** (`_rr_js.html`), a step before *Send rosters*
  (segment 23J), makes the gate's session as an empty linked draft carrying
  its settings and response fields, so a custom gate's instrument can be
  built there before the rosters are known. It is offered once the exercise
  is published, for either gate type, and is a manual step, never made by
  a Save. It checks the session's name and code (against the exercise's
  other gates' codes, set-up ones included) and any field Review Robin would
  refuse; the pairs and the gate's readiness wait for *Send rosters*. The
  gate is then *Set up*: a state between *Not set up* and *Sent*, read on the
  link line, with the set-up kept under `applydesk-rr-setup:<exercise>`
  beside its transfer; *Set up* is off from then on. *Open in Review Robin ↗*
  (new tab) is live from set-up on, and goes to the session by its code
  (`/operator/sessions/by-code/<code>`, `spec/session_home.md`): the code it
  was sent or set up with, else the sample's. *Send rosters* after a
  set-up sends to the set-up's transfer, as a re-send. Review Robin's
  step is a linked create without rosters (`spec/handoffs.md` §5). **Set-up
  is simulated in the browser tab until AD6 makes the real calls.**
- **Send rosters and Re-send** (`_rr_js.html`), simulated in the tab (ruling 55):
  a send is kept in `sessionStorage` under `applydesk-rr:<exercise>`, by
  gate, with its name, code, time, transfer ID and the bundle's digest.
  The head's chip and Evaluations' row then read *Sent* (*Sent in this
  tab*), and *Send rosters* is off. *Re-send* is on while the name, the code or
  the files differ from what was sent, marked *Changed since sent*.
  Refusals name Review Robin's code: `invalid_package` (a name of 1–255
  characters, a code of 1–64), `session_code_conflict` (another of the
  exercise's gates holds the code, any case), `invalid_setup` (the gate
  not *Ready*, or this tab having added or removed pairs, since the files
  are the pairs as saved; a re-send is refused the same). Review Robin's
  `session_opened` is not drawn: an opened gate's buttons are off with
  the reason instead; `session_has_responses` and `not_linked` cannot
  arise in the sample. A gate the sample has sent whose session has not
  opened reads as sent: *Re-send*, not *Send rosters*. A Suggested gate whose only lack is its
  approvals is sent once this tab has approved every dossier, none
  short. A gate opened, closed or detached in Review Robin sends and
  re-sends nothing, its name and code fixed, the reason in each title.
- **Pull results** (ruling 57), on a gate whose session has opened, fills
  *Done* per evaluator (`workflow.progress_of`: the sample keeps only the
  gate's line, so each evaluator shows that share of their pairs). A
  detached gate shows what Review Robin last reported. On a
  gate *Closed* in Review Robin it reads **Pull final results**, which
  marks the gate *Results in* (head chip, link line, Evaluations' row,
  *Results pulled in this tab*); the results fill Dossiers with AD6. Off,
  with the reason, before its session opens, once its results are in, or
  detached.
- **Invite evaluators** (a gate sent, in the tab or the sample, with
  evaluators paired, its session neither closed nor detached, its results
  not in)
  and **Remind those not done** (an open session, someone not done) show
  the email first, under the buttons: whom it goes to, its subject and
  body, fixed until AD7 puts these templates on Emails, linking Review
  Robin's `/me`, where an evaluator signs in. *Send (simulated)* records
  when and how many in the card's *Invited* or *Reminded* line; *Cancel*
  or Escape closes it. Pulls, invitations and reminders are kept under
  `applydesk-rr-log:<exercise>`.
- **What is sent** (`applydesk/handoff.py`, built from the gate's pairs
  and card as saved, not this tab's changes): **reviewers**, each paired
  evaluator once by name and email, no tags; **reviewees**, each dossier
  entered, keyed by its application ID with its dossier page as an
  absolute `ProfileLink`, or on a blind exercise or confidential gate by
  its Dossier ID with the name *Name redacted* (ruling 43);
  **relationships**, each pair tagged `PairContextTag1.Apply-Desk-Link`
  with its evaluator's source, commas dropped; **settings**, the gate's
  description, the exercise's help contact and timezone, the gate's
  window with its offset, the tag `applydesk`, and one instrument named
  for the gate holding its response fields (a scale's `scale` = `true` and, when
  set, `scale_labels`, beside its `data_type`, which stays Integer or
  Decimal; the extract's field detail shows both, a result's never). Never observers, release,
  rules or layouts. Each file downloads from
  `…/evaluations/<key>/<kind>.csv` as `<code>_<kind>.csv`, each cell a
  spreadsheet would run as a formula guarded with `'` (`extract.guarded`);
  the handoff sends Review Robin the files unguarded, as its handoff route
  takes them (`tests/integration/test_handoffs.py`).
- **Paging** (`applydesk/paging.py`): 200 rows a page, a pager as Review
  Robin's rosters, « ‹, a range menu of every page (*201–400*), › », kept
  on one line and repeated below a table longer than a page; an
  offset is snapped to a page and one past the last clamps to the last, one
  that is not a whole number is the first page.
- **Filter**, *Find an applicant or an evaluator*: the applicant's name, email,
  application or dossier ID, or the pair's evaluator's name or email, any
  case (`stages.matching`). A blind exercise's or a confidential gate's applicant is found by the
  dossier ID alone, never by who they are. *Clear* drops the filter, not the
  sort.
- **Sort**, as Review Robin's tables (`spec/sort_by_reviewee.md`), on the
  server because a page holds 200 of the gate's rows (`paging.parse_sort`,
  `stages.sorted_pairs`): a column's ↕ sorts it up, again down, again clears
  it; shift-click adds it to a cascade of three. A header shows its place
  and direction, `1↑`, `2↓`. An empty cell sorts last either way and numbers
  sort as numbers (*Short by 2* before *Short by 10*); the fill's order
  breaks ties. A new order starts at the first page; the pager, range menu
  and filter keep it. A blind exercise's or a confidential gate's table sorts by dossier ID.
- **States**, by mode (`stages.assignment_state`): *Short by n* when the
  Total's min is not met, *Short* when a source gives less than its own min,
  else *Filled* (Automatic), *Suggested* then *Approved* (Suggested), *Not
  assigned* then *Assigned* (Assigned). A pair removed in the tab reads
  *Removed*. The head's counts and the load lines follow **every** pair, not
  the page's.

**Operations**, by the gate's mode (`Assignment` on Process); they work in
the browser (`_gate_ops_js.html`):

| Mode | Starts as | Operations |
|---|---|---|
| Automatic | every dossier filled as its sources give | *+Pair*, *Remove* (then *Undo*): never re-run, only edited by hand (ruling 48) |
| Suggested, then approved | the fill, each pair *Suggested* | *Approve* on any of a dossier's pairs approves them all, as ruling 34 has it (*Approved*, clicked again, takes them back; a pair added later waits for its own), *Approve all* (asking first while a dossier is short), *Remove* (then *Undo*), *+Pair* |
| Assigned by the operator | empty, every dossier *Not assigned* | *+Pair*, *Remove* |

- **Ticks** (ruling 51). Each pair's row has a tick, in its first cell,
  and the header's ticks every pair on the page. With rows ticked,
  *Approve all* becomes *Approve ticked (n)*: each ticked row's dossier
  approved whole (ruling 34), asking first if any is short. *Discard
  changes* becomes *Discard ticked (n)*, off when they hold none, asking
  first past three changed pairs: a ticked pair removed comes back where
  its dossier has room, one added goes, and its dossier's approval is
  taken back. A ticked row removed approves nothing. Ticks are the page's
  own and clear once acted on. A row's own buttons sit at its end.
- **Kept in the tab.** Changes live in `sessionStorage` under
  `applydesk-ev:<exercise>:<gate>:<mode>`, so paging, sorting and searching
  keep them; *Changes in this tab, not saved* and *Discard
  changes* show while any exist,
  and Discard puts the sample back, asking first past three changes. Leaving the gate's pages with any asks
  first, a reload included, since the browser cannot tell a reload from
  closing the tab, which loses them; its own pager, sort and filter do
  not. On load they are reconciled against the
  sample, the mode and the limits: a stale pair, an approval the mode lacks or
  an addition past a limit is dropped.
- **+Pair** opens a panel to choose a dossier and an evaluator. The
  evaluators offered are the gate's panel members less the applicant and
  those already on the dossier; it refuses a pair that would pass the
  Total's max or the source's max, saying why. **Undo is held to the same
  limits** and says why it did not undo. An added pair shows on the first page
  only, and under a filter only if it matches; removing it takes its approval
  with it, while Undo keeps an approval.
- **Off** once the gate's session has opened (`workflow.gate_opened`: its
  pairs are Review Robin's to change), with the reason in each button's title;
  and off until the page's script has run.
- **A blind or confidential gate's +Pair** still never offers an applicant
  as their own evaluator: the page's data names no applicant, but gives each
  dossier the one panel member it may not take, its applicant when they sit
  on the gate's panels (author, 2026-11-18). AD2's server checks it again.

The model exercise, *Recruitment and Selection of Residential Assistants*
(`wa9juxbc2t`), has gates that pair a panel of 30 with every applicant, so
the paged table is exercised there. The second exercise (`k7mfr3pq8z`)
shows the gate states the model lacks: *Panel review* *Sent* and under
way, *Second reading* *Closed* in Review Robin and not yet pulled, and
*Moderation* *Detached* (`workflow._GATES`); the last two count as opened.

## Extract data

At `/operator/exercises/<id>/extract`: Review Robin's Extract data, a
workbench that cuts the exercise's data into files and **shows none of it**
(Dossiers shows one application, a gate's page one gate). Files are built by
`applydesk/extract.py` from the sample until AD2 (applications, setup), AD4
(applicants' answers) and AD5 (Review Robin's answers); downloads are logged
from AD2.

- **Cards.** Six, two to a row and one column under 900px: *Extract all
  data*, *Applications*, *By gate*, *Outcomes*, *Alias key*, *Extract
  setup*. Each has a heading, a line on what its file answers, chips, the
  file's columns in a line and its download at the foot. No card draws a
  data table; *By gate* lists its gates with row counts.
- **Chips** shape the download's link: a many-of chip (*Carries*, Extract
  setup's pages) is a `.pn-show` pill, a one-of choice a `.seg` (ruling 47),
  both with rounded sides at one height, `--tog-h` (ruling 63).
  Each viewer's are kept in `localStorage` `applydesk-extract-<id>`; with storage blocked, or no script,
  the defaults apply. *Download all (ZIP)*'s link also takes the other cards' settings
  (Applications' rows and drafts, By gate's shape, Outcomes' rows, Extract
  setup's pages) so the ZIP carries each file as its card is set.
  While its files line names only `manifest.csv` (nothing carried, or Setup
  carried with every setup page off), *Download all (ZIP)* is off, titled *Tick a file
  to carry first*.

| Card | Chips (default first) | Download |
|---|---|---|
| Extract all data | *Carries*: Applications, Gates, Outcomes on; Setup off. *Applicants as*: Names, Dossier IDs | *Download all (ZIP)* |
| Applications | *Rows*: Last applications, All applications. *Drafts*: Left out, Included | *Download CSV* |
| By gate | *Shape*: A row per pair, A row per application. *Applicants as*: Names, Dossier IDs (Dossier IDs pressed) | a *Download CSV* per gate; *Download gates (ZIP)* |
| Outcomes | *Rows*: Last applications, All applications | *Download CSV* |
| Alias key | none | *Download key (CSV)* |
| Extract setup | *Carries*: Form, Process, Panels, Emails, all on | *Download setup (ZIP)* |

- **The route** `GET /operator/exercises/<id>/extract/<file>`
  (`routes_operator.extract_file`, `applydesk_extract_file`; 404 for an
  unknown exercise or file). Files: `applications.csv`, `outcomes.csv`,
  `alias_key.csv`, `gate_<key>.csv`, `gates.zip`, `all.zip`, `setup.zip`.
  Query parameters, an unrecognized value reading as its default:

  | Parameter | Values | Read by |
  |---|---|---|
  | `rows` | `last`, `all` | applications, outcomes, `all.zip` |
  | `drafts` | `1` | applications, `all.zip` |
  | `shape` | `pair`, `application` | gate files, `gates.zip`, `all.zip` |
  | `applicants` | `names`, `ids` | gate files, outcomes, the ZIPs |
  | `carries` | comma-separated | `all.zip`: `applications`, `gates`, `outcomes`, `setup`; `setup.zip`: `form`, `process`, `panels`, `emails` (`none` for none) |
  | `orows` | `last`, `all` | `all.zip`'s outcomes |
  | `sparts` | comma-separated setup pages | `all.zip`'s `setup/` files |

  Without `applicants`, `extract.names_by_default` decides: a gate's files
  by Dossier ID; outcomes by name unless blind review is on; `all.zip` by name unless blind review is
  on or any gate is confidential, when it starts on Dossier IDs and the card
  says why. The operator may still choose *Names*: the files are the
  operator's, and a dossier part's visibility governs only what applicants
  and evaluators see.
- **The files.** CSV with a header row, UTF-8 **with a byte-order mark**
  (Apply Desk's choice, so Excel reads UTF-8; Review Robin's importers
  tolerate it on read though its own extracts write none), CRLF line ends.
  Every cell goes through `extract.safe`: one starting `=`, `+`, `-`, `@`, a
  tab or a return gets a leading apostrophe, a plain number aside.
  - **`applications.csv`**: a row per application, `application_id`,
    `dossier_id`, `applicant`, `email`, `state`, `submitted`, then a column
    per form question, headed by its label and read by its key, in the form's
    order (a section, page break or text block no column). *Last applications* is each applicant's
    last submitted one (Dossiers', ruling 13); *All applications* every
    submitted one; *Drafts* adds drafts, never a withdrawn application. It
    always names its applicants. A list answer is one cell, items joined by
    `; ` (Select people: the nominees); a photo its file name. Where the
    sample holds no answer, one is seeded per application and question key (a
    rename keeps it), the same every time.
  - **`gate_<key>.csv`**, by the gate's key and downloaded as
    `<key>_<slug>.csv` (the gate's name in lower case, other runs as `_`). An
    old `gate_<n>.csv` is a 404: only this page links to it.
    The file: *A row per pair* is `dossier_id`
    (then `applicant`, `email` for *Names*), `evaluator`, `evaluator_email`,
    then a column per response field by label; a dossier with no evaluator
    yet has no row. Answers are seeded per pair until AD5. *A row per
    application* is `dossier_id` (and names), then a column per result by
    name, as Dossiers collates them. A gate **not sent** (its Review Robin
    session has not opened, or the exercise is a Draft) has no file: its
    download is absent on the card, which says *Not sent* in place of a row
    count, and the route 404s.
  - **`outcomes.csv`**: a row per submitted application (*Rows* as above, no
    drafts): `dossier_id` (and names), then in the timeline's order each
    gate's results (`<gate>: <result>`), then each outcome's value and
    `<outcome> released`, the date once decided and released, else empty.
  - **`alias_key.csv`**: `dossier_id`, `application_id`, `applicant`,
    `email` for **every** application, drafts included. Never inside *Extract
    all data*.
  - **Setup CSVs**, one per Setup page, in Setup's order, from `extract.setup`:
    `form.csv` (a row per card: order, kind, type, label, help, bounds,
    options, choose, required, `shown_to_evaluators`, pool); `process.csv` (a
    row per stage item, *form*, *gate* or *outcome*, with its evaluators,
    mode, results, values, due and rule in words, and under each gate a
    *field* row per response field and a *result* row per result, their
    settings in `detail` as `name=value; …`, enough to rebuild the gate);
    `panels.csv` (long, a row per member: panel, name, email, note; Panels' own CSV is wide, a column per panel, and Extract's card says so); `emails.csv` (each template
    owed and whether it is written).
- **The ZIPs.** Named `<code>_<kind>_<date>.zip` (the Exercise code, or the
  ID if none, as a file-name slug; today's date; kind `extract`, `gates` or
  `setup`), each with `manifest.csv` first: a row per file with its row
  count, then a row per gate left out with the note *Not sent*. *Download all (ZIP)*
  holds `applications.csv`, each sent gate's file, `outcomes.csv`, and with
  *Setup* the pages Extract setup's chips leave on, under `setup/`. *Download
  gates (ZIP)* holds the sent gates' files.
- **Empty and Draft.** With no submitted applications the empty-state card
  above the cards says so, linking to Home for a Draft exercise (only its
  setup can be extracted) and to Dossiers otherwise, and every download but
  *Download setup (ZIP)* is off, its chips off with it and each saying why in
  its title; *Download setup (ZIP)* works
  for a Draft too, as it needs no applications. *Download gates (ZIP)* is off while no
  gate is sent, and *By gate*'s chips with it. An exercise with no gates says so in *By gate*.

## The Emails page

Every template the exercise owes (see Process, "Emails"), a card each in
timeline order (`workflow.emails`). A line above them says Process ticks
which items email whom, that evaluators' invitations and reminders for a
linked gate come from Apply Desk (AD7; Review Robin sends none).

- **Each card** is named for its email, `em-<item>-<audience>`
  (`workflow.email_anchor`), so a link reaches it wherever it falls; its
  *when* line ends *Set on Process →*, to the form's card (`#form`) or the
  outcome's (`#outcome-<key>`), which Process opens and scrolls to (ruling
  65). A name Process does not know opens the page as usual.
- **Layout** (author, 2026-11-19), as Form's and Process's (`fb-split`):
  the template cards in the main two columns, and on the right a card
  that stays in view (scrolling within itself when taller than the
  window) with the **Outline**, a link to each email beside its *Written*
  or *Owed* chip, kept in step as cards are saved, and the counts (*5
  emails · 3 written · 2 owed*); then the **Merge tags**, each with its
  description and the kinds that take it, listing only the tags some
  email on the page takes (`workflow.tag_rows`). Clicking a tag puts it in
  the box last used, as *Insert field* does on that card; on
  an email whose kind lacks it, it is refused and says so, and with no
  box used yet it asks for one first.
- **A card**: the template's name with a *Written* or
  *Owed* chip; when it goes (*When an application is submitted*, *To
  drafts, 7 days before the form closes*, *When <outcome> is released*);
  then *Subject* and *Body*, both editable. A template written in the
  sample shows its kind's default; an owed one starts empty.
- **Its kind** (`Email.kind`): *receipt*, *reminder*, an outcome to
  applicants, or an outcome to evaluators. The kind sets the template's
  default (`workflow.DEFAULT_TEMPLATES`).
- **Save**, each card's own (ruling 23; the page has none): on while the
  card differs from what it last saved, an *Unsaved changes* marker beside
  it. It posts to `…/emails` for every exercise and keeps the template in the
  database (`email_store.save_template`), by the item, audience and name
  Process owes it for; the status row's *Emails*, Home and Dossiers'
  *Released* follow it. A template is *Written* once it has a subject and a
  body, else *Owed* (*Saved, still owed*). A kept template shows only while
  Process still makes it owed. A sample's card never saved keeps its default
  (*Written*) or empty (*Owed*) state, and an ordinary exercise's is empty
  and *Owed*. Leaving with a card unsaved asks first. A save says *Saved.*
  (or *Saved, still owed: it needs a subject and a body.*), or is refused,
  saying why, when:
  - the post is malformed (400);
  - the email is not one Process owes, or the page opened before Process last
    saved (`workflow.process_revision`, sent as the page's revision), checked
    under the exercise's lock so no stale key lands on another outcome (400,
    *reload Emails*);
  - the template was saved since the page opened (409, *saved since the page
    opened; reload*): each card carries its own `version`, how many times it
    was saved, sent back with the save, taken from the same read as its text
    and updated after each save, so a card's save does not stale the others;
  - a subject is over 300 characters or a body over 20,000 (400);
  - the text names another kind's merge tag (`workflow.foreign_tags`; 400);
  - the exercise is archived, or deleted meanwhile (400);
  - another save of a new template lost the race (409, *reload and retry*).

  Saved audited as `exercise.email_saved` (`context`: `item`, `audience`,
  `version`, `written`). Process's *Save* records the emails it ticks for
  every exercise, with its timeline; until a sample's is first saved the
  sample keeps its own ticks (`workflow.sends`). A template whose email
  Process retires is kept, not shown.
- **Reset to default** puts the kind's default in the card, asking first
  over other text; on the default already it says so. The button reads
  *Start from the default* while the subject or the body is empty, but asks
  whenever either holds text. The default waits for *Save*.
- **Merge tags** (`workflow.EMAIL_FIELDS`, ruling 54): Review Robin's
  syntax (`spec/email_template_editor.md` §6), `$tag` or `${tag}`, case as
  written, `$$` a literal `$`. *Receipt*: `$applicant_name`,
  `$exercise_name`, `$application_id`, `$exercise_url`, `$help_contact`.
  *Reminder*: `$applicant_name`, `$exercise_name`, `$closes`,
  `$exercise_url`, `$help_contact`. *An outcome to applicants*:
  `$applicant_name`, `$exercise_name`, `$stage_name`, `$outcome`,
  `$exercise_url`, `$help_contact`. *An outcome to evaluators*:
  `$evaluator_name` in place of `$applicant_name`, and `$outcome` the
  outcome's tally; no applicant tag, so a blind exercise's names no one.
  *Insert field*, on each card, is a menu of the kind's tags, each with
  what it stands for (`workflow.TAG_HELP`), and an *Insert* button, as tall
  as the menu and in line with it, which
  puts the chosen tag at the cursor in the box last used on that card,
  else at the end of the body, braced (`${tag}`) before a letter, digit
  or `_`. *Save* refuses a template naming another kind's tag, saying
  which; an unknown tag stays as typed, as Review Robin's.
- **Paragraphs** (ruling 53): one body per template, never one per
  outcome value. The body box grows with its text, as the page's other
  boxes do, with no resize handle. A blank line in it separates
  paragraphs; Preview shows each with a small gap, and a single line
  break stays a line break.
- ***Preview*** (*Hide preview* while open) shows the card as it stands,
  saved or not, under it: the subject and the body with each tag filled
  from the sample (`workflow.sample_values`): the first submitted
  application's applicant and ID; `$closes` the form's close date;
  `$help_contact` the exercise's; `$outcome` the outcome's value in that
  row (*Pending* when undecided) or, to evaluators, its tally;
  `$evaluator_name` the first member of the first panel at that stage's
  gates; `$exercise_url` the participant page, under the mount (the route
  adds it, `_email_sample`). As Review Robin's, a default body drops each
  line whose tag comes out empty; here a body is a default when it equals
  its kind's default, saved or not. Elsewhere, in a subject or a body of one's own, a tag with no
  value in the sample (a draft has no application) shows dimmed. Another
  kind's tag shows marked.
  It follows the card as it is typed.
- **Empty**: an exercise owing no template shows one card, *No emails yet*,
  saying each email ticked on Process is listed here as a template to
  write.
