# Apply Desk as the host sees it

> **Built so far:** segment AD1 built "The registry entry", "Health",
> "Running alone" (item 1) and "The URL map" as placeholders on sample
> data (item 2), pending the author's approval in a browser. Segment AD1B
> built "The Form page" as a working scaffold: every move works on screen,
> nothing is saved. Segment AD1E built "The Process page" the same way,
> with Emails listing the templates it makes owed (ruling 16).

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

The table is `applydesk/guide/segment_AD1_skeleton.md`, "The URL map":
operators under `/operator/exercises`, participants under `/me`.

- **Public IDs** (`applydesk/ids.py`): 10 symbols from RRW's alphabet,
  `23456789abcdefghjkmnpqrstuvwxyz`, drawn at random. A path whose ID has
  any other shape, or names nothing, is a 404 before anything is read.
- **The application file**, what a reviewer opens, one per application
  (`/me/exercises/<id>/files/<file>`), is named by its own ID, never the
  application's, and shows only the *Shown to reviewers* section. In a blind exercise it
  redacts the applicant's name and identifiers.
- **The chrome** is the shared bar (`docs/header_chrome.md`): the app
  icon, the workspace's top line over *Apply Desk* (the app's name, as
  Review Robin's bar names Review Robin; author, 2026-11-13), a switcher of the
  *Operator Lobby* (`/operator/exercises`, operators only) and the *User
  Lobby* (`/me`) then *All applications*, the Light/Dark toggle and the
  account menu. Each lobby's H1 and tab read its name, as Review Robin's
  do (author, 2026-11-13). An exercise's operator pages add Review Robin's chrome
  under a breadcrumb (ruling 14, segment AD1D): *Exercise Home*
  double-height on the left; a Setup row (Process, Form, Panels, Emails)
  and an Operations row (Applications, Evaluations, Extract data); and a
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
  Review Robin's do. Until AD2 knows Apply Desk's operators, an operator
  is everyone on a local run and, deployed, the super-admin
  (`gate.is_operator`).
- **The gate** (`applydesk/gate.py`): every route but `/health` answers
  anyone on a local run and, deployed, only the platform super-admin,
  with a 404 for everyone else, until the segments that wire them.

## The Form page

The application form builder on the Form tab,
`/operator/exercises/<id>/form`. Every move works in the browser; nothing
is saved until AD2, and a reload restores the sample form. A blank exercise
shows the form's own card and one empty String card, open.

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

  Every type but Title and Description also has *Required*. An empty bound
  is left out of the summary (`Integer · up to 6`); both bounds equal read
  `exactly N`; a list with no options reads `no options yet`; a photo with
  no valid ratio reads `Photo · ratio not set`.
  A photo is kept as a JPEG 600 px on its longer side, the other side by
  the ratio, rounded half up (4:5 is 480 × 600; 1:1 is 600 × 600). *Chosen
  from* is a menu of *Institution-wide*, then the exercise's panels by name
  (`sample_data.Panel`), then *+ New panel…*. That choice opens a box under
  the row: *Panel name* and *Members*, a token box as Residential's people
  boxes are (names or emails, comma-separated, each found in the directory
  a pill with ×; one not found stays in the box with the reason), then
  *Create panel* and *Cancel*. A panel created joins every *Chosen from*
  menu on the page and Preview's lookup, and is selected; it lives on this
  page only. *Edit on Panels →* beside the menu links to the chosen panel
  on Panels, hidden for *Institution-wide* and for a panel made here. A
  panel the exercise lacks reads as *Institution-wide* on the card, in its
  summary and in Preview. Help text and descriptions grow to fit what is typed, with no
  resize handle, as does a long answer's box in Preview. Changing the type
  keeps the question, help text, *Required* and visibility, and empties the
  new type's settings: a photo's ratio starts at 4:5, a list at *Choose
  one* and Select people at *Institution-wide*.
- **Visibility** is per card: *Shown to reviewers* or *Not shown*; a new
  card is *Not shown*, the side that hides.
- **Collapsed**, a card shows its question and help text (a text card's
  title and description), the summary of its settings, and chips: *Required*
  or *Optional* (a text card has none) and its visibility. Expanded, it
  shows its fields and its buttons. Cards load collapsed, the form's own
  card too; a form with one card opens both. Several can be open at once.
  No card shows a number. A card with no question reads *Untitled
  question* (*Untitled text*, *Untitled section*).
- **Buttons** along each card's foot, flush right, in this order:
  *Replicate* (a field card only), *+ New* (an empty String card),
  *+ Section*, *+ Page break*, *Delete*. Each insert lands right after the
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
- **Keeping an edit** (ruling 23). One *Save*, in the Outline, disabled
  until AD2; an *Unsaved changes* marker beside it once anything is edited
  (a move, a toggle, an added, replicated or removed card; opening a card or
  the preview is no edit), and a warning on leaving the page with it showing.
- **Preview**, at the foot of the Outline with *Save* beside it, shows the form in place of the cards, as an applicant sees it,
  page by page, built from the cards on screen; the button reads *Back to
  edit* meanwhile. *Open the preview in a new tab*, under them, shows the
  same at `/operator/exercises/<id>/form/preview`, with *Submit* disabled.
  The tab reads the builder that opened it, so a reload picks up later
  edits; opened on its own, or once the Form page has gone to another
  exercise, it shows the sample form and says so. Both are drawn by one
  renderer. A string with a maximum of 200 characters or fewer previews as
  one line, longer or unbounded as a box; a number as a field with its
  bounds; a list as radio buttons (*Choose one*) or tick boxes; a photo as
  a frame at its ratio; "Reviewers see your answer." appears under a shown
  question. Select people previews as a box of pills, after Residential's
  Staff box: each comma-separated name or email found in its pool becomes a
  pill, one not found (or matching more than one person) stays in the box
  with the reason, a repeat is declined, and the box takes no more at the
  maximum, naming what it dropped. The pools are sample rosters;
  looking people up in Entra ID through Graph comes with the applicant's
  form (AD4). Nothing typed in a preview is kept.
- **Conditional questions** (branching) are not built: deferred, see
  `applydesk/guide/todo_master.md`.

## The Process page

The exercise's timeline as a stack of stage cards, on the Process tab,
`/operator/exercises/<id>/process` (rulings 13–16). Process sets up the whole
flow and every rule Applications applies; Form, Panels and Emails flesh out its
nodes. Every move works in the browser; nothing is saved until AD2, and a
reload restores the sample. A blank exercise shows one open card, *Stage 1*,
holding the form. The cards are drawn from `stages.plan_of`, so Process,
Applications and the Workflow card agree on load.

- **Layout.** The cards in timeline order, the Outline beside them (as
  Form's), *Save* at its foot, disabled until AD2.
- **A stage card.** *Stage name* (an empty name reads *Stage N*, by position),
  *From* and *To* dates, and *Shown to applicants*. Collapsed, it shows its
  name, dates and a summary (`Form · Outcome: Shortlist`, `2 gates`,
  `No gates`). Cards load collapsed; a lone card is open. Below, its items in
  order: the form, gates, the outcome.
- **Ruling 15, enforced as it is edited.** One stage holds the form, anywhere;
  never the form and a gate together; one outcome at most per stage; an empty
  stage is allowed. A button that would break it is disabled with the reason in
  its title: *+ Gate* on the form's stage, *+ Form* on a stage with gates or
  when another holds it, *+ Outcome* on a stage with one. `stages.problems`
  words the same rules and the Outline names any breach.
- **Buttons.** Along a card's foot, flush right: *Replicate*, *+ Stage*,
  *Delete*. Each insert lands after the card and opens. *Delete* has no
  confirmation and is disabled on the last stage. A replica leaves the form
  behind; its gates and outcome take keys of their own, and its rules and
  weights read them. Inside the card: *+ Gate* (after the last gate, before the
  outcome), *+ Outcome*, *+ Form*; each item has *Remove the form* / *the gate*
  / *the outcome*.
- **Reordering** by the card's handle, dragged or with ↑ ↓ (announcing the new
  position). Gates and outcomes are numbered by the timeline and renumber as
  cards move; the Outline and Applications' headers follow.
- **Items collapse.** A stage's items each have a head, always shown, with
  its kicker, name and chips, and a toggle for the body: a gate's state,
  results count and panel (*Panel A · 2 people*, or *No panel*); an
  outcome's release and emails; the form's state and emails. An open stage
  shows its items collapsed; an item alone in its stage, or just added, is
  open. The chips follow the edits.
- **The form item.** When it opens and closes (the stage's dates), a link to
  Form, and its *Emails* to applicants: *Receipt on submitting* and *Reminder
  to drafts*. A new form ticks the receipt only.
- **A gate.** *Name*, its *Entry rule*, *Evaluators*, *Runs as* (*A Review
  Robin session* or *Results entered here*) and its results.
  - *Evaluators* is the panel menu and *+ New panel…* box Form uses (above),
    *Edit on Panels →*, the panel's members and *Panel sees* with the gate's
    progress. A sent gate (`workflow.gate_state`: *Sent*, *Results in*) has
    its menu, *Runs as* and results fixed, and says it keeps the roster it
    was sent with.
  - *Results*: up to three (*+ Result* disabled at three), rows that read as
    Form's card summaries and edit in place. Each has a *Name*, a *Response
    field* the evaluators fill in (Integer, Decimal, List or String, with
    Min/Max/Step, Max length or Options), *Derived as*, and *From at least*
    responses (default 1; fewer and the result is none yet). **The
    derivation fixes the result's type; there is no second definition:**

    | Field | Derivation | Result |
    |---|---|---|
    | Integer, Decimal | Mean, Median | Decimal |
    | | Lowest, Highest | the field's type |
    | | Sum | the field's type, n × its bounds |
    | List | Share choosing a value | Decimal, 0 to 100 (%) |
    | | Most common | List, the field's options |
    | String | All, joined | String, for reading |
    | any | Count of responses | Integer, from 0 |
    | any, *Results entered here* | Entered here | the field as defined |

    A List is never mapped to numbers: a numeric scale is a numeric field,
    its help text saying what the numbers mean. For a Review Robin session,
    *For Review Robin* lists the fields its instrument must ask. Result 1 is
    the gate's headline.
- **The outcome.** *Name*, *Due*, *Values* (comma-separated), *Rule*, and, when
  more than one gate is in scope, the *Combined result*: a weight per gate's numeric result, as
  percentages. Scope is the gates since the previous outcome (ruling 13); the
  weights follow as gates are added, removed or moved, a new gate takes what is
  left of 100, and the item says when the gates changed. *When released*, per
  audience, *Applicants* and *Panel evaluators* each with *Update timeline*
  (the timeline they see on signing in to their participant page) and *Send
  email*. Whether it is released is set on Applications.
- **The rule editor** (*Add a rule* / *Edit the rule*, on a gate or an outcome).
  A row per condition, joined by AND, then *Then* and *Otherwise*; *Decide by
  hand* clears it. Conditions are ruling 13's and no others:

  | On | Kinds |
  |---|---|
  | A gate | Status; the applicant's last N submitted; an earlier outcome |
  | An outcome | A named gate result (`≥` / `<` a number, or *is* a list's option); entry at a gate; the combined result; an earlier outcome |

  A gate's *Then* and *Otherwise* are *Entered* / *Not entered*; an outcome's
  are its values. The item's line reads as Applications' header does
  (`stages.rule_text`), *Decided by hand* for none. A rule names columns by key,
  so moving a stage keeps its meaning. One that reads a later outcome, a gate
  outside its outcome's scope, or a column since removed; decides or compares
  with a value its target lacks; or has a count or threshold that is not a
  number, is **flagged** on its item and in the Outline, and keeps reading what
  it read (a removed column as *(removed)*) until the operator picks another.
  Weights that are not numbers or do not total 100 are flagged likewise.
  A rule or weight names a gate's *result* (`stages.result_label`, *Rating at
  Peer Review*), and Applications' headers say the same: a number (a mean,
  median, sum, count, share, or a numeric field's lowest, highest or entered
  value) is compared and weighed, a list matched, a string offered to
  neither (`stages.comparable`). Only numeric results take a weight.
- **The Outline** lists each stage by name and dates with its items beneath,
  the counts (stages, gates, outcomes) and every problem, among them a gate
  with no panel. A stage or item is a button: it opens its card and goes to
  it. *Save* and the *Unsaved changes* marker sit at its foot, kept as Form's
  are (ruling 23): *Save* disabled until AD2, a warning on leaving with
  changes pending. Nothing in it is saved.
- **Emails** (ruling 16). Process picks no template. Each email ticked, the
  form's receipt and reminder or an outcome's *Send email* per audience, is a
  template owed on the Emails page, named for its stage (*Review: Outcome -
  Applicants*, *Call for applications: Receipt - Applicants*), one section each
  in timeline order with a *Written* or *Owed* chip (`workflow.emails`). An
  outcome with an owed email is not ready to release: the Workflow card says
  which audiences' emails are not written, until it is released. Template text
  and sending come later (Emails' own segment; AD6, AD7).
- **Preview** of the Workflow card the cards describe is not built.

## The Panels page

The Setup tab for everyone on the exercise's panels (rulings 19, 20, 22, 23),
`/operator/exercises/<id>/panels`. A **panel** (`sample_data.Panel`: key,
name, members) is a named roster Apply Desk keeps: an assessment panel, the
reviewer pool, the interviewers. Form and Process hold a panel's *key*, not
its name, so a rename follows everywhere. Panels laid out as Review Robin's
roster pages: a roster card, then one full-width table. Every move works in
the browser; nothing is saved until AD2, and a reload restores the sample.
A panel made on Form or Process appears here only once saved (AD2).

- **The roster card.** *People* (the count of rows), a pill per panel with its
  count, how many panels are in use, and *Manage panels*. Problems list under
  it: an email not found in the directory, one listed twice, a panel in use
  with nobody on it.
- **Manage panels** opens a card of actions (ruling 23), where Review Robin
  has *Unlock*:
  - *Panels*: each panel's name edited in place, *Copy emails* (its addresses,
    comma-separated, to the clipboard) and *Retire*, disabled with its
    reason while a question or gate uses the panel. Each shows its count and
    *Used by* (*Gate 1: Peer Review*) or *Not used yet*; a sent panel says it
    is kept as sent.
  - *Add new panel*: *Name*, then *People* (*None: a blank panel* or *Copy
    from* a panel). A blank panel takes *Members* in the token box Form's
    *+ New panel…* has; a row is added for anyone not yet in the table.
    *Add panel* is an outline button.
  - *Upload*: *Import CSV* and *Export CSV*. The CSV has `Name`, `Email` and
    `Note` and a column per panel by name, marked for each member; people not
    found in the directory are left out and named.
  - *Cancel*, *Save* and *Close* at the card's bottom right. A rename, a
    panel added and a panel retired wait for *Save*: each is marked *not
    saved yet* (a retired panel's heading and chip struck through), and the
    columns, pills and menus follow at once. *Cancel* takes them back, with
    the rows an added panel brought (a row kept with its own ✓ stays); neither
    closes the card. Enter in a name box is *Save*, Esc puts that name back.
    *Close* asks first while any waits. *Copy emails* and the CSV act at once.
- **The table.** *Filter* (matches name, email, note and the names of the
  panels a row is on; a row being edited stays in view) and *Add new*, which
  opens a blank row at the top (an imported row joins the end). *Show
  columns:* has a chip per panel, pressed while its column shows. Columns:
  a select box, *Name*, *Email*, *Note*, one per panel and a ✓ and × column;
  *Name*, *Email* and *Note* sort with ↕. A panel's heading carries its count
  and a *Sent* chip when sent; its tooltip says *Used by* or *Not used yet*.
  Widths are fixed, so selecting a row moves nothing.
- **Editing a row** (ruling 22; how Panels keeps an edit, ruling 23). A row
  is inert until its box is ticked: then its cells are edit boxes and its
  panel ticks live. Several rows may be ticked at once. ✓ at the row's end
  (Enter too) keeps its changes on the page; unticking without ✓ puts the row
  back, and a new row never kept goes. A verified email, found in the
  directory, is a pill, clicked to change it; unticked it reads as text, red
  when the directory has no such person. There is no page *Save*.
- **Checks.** An email is required, found in the directory and listed once.
- **A sent gate** (`workflow.gate_state`: *Sent*, *Results in*) keeps the
  roster it was sent with: its panel says so here and on Process.

## The Applications page

A control surface (ruling 23), worked down its columns. The whole table is
locked until *Unlock*; then every cell, *Set ticked rows*, *Apply rules…*,
*Upload CSV* and each outcome's *Released* are live. *Lock* keeps what
changed; *Undo changes* puts the table back as it was when unlocked; meanwhile
a count of the changes shows, and leaving the page with any pending asks
first. Ticks only choose rows. The page has no *Save*; nothing is kept until
AD2.

## The Emails page

Every template the exercise owes (see Process, "Emails"). Each template card
stands alone and has its own *Save*, disabled until AD2; the page has none.
