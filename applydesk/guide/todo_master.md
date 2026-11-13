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
      per gate, its panel roster on it), *Emails* (every template to
      applicants, kept in one place; Process sets which steps send one,
      and when); then
      an **Operations** row: *Applications*, *Evaluations* (each gate's
      progress and results), *Extract data*. Panels folds into Gates,
      Review becomes Evaluations, Reports becomes Extract data, Setup
      becomes Process. Ruling 13's "Setup and the Timeline" is Process.
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
    - A stage holds **the application**, or **one or more gates**, and
      may hold an **outcome**: never the application and a gate together.
      Only one stage holds the application, anywhere in the timeline (a
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
    - The sample's stages are *Applications*, *Review*, *Interview* and
      *Decision*. The exercise's current stage is worked out from the
      timeline (the one holding its next step), not stored. Setup (a
      draft) and Close are the exercise's state, not stages.
    - **Process is a stack of stage cards**, as Form is of question
      cards: a new exercise starts with one stage card offering the
      application and an outcome (an outcome is optional: the sample's
      Applications stage has none); stages are added, moved and deleted,
      but the last one cannot be deleted.

## MVP roadmap

Segments in order; each gets a plan in this folder when it starts.

| Segment | Lands | Gates and dependencies |
|---|---|---|
| **AD1 — Skeleton** | Package, `/applydesk` mount, health, CI lane, the URL map as placeholder pages | `applydesk/guide/segment_AD1_skeleton.md` |
| **AD1C — Applications page** | The Applications tab as a working scaffold: rounds of gates and outcomes as columns, admittance and outcome chips, release switches, rules from Setup or a CSV applied as a proposal, all or last applications; the application file named; nothing saved | `applydesk/guide/segment_AD1C_applications.md` |
| **AD1D — The exercise's chrome** | Home, the Setup row (Process, Form, Gates, Emails) and the Operations row (Applications, Evaluations, Extract data), as scaffolds; the status row; the Workflow card stepping through the timeline (ruling 14); nothing saved | `applydesk/guide/segment_AD1D_chrome.md` |
| AD1E onward — the new pages | Process (a stack of stage cards, as Form's, with their rules and dates: ruling 15), then Gates, Emails, Evaluations and Extract data built out as working scaffolds, one segment each | After AD1D |
| AD2 — Database and identity | The `applydesk` database and Alembic history; people bound by Entra tenant and object ID; operator grants; audit | Cordware: the database and its runtime principal (private) |
| AD3 — Exercises | The exercise and its public ID, configuration, draft → published → closed → archived, Validate, the form closing and the next stage opening (ruling 15) | G2 (published changes), G3 (stages) |
| AD4 — Applicant forms and portal | The applicant form with *Shown* / *Not shown to reviewers* sections, versioned; drafts, submit, withdraw; open or invitation-only exercises | G1 narrowed to applicant forms (shared package or fork); G4 (allowance) |
| AD5 — Panels and application files | The rosters on Panels (ruling 11): assessment panels and the applications each assessor is asked to review (ruling 9), the reviewer pool, interviewers; application files generated, the file with its access check, audit and blind redaction | — |
| AD6 — Assessment in Review Robin | Rosters from submitted applications, the pairs as tags, `ProfileLink` to the application file, the blind alias key (ruling 10), results back into ApplyDesk | The open items below |
| AD7 — Timeline and outcomes | Milestones, announcements, outcome import, embargo on read, release, correction | G5 (sender), G7 (publication) |
| AD8 — Dashboard and Reports | Counts by state; Reports: every evaluation response collated (ruling 11), the export bundle | — |
| Later | Blob storage, then uploads and referees | G8, with IT |

## Open decisions

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
