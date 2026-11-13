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
  icon, the workspace's top line over the area, a switcher of the
  *Operator Lobby* (`/operator/exercises`, operators only) and the *User
  Lobby* (`/me`) then *All applications*, the Light/Dark toggle and the
  account menu. Each lobby's H1 and tab read its name, as Review Robin's
  do (author, 2026-11-13). An exercise's operator pages add Review Robin's chrome
  under a breadcrumb (ruling 14, segment AD1D): *Exercise Home*
  double-height on the left; a Setup row (Process, Form, Gates, Emails)
  and an Operations row (Applications, Evaluations, Extract data); and a
  status row of the exercise, its form, gates, outcomes, emails and
  applications.
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
  from* is *Institution-wide* or a roster of the exercise: an assessment
  panel, the reviewer pool or the interviewers. A pool the exercise has no
  roster for reads as *Institution-wide* on the card, in its summary and in
  Preview. Help text and descriptions grow to fit what is typed, with no
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
- **Preview**, at the foot of the Outline with *Save* (disabled until AD2)
  beside it, shows the form in place of the cards, as an applicant sees it,
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
flow and every rule Applications applies; Form, Gates and Emails flesh out its
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
- **The form item.** When it opens and closes (the stage's dates), a link to
  Form, and its *Emails* to applicants: *Receipt on submitting* and *Reminder
  to drafts*. A new form ticks the receipt only.
- **A gate.** *Name*, *Runs as* (*A Review Robin session* or *Results entered
  here*), *Result* (its measure), its *Entry rule*, and a link to Gates for its
  panel.
- **The outcome.** *Name*, *Due*, *Values* (comma-separated), *Rule*, and, when
  more than one gate is in scope, the *Combined result*: a weight per gate, as
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
  | An outcome | A gate's result (`≥` / `<` a number); entry at a gate; the combined result; an earlier outcome |

  A gate's *Then* and *Otherwise* are *Entered* / *Not entered*; an outcome's
  are its values. The item's line reads as Applications' header does
  (`stages.rule_text`), *Decided by hand* for none. A rule names columns by key,
  so moving a stage keeps its meaning. One that reads a later outcome, a gate
  outside its outcome's scope, or a column since removed; decides or compares
  with a value its target lacks; or has a count or threshold that is not a
  number, is **flagged** on its item and in the Outline, and keeps reading what
  it read (a removed column as *(removed)*) until the operator picks another.
  Weights that are not numbers or do not total 100 are flagged likewise.
- **The Outline** lists each stage by name and dates with its items beneath,
  the counts (stages, gates, outcomes) and every problem. A stage or item is a
  button: it opens its card and goes to it. Nothing in it is saved.
- **Emails** (ruling 16). Process picks no template. Each email ticked, the
  form's receipt and reminder or an outcome's *Send email* per audience, is a
  template owed on the Emails page, named for its stage (*Review: Outcome -
  Applicants*, *Call for applications: Receipt - Applicants*), one section each
  in timeline order with a *Written* or *Owed* chip (`workflow.emails`). An
  outcome with an owed email is not ready to release: the Workflow card says
  which audiences' emails are not written, until it is released. Template text
  and sending come later (Emails' own segment; AD6, AD7).
- **Preview** of the Workflow card the cards describe is not built.
