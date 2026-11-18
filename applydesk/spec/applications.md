# Apply Desk as the host sees it

> **Built so far:** segment AD1 built "The registry entry", "Health",
> "Running alone" (item 1) and "The URL map" as placeholders on sample
> data (item 2), pending the author's approval in a browser. Segment AD1B
> built "The Form page" as a working scaffold: every move works on screen,
> nothing is saved. Segment AD1E built "The Process page" the same way,
> with Emails listing the templates it makes owed (ruling 16). Segment AD1K
> gave each stage a status and made a published stage's contents fixed on every
> page that shows them (ruling 35), the same way: on the sample, nothing saved.

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
- **The dossier**, what an evaluator opens, one per application
  (`/me/exercises/<id>/dossiers/<dossier>`), is named by its own ID, never the
  application's, and shows only the *Shown to evaluators* section. In a blind exercise it
  redacts the applicant's name and identifiers. It and the applicant's own
  application page read the Form's questions (text blocks aside), grouped
  by visibility in the Form's order, with the answers Extract writes, *—*
  where there is none (`extract.form_answers`); the title is the page's
  heading alone.
- **The chrome** is the shared bar (`docs/header_chrome.md`): the app
  icon, the workspace's top line over *Apply Desk* (the app's name, as
  Review Robin's bar names Review Robin; author, 2026-11-13), a switcher of the
  *Operator Lobby* (`/operator/exercises`, operators only) and the *User
  Lobby* (`/me`) then *All applications*, the Light/Dark toggle and the
  account menu. Each lobby's H1 and tab read its name, as Review Robin's
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
- **Visibility** is per card: *Shown to evaluators* or *Not shown*; a new
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

## Exercise Home

Home, `/operator/exercises/<id>`, is two columns: the **Timeline** card
(two-thirds) and the **Details** card (one-third), one column from 899px down,
Details below. The status row (`workflow.status_row`) opens with the exercise's status,
derived from its stages ("Stage status"), and carries *Applications: N
submitted · M drafts*. Under the timeline a *Next step* line says where
today falls (`timeline.next_step`), with *Go to Gate N*, its page under Evaluations, while a gate runs
(`timeline.running_gate`). Home has no Publish card: publishing is per stage,
on Process, and the timeline's operator part says what blocks each stage.
Cards side by
side share a height only when within a fifth of the taller; a short card
beside a much taller one keeps its own.

### The timeline

Drawn from Process's stages by `applydesk/timeline.py` (the participant-safe
adapter) through the partial `applydesk/templates/applydesk/_timeline.html`,
which Home and the applicant's exercise page (`/me/exercises/<id>`) both
include.

- **Stage**: name, dates and a state. *Done* when its last date has passed
  (*Closed* for the stage holding the form), *Now* when today falls within it,
  *Next* otherwise (the calendar's, apart from the stage's status); a stage with no (or impossible) dates is *Next* and reads
  *Dates not set*. Today is the sample's until AD2, marked on the current
  stage at its share of that stage's days and said in words, between stages
  too.
- **Items**: the form as *You*, its close as a *Milestone*, each gate as a
  *Step* by name (*A step.* unnamed), each outcome by name with *released
  <date>* or *expected <the exercise's expected outcome>*. Outcome values
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
  stages), to the right of each stage (Vertical), under the items on a phone,
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
  (`sample_data.my_applications` until AD2).
  Under each, every outcome released to applicants gives *Your result*
  with the applicant's own value and when (`stages.released_results`; the
  application page lists them as *Your results*); AD7 sends them. `/me`
  shows Published and Closed exercises (ruling 41): a Closed one stays,
  read-only, its *Apply* saying it is closed; Draft and Archived do not,
  and their application and dossier pages answer 404 (author, 2026-11-18).
  *Your results* is the applicant's own: another application's page shows none.
  A submitted application may be withdrawn (*Withdraw*, Outline-amber, with a
  confirm, AD4) until a gate holding its dossier is sent; then the page names the
  gate it has gone to (`workflow.closed_by`, ruling 45).
  Closing and archiving themselves are not built (AD3).
  A stage left unticked in Process's *Shown to applicants* is not on it
  (`Stage.shown`, ruling 46); the operator's Home shows every stage.

### Details

Name, Exercise code, Description (`Exercise.summary`), Help contact,
Timezone, Who may apply and Blind review, locked until *Unlock*. A Help
contact or Timezone left unset reads the operator settings' default
(`DEFAULT_HELP_CONTACT`, `DEFAULT_TIMEZONE`) followed by *· the default*
(`help_contact(e)` / `timezone(e)`, template globals in `applydesk/web.py`).
Unlocked, each is a field with a line saying where it is used.

- *Lock* keeps the changes on the page; *Discard changes*, or Esc, restores
  the last kept values, saying *Changes discarded.* only when something
  changed. *Unsaved changes* shows, and the browser warns on leaving, from
  any change since load.
- *Lock* refuses an empty Name, an Exercise code another exercise holds (any
  case, saying whose) and a Help contact that is not an email address. The
  Timezone is chosen from `sample_data.TIMEZONES`, the default first.
- A published exercise's Exercise code and Who may apply are fixed, saying
  so; changing them waits for re-publishing (G2).
- **Blind review** is fixed, with its reason, once the first stage holding a
  gate is published (`locks.blind_lock`).
- Nothing is saved until AD2: a reload restores the sample. Process shows
  Help contact and Timezone read-only.

## The Process page

The exercise's timeline as a stack of stage cards, on the Process tab,
`/operator/exercises/<id>/process` (rulings 13–16). Process sets up the whole
flow and every rule Dossiers applies; Form, Panels and Emails flesh out its
nodes. Every move works in the browser; nothing is saved until AD2, and a
reload restores the sample. A blank exercise shows one open card, *Stage 1*,
holding the form. The cards are drawn from `stages.plan_of`, so Process,
Dossiers and the status row agree on load. There is no Workflow card:
ruling 14's was removed (author, 2026-11-15: derivative of the other
pages, it can wait); `workflow.steps` still names the current stage.

- **Layout.** The cards in timeline order, the Outline beside them (as
  Form's), *Save* at its foot, disabled until AD2.
- **A stage card.** *Stage name* (an empty name reads *Stage N*, by position),
  *Starts* and *Ends*, and *Shown to applicants*. Collapsed, it shows its
  name, dates, status chip and a summary (`Form · Outcome: Shortlist`,
  `2 gates`, `No gates`). Cards load collapsed; a lone card is open. At its
  head, its status box ("Stage status"); below, its items in order: the form,
  gates, the outcome.
- **Dates are typed** (author, 2026-11-18). A stage's *Starts* and *Ends* are
  date-time inputs (`stages.StageDates`, in the exercise's time zone; a bare
  day's end is its last minute, 23:59); an empty or reversed pair is no dates.
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
  cards move; the Outline and Dossiers' headers follow.
- **Items collapse.** A stage's items each have a head, always shown, with
  its kicker, name and chips, and a toggle for the body: a gate's state,
  results count and evaluators (*Nominated 0–2 · Panel A 1–3 · Total 3*, or
  *No evaluators*; amber on a problem); an
  outcome's release and emails; the form's state and emails. An open stage
  shows its items collapsed; an item alone in its stage, or just added, is
  open. The chips follow the edits.
- **The form item.** When it opens and closes (its own dates, else the
  stage's), a link to Form, and its *Emails* to applicants: *Receipt on submitting* and *Reminder
  to drafts*. A new form ticks the receipt only.
- **A gate** is one Review Robin run (ruling 28), in four parts, in this
  order. The *Gate* and *Evaluators* cards are collapsible, start shut and
  say what they hold on their summary line (`stages.gate_summary`,
  `evaluators_summary`); a new gate, and an Outline jump to one, open the
  *Gate* card for its name. Its window is its own dates, else the stage's.
  The gate is *fixed* once its Review Robin session has opened
  (`workflow.gate_opened`: *Results in*, or *Sent* with its session under
  way): every control in it is disabled and a line says so, a revert of its
  stage leaving it so (ruling 29). Sent but unopened, it is still changed
  here, each change re-sent, unless its stage is published ("Stage
  status").
  - **Gate**: *Name*; *Type* (a disabled menu, *Review Robin session*, kept
    for other kinds); *Description* (Review Robin's instrument description);
    *Confidential* (per gate: Review Robin shows each applicant as *Name
    redacted* with their Dossier ID); the *Entry rule*. The exercise's *Help
    contact* and *Timezone* show read-only, linking to Home, where they are
    set: they are Review Robin's for every gate.
  - **Evaluators** (ruling 27): a row per ranked **source**, in order
    (▲ ▼; a row's **+** adds the next, × removes; *+ Source* shows only
    when there is none), each a *Kind*, its *Min* and *Max* per dossier:
    - *Nominated*, the people a applicant named in a *Select people*
      question of Form, picked by its label, offered only when the form has
      one; or
    - *Panel*, by the shared menu and *+ New panel…* box Form uses (above)
      with *Edit on Panels →*; a panel's members are on Panels, not listed.

    Then the **Total**: its *Min* and *Max*, with the bounds the sources allow
    (their mins together, their maxes together) beside it. A Total outside
    them is a problem on the Outline, never silently clamped
    (`stages.total_problem`). The Outline also names a gate with no source,
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
    each, edited in place: *Label*, *Type* (Integer, Decimal, List or
    String, with Min/Max/Step, Max length or Options), *Required*, and *Help*
    (shown under the field in Review Robin); *+ Field*, *Remove the field*.
    Each shows its **Key**, read-only: what Review Robin reports the field's
    answers under. A new field takes `f<n>`, the first not in use on the gate.
    A gate with none lists one per result.
  - **Results**: up to three (*+ Result* disabled at three), rows that read
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
- **The outcome.** *Name*, *Due* (a date-time, blank for the stage's end), *Values* (comma-separated), *Rule*, and, when
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
  *+ Condition* and *Then*; *+ Else if* adds a branch, *Remove branch* drops
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
  (`stages.rule_text`), *Decided by hand* for none. A rule names columns by key,
  so moving a stage keeps its meaning. One that reads a later outcome, a gate
  outside its outcome's scope, or a column since removed; a form question gone from Form, or an answer
  not among its options; a best N that is not a whole number or ranks by a
  result that is not a number; decides or compares
  with a value its target lacks; or has a count or threshold that is not a
  number, is **flagged** on its item and in the Outline, and keeps reading what
  it read (a removed column as *(removed)*) until the operator picks another.
  Weights that are not numbers or do not total 100 are flagged likewise.
  A rule or weight names a gate's *result* (`stages.result_label`, *Rating at
  Peer Review*), and Dossiers' headers say the same: a number (a mean,
  median, sum, count, share, or a numeric field's lowest, highest or entered
  value) is compared and weighed, a list matched, a string offered to
  neither (`stages.comparable`). Only numeric results take a weight.
- **Stage status** (ruling 35; author, 2026-11-18). Each stage is *Draft*,
  *Published*, *Overdue* or *Completed* (`locks.stage_status`); the operator
  declares only Draft and Published (`Stage.status`), the rest follow from its
  end and its items, against the sample's now (`locks.NOW`; the page's script
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
    audited at AD2), from the last published stage back, so no Draft precedes a
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
  are (ruling 23): *Save* disabled until AD2, a warning on leaving with
  changes pending. Nothing in it is saved.
- **Emails** (ruling 16). Process picks no template. Each email ticked, the
  form's receipt and reminder or an outcome's *Send email* per audience, is a
  template owed on the Emails page, named for its stage (*Review: Outcome ·
  Applicants*, *Call for applications: Receipt · Applicants*), one section each
  in timeline order with a *Written* or *Owed* chip (`workflow.emails`). An
  outcome with an owed email is not ready to release. `workflow.steps`
  records which audiences' emails are not written, but no page shows it
  until a Workflow card returns; meanwhile the *Owed* chips and the status
  row's Emails pill do. Template text and sending come later (Emails' own
  segment; AD6, AD7).
- **Preview** of the timeline the cards describe is not built.

## The Panels page

The Setup tab for everyone on the exercise's panels (rulings 19, 20, 22, 23),
`/operator/exercises/<id>/panels`. A **panel** (`sample_data.Panel`: key,
name, members) is a named roster Apply Desk keeps: an assessment panel, the
evaluator pool, the interviewers. Form and Process hold a panel's *key*, not
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
    *Used by* (*Gate 1: Peer Review*) or *Not used yet*; a panel an opened
    gate uses says that gate keeps it.
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
  - Whatever ✓, ×, *Save* or an import changes is on the page only: ✓ says
    *kept on this page* (*nothing changed* on an untouched row), the page
    shows *Changes on this page, not saved until AD2*, and leaving asks
    first, as it does while a ticked row holds changes ✓ has not kept. ×
    on a member of a panel an opened gate keeps (as kept, not as ticked
    while editing) asks before removing them.
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
- **An opened gate** (`workflow.gate_opened`: its Review Robin session has
  opened, ruling 29) keeps the roster it opened with: its panel says so here,
  with an *Opened* chip, and on Process. Every panel source of a gate counts
  (`stages.gate_panels`), for *Used by* and the *Retire* guard too.

## The Dossiers page

At `/operator/exercises/<id>/dossiers` (the Applications page until ruling
25): a row per dossier, an application's where it has one; until dossiers
are made (*Create dossiers*, ruling 26), the rows are the sample's
applications.
A control surface (ruling 23), worked down its columns. The whole table is
locked until *Unlock*; then every cell, *Set ticked rows*, *Apply rules…*,
*Upload CSV* and each outcome's *Released* are live, but for the fixed ones
below. *Lock* keeps what
changed; *Undo changes* puts the table back as it was when unlocked; meanwhile
a count of the changes shows. Locked, what differs from the page as loaded
stays marked (*N changes on this page, not saved until AD2*), and leaving the page with any pending or
kept asks first. *Return to draft* is a submitted row's own (Outline-amber)
until a gate holding its dossier is sent, as withdrawal is, and *Return
ticked to draft* the ticked rows', gates or none (ruling 45; both AD4). Ticks
only choose rows; the *Application* header's tick ticks every
row in view, or clears them, and *Set ticked rows* with none ticked says *No
rows ticked*. *Download CSV* writes the rows in view in the shape *Upload
CSV* reads, a cell a spreadsheet would run as a formula guarded with `'` (a
lone `-`, no status, is not), named `<code>_dossiers_<date>.csv`; *Upload
CSV* undoes the guard. The page has no *Save*; nothing is kept until AD2.

*Apply rules…* proposes each outcome and gate cell from the rule Process
holds (branches in order, a form answer from the application's answers, the
best N), as a proposal the operator approves (Esc is its *Cancel*); a hand-set cell is kept unless
*Also replace cells set by hand* is ticked. An outcome whose gates a dossier entered none of is not reached
and stays as it is, unless its cell is already open (*Pending* or decided) or
a branch of its rule reads earlier outcomes' values alone and they hold, set
by hand or by the same run: re-appointment skips the interview and still
reaches *Selection*. An outcome's **going-on values** are every one but its
last (`stages.going_on`; *Re-appointment* and *Interview*, not *Not
shortlisted*): each is counted in its column head and toned green, the rest
muted, undecided amber. A mean's note under its chip says how many scores it
took (`stages.mean_note`).

- **A gate's cells are fixed once its Review Robin session has opened**
  (`locks.cells_lock`; entry flips there change who the results cover). The
  column says so, its cells stay disabled when the table is unlocked, and
  *Set ticked rows*, *Apply rules…* and *Upload CSV* skip them, naming what
  they skipped. A gate whose stage is published but not yet opened keeps live
  cells: entering applications is that stage's work while it runs.
- **Released waits on its emails** (`locks.release_lock`): the switch is off,
  with the reason, while an email the release sends is owed on Emails, and a
  release withdrawn waits on them to be made again. Before a release, the
  dossiers it reaches that are still undecided or *Pending* are counted; a
  row none of whose gates entered it is not reached, unless a branch of the
  rule reads earlier outcomes alone and they hold.

## The Evaluations page

At `/operator/exercises/<id>/evaluations`: the **Gates** table (gate, type,
state, progress, and *Send to Review Robin* / *Pull results*, disabled until
the later segment that sends), then **Assignments**, a short card per gate:
its mode, its counts (*42 dossiers · 40 filled · 2 short*, over every pair),
its load line per panel source (*Ana 6 · Ben 5 …*) and a link, *Assignments
(n rows)*, to the gate's own page. A draft exercise shows neither. Nothing is
saved until AD2; a reload restores the sample.

**The gate page**, `…/evaluations/gate_<n>` (`routes_operator.gate_evaluations`),
404 for a gate the exercise lacks or a draft exercise. Its breadcrumb runs
Exercise / Evaluations / *Gate n · label*. The gate's head (its
state chip, as Evaluations' Gates table, its mode and counts, and its
disabled *Send to Review Robin* or *Pull results*, AD6), its load lines and a table with **a row per pair**,
*Applicant*, *Evaluator*, *Source*, *State*; a dossier with no evaluator yet
is one row, *None yet*. A blind exercise, or a confidential gate (ruling 42),
shows the dossier ID as the applicant, and is searched and sorted by it. The pairs are `stages.assignments`, drawn as the gate's mode and
sources fill them. A gate can pair 30 evaluators with 100 dossiers, so the
table is paged and queried in the URL (`offset`, `q`, `sort`), and a link
keeps all of them.

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
| Automatic | every dossier filled as its sources give | *Re-run* (back to the fill) |
| Suggested, then approved | the fill, each pair *Suggested* | *Approve* a pair, *Approve all*, *Remove* (then *Undo*), *+ Pair* |
| Assigned by the operator | empty, every dossier *Not assigned* | *+ Pair*, *Remove* |

- **Kept in the tab.** Changes live in `sessionStorage` under
  `applydesk-ev:<exercise>:<gate>:<mode>`, so paging, sorting and searching
  keep them; *Changes in this tab, not saved until AD2* and *Discard
  changes* show while any exist,
  and Discard puts the sample back. Leaving the gate's pages with any asks
  first, a reload included, since the browser cannot tell a reload from
  closing the tab, which loses them; its own pager, sort and filter do
  not. On load they are reconciled against the
  sample, the mode and the limits: a stale pair, an approval the mode lacks or
  an addition past a limit is dropped.
- **+ Pair** opens a panel to choose a dossier and an evaluator. The
  evaluators offered are the gate's panel members less the applicant and
  those already on the dossier; it refuses a pair that would pass the
  Total's max or the source's max, saying why. **Undo is held to the same
  limits** and says why it did not undo. An added pair shows on the first page
  only, and under a filter only if it matches; removing it takes its approval
  with it, while Undo keeps an approval.
- **Off** once the gate's session has opened (`workflow.gate_opened`: its
  pairs are Review Robin's to change), with the reason in each button's title;
  and off until the page's script has run.
- **A blind or confidential gate's + Pair** still never offers an applicant
  as their own evaluator: the page's data names no applicant, but gives each
  dossier the one panel member it may not take, its applicant when they sit
  on the gate's panels (author, 2026-11-18). AD2's server checks it again.

The model exercise, *Recruitment and Selection of Residential Assistants*
(`wa9juxbc2t`), has gates that pair a panel of 30 with every applicant, so
the paged table is exercised there.

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
  setup's pages) is a `.pn-show` pill, a one-of choice a `.seg` (ruling 47).
  Each viewer's are kept in `localStorage` `applydesk-extract-<id>`; with storage blocked, or no script,
  the defaults apply. *Zip all*'s link also takes the other cards' settings
  (Applications' rows and drafts, By gate's shape, Outcomes' rows, Extract
  setup's pages) so the ZIP carries each file as its card is set.
  While its files line names only `manifest.csv` (nothing carried, or Setup
  carried with every setup page off), *Zip all* is off, titled *Tick a file
  to carry first*.

| Card | Chips (default first) | Download |
|---|---|---|
| Extract all data | *Carries*: Applications, Gates, Outcomes on; Setup off. *Applicants as*: Names, Dossier IDs | *Zip all* |
| Applications | *Rows*: Last applications, All applications. *Drafts*: Left out, Included | *Download CSV* |
| By gate | *Shape*: A row per pair, A row per application. *Applicants as*: Dossier IDs, Names | a *CSV* per gate; *Zip gates* |
| Outcomes | *Rows*: Last applications, All applications | *Download CSV* |
| Alias key | none | *Download key* |
| Extract setup | *Carries*: Form, Process, Panels, Emails, all on | *Zip setup* |

- **The route** `GET /operator/exercises/<id>/extract/<file>`
  (`routes_operator.extract_file`, `applydesk_extract_file`; 404 for an
  unknown exercise or file). Files: `applications.csv`, `outcomes.csv`,
  `alias_key.csv`, `gate_<n>.csv`, `gates.zip`, `all.zip`, `setup.zip`.
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
    per form question by its label, in the form's order (a section, page
    break or text block no column). *Last applications* is each applicant's
    last submitted one (Dossiers', ruling 13); *All applications* every
    submitted one; *Drafts* adds drafts, never a withdrawn application. It
    always names its applicants. A list answer is one cell, items joined by
    `; ` (Select people: the nominees); a photo its file name. Where the
    sample holds no answer, one is seeded per application and question, the
    same every time.
  - **`gate_<n>.csv`**, downloaded as `gate_<n>_<slug>.csv` (the gate's name
    in lower case, other runs as `_`): *A row per pair* is `dossier_id`
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
    `panels.csv` (panel, name, email, note); `emails.csv` (each template
    owed and whether it is written).
- **The ZIPs.** Named `<code>_<kind>_<date>.zip` (the Exercise code, or the
  ID if none, as a file-name slug; today's date; kind `extract`, `gates` or
  `setup`), each with `manifest.csv` first: a row per file with its row
  count, then a row per gate left out with the note *Not sent*. *Zip all*
  holds `applications.csv`, each sent gate's file, `outcomes.csv`, and with
  *Setup* the pages Extract setup's chips leave on, under `setup/`. *Zip
  gates* holds the sent gates' files.
- **Empty and Draft.** With no submitted applications one line above the
  cards says so (adding, for a Draft exercise, that only its setup can be
  extracted), and every download but *Zip setup* is off; *Zip setup* works
  for a Draft too, as it needs no applications. *Zip gates* is off while no
  gate is sent. An exercise with no gates says so in *By gate*.

## The Emails page

Every template the exercise owes (see Process, "Emails"). Each template card
stands alone and has its own *Save*, disabled until AD2; the page has none.
