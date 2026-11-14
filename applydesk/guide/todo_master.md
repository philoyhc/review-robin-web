# ApplyDesk — rulings and open work

Open work only, as RRW's `guide/todo_master.md`. The functional baseline
is `applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md`;
where a ruling below differs from it, the ruling wins.

## Rulings (author, 2026-11-12)

1. **No native assessment engine in the MVP.** Assessment runs in Review
   Robin: ApplyDesk pushes rosters to it and pulls results back, on the
   handoff that segments 23A and 23B proved (`spec/handoffs.md`). The
   spec's native assessor instruments, panels and assessor CSV import
   (§4.1, §7.6–§7.8) are not built for the MVP.
2. **Referees are native to ApplyDesk, but set aside** until the Blob
   storage questions are settled with IT (spec §5.3, G8).
3. **No uploads in MVP applications**: form answers only. Attachments
   come with Blob storage, alongside referees.
4. **ApplyDesk keeps the roster of recognized assessors and referees, and
   what each may view.** To Review Robin they are ordinary reviewers; it
   holds no ApplyDesk authorization.
5. **Reviewers read an application on ApplyDesk's application file**
   (the profile page, renamed by ruling 13), linked as each reviewee's `ProfileLink` in the handoff.
   ApplyDesk decides each view itself, from the signed-in Cordware
   identity and its own roster. The page shows only the *Shown to
   reviewers* section.
6. **Blind review is possible**: in a blind exercise the application file
   redacts the applicant's name and identifiers.
7. **Every exercise has a 10-character public ID**, in RRW's alphabet
   (`app/db/models/review_session.py`, `PUBLIC_ID_ALPHABET`).
8. **The URL map follows RRW's.** Operators work under
   `/applydesk/operator/exercises` and
   `/applydesk/operator/exercises/<id>/…`; participants under
   `/applydesk/me` and `/applydesk/me/exercises/<id>/…`.
9. **A reviewer opens only the application files of the applications they are
   asked to review** (AD5). ApplyDesk's roster holds that permission.
   **The exercise's operators open every application file** (author, 2026-11-12).
   How the same pairs reach Review Robin's assignments, through reviewer,
   reviewee or relationship tags, is decided at AD6.
10. **A blind exercise sends Review Robin an alias key** in place of the
    application ID, minted per handoff and mapped back only by
    ApplyDesk (AD6), since RRW shows `RevieweeEmail` under each name.
11. **The operator's pages are Home, Setup, Form, Applications, Panels,
    Review and Reports** (author, 2026-11-12; *the tabs superseded by
    ruling 14*: Process, Gates, Evaluations and Extract data take them). Home shows the timeline and
    the current stage; Setup holds the timeline's setup; Form builds and
    previews the application form; Applications generates application
    files (ruling 13). **Panels holds the rosters ApplyDesk keeps (ruling 4)**:
    assessment panels, a reviewer pool applicants choose from on the form,
    and interviewers. Ruling 1's "panels" are the native assessment
    engine's, still out of the MVP; these are rosters. **Reports collates
    every evaluation response**, Review Robin's included, beside the data
    export.

12. **A photo is a question type in the MVP** (author, 2026-11-12): the
    one upload ruling 3 allows, since it needs no Blob storage (the
    applicant frames it, the server keeps a re-encoded JPEG;
    `applydesk/docs/photo_field_design.md`). Its aspect ratio is set per
    question.

13. **Evaluation runs in rounds of gates and outcomes, driven from the
    Applications page** (author, 2026-11-12; *rounds and the timeline's
    stages became one, the stage, in ruling 15*):
    - A **round** is sequential; a round holds one or more **gates**,
      which may run at the same time. A gate is who evaluates (a Panels
      roster), what they see (which sections), how (a Review Robin
      session, or results the operator enters), who enters, and a window
      of dates.
    - An **outcome** (shortlisted, finalist, awarded …) sits after a
      gate or at the end. It is a point on the Timeline, with its own
      date; each outcome has a *Released* switch, and what a release does
      (to applicants, to reviewers, by email) is set with the Timeline.
    - Rounds, gates, outcomes and their dates are set up on **Setup**
      and the Timeline (*stages, on Process: rulings 14, 15*). **Applications** is the control surface: who
      enters each gate (*—* for no status yet, *Entered*, *Not entered*;
      author, 2026-11-13) and each
      outcome's value, set by hand, by the column's rule, or uploaded as
      a CSV keyed by application ID. **Rules are set on Setup, not here**
      (author, 2026-11-13): Applications applies them, and the operator
      overrides any cell by hand. A gate's rule reads the application's
      status, whether it is the applicant's last submitted, and earlier
      outcomes, never another gate; an outcome's reads the gates in its
      scope (those since the previous outcome) and earlier outcomes. An
      outcome may be a function of its gates' results: a weighted
      average (e.g. 30% / 70%), a gate not entered dropping out and the
      rest re-weighted; conditions combine with AND. A rule or an upload
      is a proposal the operator reviews before saving.
    - ~~The word **stage** stays with the exercise's timeline (Setup,
      Application, Review …); evaluation steps are **rounds**.~~ One word,
      the **stage**, since ruling 15.
    - An applicant may send more than one application; the page shows
      all of them, or each applicant's last **submitted** one.
    - What a reviewer opens is the **application file**, one per
      application (ruling 5's "profile page"); it keeps its own ID apart
      from the application ID, for ruling 10's blind exercises.
14. **An exercise's pages follow the operator's workflow, in Review
    Robin's chrome** (author, 2026-11-13; segment AD1D):
    - **Home**, then a **Setup** row: *Process* (stages, gates, outcomes,
      dates, every rule, what a release does), *Form*, *Gates* (one card
      per gate, its panel roster on it; *a panel picked from Panels: ruling 19*), *Emails* (every template to
      applicants, kept in one place; Process sets which steps send one,
      and when; *who it is to and how templates are named: ruling 16*); then
      an **Operations** row: *Applications*, *Evaluations* (each gate's
      progress and results), *Extract data*. Panels folds into Gates,
      Review becomes Evaluations, Reports becomes Extract data, Setup
      becomes Process. Ruling 13's "Setup and the Timeline" is Process.
      *Panels came back as its own tab after Gates: ruling 19; Gates
      folded into Process, Panels in its slot: ruling 20.*
    - **Each item goes live on its own**: the form (*Draft → Open →
      Closed*), each gate (*Not ready → Ready → Sent → Results in*), each
      outcome (*Pending → Decided → Released*), then the exercise is
      closed and archived. An item locks when it goes live; the rest
      stays editable, so a later gate can be set up just in time.
    - **A Workflow card** on Home and every Operations page steps
      through them in timeline order, the next one carrying its action
      and what blocks it; there is no Validate tab.
15. **The exercise's timeline is built of stages** (author, 2026-11-13;
    segment AD1D), one word for ruling 13's rounds and the timeline's
    stages:
    - A **stage** has dates and a name the operator gives it, *Stage N*
      until then. Stages run one after another.
    - A stage holds **the form** (the application form: *Form* names
      what a stage holds, so *application* means only the record an
      applicant submits; author, 2026-11-13), or **one or more gates**,
      and may hold an **outcome**: never the form and a gate together.
      Only one stage holds the form, anywhere in the timeline (a
      gate stage may come first, its outcome deciding who may apply); an
      exercise may have none, its applications collected upstream and
      loaded into the Applications table. A stage may hold only an
      outcome: an offline gate, as the model exercise's *Decision*,
      where the reviews and interviews are collated for discussion
      before the final decision.
    - **An outcome is optional** (author, 2026-11-13): it officially
      notes a result that updates the timeline, and may tell reviewers,
      applicants and others. It sits naturally in the stage whose gates
      it is based on, though it need not: the sample could equally run
      Application, Review, Shortlist for interview, Interview, Finalists,
      Decision, each outcome a stage of its own.
    - **Next extension, not the MVP: one application in parts**
      (author, 2026-11-13). An exercise has one application per applicant,
      which may come in parts across stages: the stage holding the
      application creates it, and later form stages add a part (a full
      proposal after an expression of interest, a finalist's budget or
      referees, an award's acceptance). A later form stage admits by an
      earlier outcome, as a gate does, and opens its form only to those;
      its Applications column runs *Not invited → Invited → Draft →
      Submitted*; Form picks between the forms; the application file
      joins the parts. Until then, ruling 15's one application stage
      stands; each form-holding stage names its form and an application
      keeps a status per part, so the extension adds without reworking.
    - The sample's stages are *Call for applications*, *Review*,
      *Interview* and *Decision*. The exercise's current stage is worked out from the
      timeline (the one holding its next step), not stored. Setup (a
      draft) and Close are the exercise's state, not stages.
    - **Process is a stack of stage cards**, as Form is of question
      cards: a new exercise starts with one stage card offering the
      form and an outcome (an outcome is optional: the sample's
      Call for applications has none); stages are added, moved and deleted,
      but the last one cannot be deleted.
16. **Process says who is emailed; Emails lists every template owed**
    (author, 2026-11-13; segment AD1E):
    - On **Process** an item ticks whom it emails and never picks a
      template: the form, its applicants' receipt and reminder; an
      outcome's release, *Applicants* and *Panel evaluators*, each with
      *Update timeline* (the timeline they see on signing in to their
      participant page) and *Send email*.
    - **Emails** lists one template for each item and audience ticked,
      named for its stage: *Review: Outcome - Applicants*, *Review:
      Outcome - Panel evaluators*, *Call for applications: Receipt -
      Applicants*. Each is *Written* or *Owed*; an outcome with one owed
      is not ready to release.
    - So Process is set up in full without visiting Emails first; the
      templates are written after, against the list it makes.
17. **The name is *Apply Desk*** (author, 2026-11-13), two words, as
    *Review Robin* and *Support Logs* are. It is what every page, title
    and spec says. The URL, the package and every identifier stay
    `applydesk`. New prose writes *Apply Desk*; older plans and docs keep
    *ApplyDesk* until edited, as the US-spelling rule handles a word.
18. **Apply Desk's lobbies are Review Robin's** (author, 2026-11-13): the
    switcher offers the *Operator Lobby* (`/operator/exercises`, operators
    only) and the *User Lobby* (`/me`), each page titled so; `/` and
    `/operator` land by role. Until AD2 knows Apply Desk's operators, an
    operator is everyone on a local run and the super-admin deployed.
19. **Panels is its own Setup tab, after Gates** (author, 2026-11-13;
    segment AD1F), superseding ruling 14's fold of Panels into Gates:
    - The Setup row is *Process · Form · Gates · Panels · Emails*
      (*Process · Form · Panels · Emails* since ruling 20). A
      **panel** is a named roster of people kept by Apply Desk (ruling 4):
      an assessment panel, the reviewer pool, the interviewers.
    - **Form and Gates pick a panel** where they need one (a *Select
      people* question's *Chosen from*, a gate's evaluators), and may make
      one there: *+ New panel*, a name and pasted emails, with *Edit on
      Panels →*. So Setup still runs forward without going back.
    - **Panels** holds the rosters in tables, Review Robin's roster page
      style (a table per panel, or everyone in one with a column per
      panel: open, AD1F), for the adjustments made after: rows added,
      edited and removed, a CSV in and out, a *Used by* line, *Copy
      panel*; a panel is retired only when nothing uses it. A gate already
      sent keeps the roster it was sent with.

20. **Gates folds into Process; Panels takes its slot** (author,
    2026-11-13; segment AD1F), amending rulings 14 and 19:
    - The Setup row is *Process · Form · Panels · Emails*. Process's
      items (the form, a gate, an outcome) collapse inside their stage
      card, and a gate item picks its panel there (*Evaluators*, with
      *+ New panel*).
    - **Panels is one table**: a row per person, a column per panel
      ticking who sits on it, and a control card floating on the right.
21. **A gate yields up to three results, each derived** (author,
    2026-11-14; segment AD1F):
    - A gate item on Process holds its name, *Runs as*, entry rule,
      evaluators, and up to three **results**. A result has a name, the
      **response field** each evaluator fills in (String, Integer,
      Decimal or List, with Review Robin's bounds: Min, Max, Step,
      options), and a **derivation** that turns the responses into the
      gate's result for an application.
    - **The derivation sets the result's type**; there is no second
      definition. Numeric fields: mean or median (Decimal), min or max
      (the field's type), sum, count. List fields: share choosing a
      value (a percentage) or most common (the list) — never mapped to
      numbers: a numeric scale is a numeric field, explained in its
      help text. String fields: all, joined, for reading. Count is any
      field's (author, 2026-11-14). A result
      *Entered here* takes the field's type as it is. A result needs a
      minimum number of responses, else it has none yet.
    - **The fields are Review Robin's setup**: the gate lists what its
      session's instrument must ask; the handshake itself is AD6's.
    - Result 1 is the gate's headline (Applications' chip). Outcome rules
      and weights read a gate's named result; only numbers are weighed
      or compared, a list is matched, a string is read only (a count of
      either is a number).
22. **People are entered as Residential's and Review Robin's are**
    (author, 2026-11-14; segment AD1F), across Apply Desk:
    - **A box that takes several people** works and looks as the boxes on
      Residential's `/residentialops/rosters/assignments` do: names or
      emails typed, separated by commas, each found in the directory
      (Graph; the sample institution until AD4) a pill with ×; what is not
      found stays in the box, said why.
    - **A table of people with more about each** (a panel's roster) is
      Review Robin's roster table: a row is edited by selecting it, its
      cells then edit boxes; several rows may be selected at once; an
      unselected row is inert, its ticks too, so nothing is changed by
      accident. A verified email is a pill; a name is typed.
23. **How an edit is kept depends on the surface's shape** (author,
    2026-11-14; segment AD1F), so nothing waits out of sight:
    - **A roster table** (Panels): a row is ticked to edit, its ✓ keeps
      it (Enter too), and unticking without ✓ puts it back; no page Save.
    - **A control surface** (Applications), worked down its columns
      rather than along a row: the whole table is locked, and *Unlock*
      opens every cell, *Set ticked rows*, the rules, the CSV and the
      releases; *Lock* keeps what changed and *Undo changes* puts the
      table back as it was unlocked, a count of the changes showing
      meanwhile and a warning on leaving with any pending. Ticks only
      choose rows.
    - **A builder of cards that depend on each other** (Form, Process):
      one Save, in the Outline card that stays in view, with an *Unsaved
      changes* marker and a warning on leaving with changes pending.
    - **Cards that stand alone** (Emails): a Save on each card.
    - **A card of actions** (Manage panels, as Review Robin's Unlock
      panel): its buttons act at once, but what changes the panels' list
      (a name typed, a panel added) waits for the card's own *Save*
      (Enter too), *Cancel* takes it back, neither closing the card, and
      *Close* asks first while any waits (author, 2026-11-14, replacing
      a ✓ by each box; *Add panel* an outline button, Save the card's
      one primary).

## MVP roadmap

Segments in order; each gets a plan in this folder when it starts.

| Segment | Lands | Gates and dependencies |
|---|---|---|
| **AD1 — Skeleton** | Package, `/applydesk` mount, health, CI lane, the URL map as placeholder pages | `applydesk/guide/segment_AD1_skeleton.md` |
| **AD1C — Applications page** | The Applications tab as a working scaffold: rounds of gates and outcomes as columns, admittance and outcome chips, release switches, rules from Setup or a CSV applied as a proposal, all or last applications; the application file named; nothing saved | `applydesk/guide/segment_AD1C_applications.md` |
| **AD1D — The exercise's chrome** | Home, the Setup row (Process, Form, Gates, Emails) and the Operations row (Applications, Evaluations, Extract data), as scaffolds; the status row; the Workflow card stepping through the timeline (ruling 14); nothing saved | `applydesk/guide/segment_AD1D_chrome.md` |
| **AD1F — Gates and Panels** | Form's *Select people* and each gate picking or making a panel (ruling 19); Gates folded into Process, whose items collapse, and Panels in its slot as one table with a column per panel (ruling 20); a gate's results, each a response field and a derivation (ruling 21); nothing saved | `applydesk/guide/segment_AD1F_gates_panels.md` |
| AD1G onward — the other new pages | Emails, Evaluations and Extract data built out as working scaffolds, one segment each | After AD1F |
| AD2 — Database and identity | The `applydesk` database and Alembic history; people bound by Entra tenant and object ID; operator grants; audit | Cordware: the database and its runtime principal (private) |
| AD3 — Exercises | The exercise and its public ID, configuration, draft → published → closed → archived, Validate, the form closing and the next stage opening (ruling 15) | G2 (published changes), G3 (stages) |
| AD4 — Applicant forms and portal | The applicant form with *Shown* / *Not shown to reviewers* sections, versioned; drafts, submit, withdraw; open or invitation-only exercises | G1 narrowed to applicant forms (shared package or fork); G4 (allowance) |
| AD5 — Panels and application files | The rosters on Panels (ruling 11): assessment panels and the applications each assessor is asked to review (ruling 9), the reviewer pool, interviewers; application files generated, the file with its access check, audit and blind redaction | — |
| AD6 — Assessment in Review Robin | Rosters from submitted applications, the pairs as tags, `ProfileLink` to the application file, the blind alias key (ruling 10), results back into ApplyDesk | The open items below |
| AD7 — Timeline and outcomes | Milestones, announcements, outcome import, embargo on read, release, correction | G5 (sender), G7 (publication) |
| AD8 — Dashboard and Reports | Counts by state; Reports: every evaluation response collated (ruling 11), the export bundle | — |
| Later | Blob storage, then uploads and referees | G8, with IT |

## Open decisions

- **Process's Preview** (AD1E): held until the builder is complete
  (author, 2026-11-13); what it shows is decided then.
- **What a gate before the form evaluates** (AD1D, AD1E): its rows
  before any application exists.
- **Applications in parts (ruling 15's next extension):** when it lands,
  and whether a part may be optional or repeated (references from more
  than one referee are their own case, with uploads and referees, G8).

- **The 23A open items (AD6):** `reviewees.unreachable_for_results` on
  every application ID; two concurrent first posts of one transfer; the
  new-user race in `get_or_create_user` (`guide/interoperability.md` §4).
- **Unattended send (AD7):** Cordware's host sends as the signed-in
  user (`cordware/graph.py`, `/me/sendMail`); a send with no one signed
  in shares RRW segment 14G's open question for IT.
- **The applicant photo field:** designed and saved
  (`applydesk/docs/photo_field_design.md`), from Utilities' photo proof of
  concept, which needs no Blob storage. It is in the MVP (ruling 12); how
  a blind exercise treats a face is still the author's (its Open
  questions).
- **Card visibility beyond *Shown to reviewers* / *Not shown*** (author,
  AD1B: "there should be more states in the spec"): which states, and
  when; AD4 stores the form.
- **Conditional questions: deferred** (author, 2026-11-12). A typical
  application form is linear; optional questions with help text cover
  the rest, and branching would reach Required, server checks, form
  versions, the application file and exports. If needed, the smallest shape:
  a section shown when one earlier *Choose one* list has a given option,
  one condition per section, hidden answers discarded on submit.
  Revisit when a real exercise would otherwise need two near-identical
  forms, or operators keep writing "skip this if…" in help text.
- **Raise early with IT:** Blob storage (spec §5.3) and the `applydesk`
  database, beside 14G's mailbox question.
