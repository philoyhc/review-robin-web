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
5. **Reviewers read an application on ApplyDesk's dossier** (*the parts
   their panel may see: ruling 26*)
   (the profile page, renamed by rulings 13 and 25), linked as each reviewee's `ProfileLink` in the handoff.
   ApplyDesk decides each view itself, from the signed-in Cordware
   identity and its own roster. The page shows only the *Shown to
   reviewers* section.
6. **Blind review is possible**: in a blind exercise the dossier
   redacts the applicant's name and identifiers.
7. **Every exercise has a 10-character public ID**, in RRW's alphabet
   (`app/db/models/review_session.py`, `PUBLIC_ID_ALPHABET`).
8. **The URL map follows RRW's.** Operators work under
   `/applydesk/operator/exercises` and
   `/applydesk/operator/exercises/<id>/…`; participants under
   `/applydesk/me` and `/applydesk/me/exercises/<id>/…`.
9. **A reviewer opens only the dossiers of the applications they are
   asked to review** (AD5). ApplyDesk's roster holds that permission.
   **The exercise's operators open every dossier** (author, 2026-11-12).
   How the same pairs reach Review Robin's assignments, through reviewer,
   reviewee or relationship tags, is decided at AD6. *(Settled by 23F and
   ruling 27: a linked gate sends `relationships.csv`.)*
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
    export. *(Reports became Extract data, ruling 14; AD1J built the
    bundle.)*

12. **A photo is a question type in the MVP** (author, 2026-11-12): the
    one upload ruling 3 allows, since it needs no Blob storage (the
    applicant frames it, the server keeps a re-encoded JPEG;
    `applydesk/docs/photo_field_design.md`). Its aspect ratio is set per
    question.

13. **Evaluation runs in rounds of gates and outcomes, driven from the
    Applications page** (author, 2026-11-12; *the page renamed Dossiers by
    ruling 25*; *rounds and the timeline's
    stages became one, the stage, in ruling 15*):
    - A **round** is sequential; a round holds one or more **gates**,
      which may run at the same time. A gate is who evaluates (a Panels
      roster), what they see (which sections), how (a Review Robin
      session, or results the operator enters), who enters, and a window
      of dates.
    - An **outcome** (shortlisted, finalist, awarded …) sits after a
      gate or at the end. It is a point on the Timeline, with its own
      date; each outcome has a *Released* switch, and what a release does
      (to applicants, to reviewers, by email) is set on Process.
    - Rounds, gates, outcomes and their dates are set up on **Setup**
      and the Timeline (*stages, on Process: rulings 14, 15*). **Dossiers** (*Applications* until ruling 25) is the control surface: who
      enters each gate (*—* for no status yet, *Entered*, *Not entered*;
      author, 2026-11-13) and each
      outcome's value, set by hand, by the column's rule, or uploaded as
      a CSV keyed by application ID. **Rules are set on Setup, not here**
      (author, 2026-11-13): Dossiers applies them, and the operator
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
    - What a reviewer opens is the **dossier** (ruling 25), one per
      application, or per candidate where there is none (ruling 5's
      "profile page"); it keeps its own ID apart
      from the application ID, for ruling 10's blind exercises.
14. **An exercise's pages follow the operator's workflow, in Review
    Robin's chrome** (author, 2026-11-13; segment AD1D):
    - **Home**, then a **Setup** row: *Process* (stages, gates, outcomes,
      dates, every rule, what a release does), *Form*, *Gates* (one card
      per gate, its panel roster on it; *a panel picked from Panels: ruling 19*), *Emails* (every template to
      applicants, kept in one place; Process sets which steps send one,
      and when; *who it is to and how templates are named: ruling 16*); then
      an **Operations** row: *Dossiers* (*Applications* until ruling 25), *Evaluations* (each gate's
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
    - ~~**A Workflow card** on Home and every Operations page steps
      through them in timeline order, the next one carrying its action
      and what blocks it~~ (*removed, author 2026-11-15: derivative of the
      other pages, it can wait*); there is no Validate tab.
15. **The exercise's timeline is built of stages** (author, 2026-11-13;
    segment AD1D), one word for ruling 13's rounds and the timeline's
    stages:
    - A **stage** has dates and a name the operator gives it, *Stage N*
      until then. Stages run one after another.
    - A stage holds **the form** (the application form: *Form* names
      what a stage holds, so *application* means only the record an
      applicant submits; author, 2026-11-13), or **one or more gates**,
      and may hold an **outcome**: never the form and a gate together.
      Any stage may also hold a **Dossiers** item (ruling 25).
      Only one stage holds the form, anywhere in the timeline (a
      gate stage may come first, its outcome deciding who may apply); an
      exercise may have none, its candidates collected upstream and
      loaded as dossiers (ruling 25). A stage may hold only an
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
      its Dossiers column runs *Not invited → Invited → Draft →
      Submitted*; Form picks between the forms; the dossier
      joins the parts. Until then, ruling 15's one application stage
      stands; each form-holding stage names its form and an application
      keeps a status per part, so the extension adds without reworking.
    - The sample's stages are *Call for applications*, *Review*,
      *Interview* and *Decision*. *(The model exercise now has three:
      Applications, Review, Interviews; ruling 30.)* The exercise's current stage is worked out from the
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
      named for its stage: *Review: Outcome · Applicants*, *Review:
      Outcome · Panel evaluators*, *Call for applications: Receipt ·
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
      *(Superseded by rulings 22 and 23: Manage panels above the table.)*
21. **A gate yields up to three results, each derived** (author,
    2026-11-14; segment AD1F; *amended by ruling 28: response fields and
    results are separate lists, and no gate runs as* Results entered here):
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
    - Result 1 is the gate's headline (Dossiers' chip). Outcome rules
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
    - **A control surface** (Dossiers), worked down its columns
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
      (a name typed, a panel added or retired) waits for the card's own *Save*
      (Enter too), *Cancel* takes it back, neither closing the card, and
      *Close* asks first while any waits (author, 2026-11-14, replacing
      a ✓ by each box; *Add panel* an outline button, Save the card's
      one primary).
24. **A gate run in Review Robin is sent from Apply Desk** (author,
    2026-11-15): the session is Review Robin's, created through Apply
    Desk's handoff (`spec/handoffs.md`), and Apply Desk keeps the link.
    The sequence, set-up done (Process, Panels, Form):
    - **Publish** the exercise, refused while Process's Outline names a
      problem (a Review Robin gate with no panel, an empty panel, no
      result). **Open** the form, applicants apply, **close** it; an
      exercise with no form loads its candidates as dossiers instead.
    - **Dossiers** are made as the stage's Dossiers item says (ruling
      25; *the Dossiers item struck by ruling 26*): from the form at submit or when it closes, the operator's
      choice, or from an upload or an earlier outcome's list.
    - **Who enters the gate** is decided on Dossiers (the entry
      rule as a proposal, cells by hand or CSV, *Lock* keeping it),
      every row *Entered* or *Not entered*.
    - **The gate is Ready** once the exercise is published, its entry is
      decided with at least one entered, every row entered has a dossier
      (ruling 25), its panel has members and it has a result. It may be sent **before its stage's dates**, which
      guide.
    - **Send to Review Robin** shows the bundle first: the session's
      name and code; reviewers, the panel; reviewees, the entered
      rows (the application ID, or the dossier's own where there is no
      application, or ruling 10's alias, as `RevieweeEmail`; the dossier as `ProfileLink`); and *For
      Review Robin*, each result's field **with the field key Apply Desk
      prescribes**. Sent, Apply Desk keeps the transfer, the session and
      who was sent; the tab lands on the draft's Session Home.
    - **In Review Robin** the operator builds the instrument to that
      list (until Apply Desk sends it, ruling 26), the field keys as given, then sets assignments and the
      schedule, validates, invites and activates.
    - **Changes after Send**: while the session has not opened, made in
      Apply Desk and sent again to the same draft (a contract Review
      Robin's handoff does not offer yet); once it has opened, made in
      Review Robin.
    - **Results** come back on Evaluations by *Pull results*, matched on
      the prescribed field keys (a missing key asks for a mapping),
      each result derived as its gate says, filling the gate's column on
      Dossiers.
    - **Who reviews which dossier** is ruling 27's: Apply Desk makes the
      pairs and sends them as `relationships.csv`.

25. **What a panel opens is the dossier, made by a Dossiers item**
    (author, 2026-11-15), since an exercise need not start with an
    application: a nomination gate may come first, its outcome the
    invitees, or candidates from an upstream process may go straight
    through gates with no form at all.
    - **The dossier** is the record a panel opens about one candidate
      or proposal (rulings 5, 6, 9 and 13's *application file*, renamed),
      with its own ID; an **application** is only what an applicant
      submits through Form, one source of a dossier.
    - *Superseded by ruling 26: the form and gates write dossiers
      themselves; the one Dossiers item left is Create dossiers.* ~~**A
      Dossiers item** is a new kind of item a stage holds, beside
      the form, gates and an outcome, one at most per stage. It says
      where its dossiers come from (the form's submissions, at submit
      or when it closes; an upload of candidates; an earlier outcome's
      list) and what they show (the *Shown to reviewers* answers,
      uploaded fields, earlier gate results and outcomes as ticked).~~
    - **A dossier reads its sources as they change**, but sending a gate
      **freezes the version its panel sees**: a later form part or gate
      result adds to it without changing what an earlier panel read.
    - A gate is not Ready until every row entered at it has a dossier.
    - **The Applications page becomes Dossiers** (author, 2026-11-15),
      at `/operator/exercises/<id>/dossiers`: a row per dossier, an
      application's where it has one.
    - **Open:** Create dossiers' states, for when a Workflow card
      returns (ruling 14).
26. **A dossier is written in parts, by the form, gates and outcomes**
    (author, 2026-11-15), amending ruling 25:
    - **A dossier** is the complete, readable file on one candidate's
      one entry: a candidate with two applications has two dossiers.
    - **It is made of parts**, each with an **audience**, any of:
      *Operators*; *Candidate*; a panel's *all members*; a panel's
      *assigned evaluators only*. And each with **when it becomes
      visible**: the stage from which its audience sees it. A part
      that opens to different audiences at different times is two
      parts.
    - **The form writes parts**: each section names its part (replacing
      *Shown to reviewers* / *Not shown*), written at submit or at the
      form's close (ruling 24's choice).
    - **A gate writes its raw results**: each evaluator's responses, as
      the parts it names, when it concludes. A Review Robin session run
      through Apply Desk releases nothing after its window; who sees
      results is the parts' audiences, on Apply Desk.
    - **An outcome writes the derived**: its value and combined result,
      as the parts it names.
    - **Create dossiers** is the one Dossiers item: an upload of
      candidates from upstream (an ID column and fields mapped to parts),
      in a stage before the first gate that needs them, where no form
      comes first. *Add dossiers* on the Dossiers page takes late or
      paper entries by the same upload, outside the timeline.
    - **Apply Desk sends Review Robin the session's settings** with its
      rosters: the instrument (a field per result, its key prescribed),
      visibility releasing nothing after the window, and the schedule
      from the window of the stage holding the gate (a gate has no dates of
      its own: author, 2026-11-15) as its start and end. Review Robin's
      handoff takes them since its segment 23D; its 23E (planned) marks
      the session as Apply Desk's, turning off Review Robin's release.
27. **A gate's evaluators come from ranked sources; Apply Desk makes the
    pairs** (author, 2026-11-15). Process sets the rules on the gate;
    the **Evaluations** page shows each gate's evaluator-by-candidate
    assignments and carries their operations.
    - **Sources**, ranked in order on the gate, each with a **min** and a
      **max** per dossier: **nominated evaluators** (named by the candidate
      in a *Select people* question on Form; referees, ruling 2, are not
      yet) and **panels**, one or more, each giving members to a
      dossier. A last row, **Total**, sets the overall min and max per
      dossier, within what the sources allow: its min no lower than the
      sources' mins together, its max no higher than their maxes.
    - **Counts are of distinct evaluators**: someone in two sources counts
      once, for the higher-ranked.
    - **Filling a dossier**: sources are taken in rank order, each giving
      as many as it has, up to its max; lower-ranked sources then supply
      what is still needed to reach the Total's min, never fewer than
      their own min; nothing passes the Total's max. With *nominated: 0-2*,
      *Panel A: 1-3* and *Total: 3-3*, a candidate who nominated no one
      gets three from Panel A, and one who nominated two gets one. A
      dossier that cannot be filled is not ready for the gate.
    - **Automatic assignment** gives every dossier its counts, spreads the
      work evenly across each panel's members, and never pairs a known
      conflict (a nominated evaluator who is also on the panel counts
      once; the candidate themselves never).
    - **Three modes**, set on the gate: **automatic**; **Apply Desk
      suggests, the operator approves** (on Evaluations); **the operator
      assigns** (on Evaluations). A gate is Ready only when every entered
      dossier is assigned, or approved.
    - **The pairs go to Review Robin** as `relationships.csv`, the
      instrument keeping only those pairs; they are a gate's *assigned
      evaluators* audience (ruling 26) and decide who opens which dossier
      (ruling 9). After Send, ruling 24: edited in Apply Desk until the
      session opens, then in Review Robin.

28. **A gate is one Review Robin run, and its card follows what that run
    needs** (author, 2026-11-17), amending rulings 21 and 24:
    - A gate puts those it enters through **one** evaluation run, yielding
      up to three results. More runs are more gates.
    - **Every gate runs in Review Robin** for now. The card's **Type** is a
      menu fixed at *Review Robin session*, kept for other kinds later.
      *Runs as* and *Results entered here* go: nothing in Apply Desk keys
      in a gate's results. An operator's decision needs no gate: it is an
      outcome *Decided by hand*, keyed on Dossiers.
    - **The card**, in order: a collapsible **Gate** card (Name and Type,
      Description, **Confidential**, Entry rule); a collapsible
      **Evaluators** card (sources, Total, members, Assignment); then
      **Response fields**, what each evaluator answers (type, bounds or
      options, required, help); then **Results**, up to three. Both cards
      start collapsed, each saying what it holds.
    - **A result names the response field it collates** and its
      derivation, which still sets its type (ruling 21); fields and
      results are no longer one row.
    - **Start and End are the stage's**, not the gate's.
29. **A sent gate can be changed and re-sent until its session opens**
    (author, 2026-11-17), settling the open question below: its card
    stays editable while sent and unopened, each change re-sent; once the
    session opens it is fixed in Apply Desk (a linked session stays
    locked: changes then come by revert-and-re-send or Unlink, in Review
    Robin). **The model exercise is mid-stage**: its Review stage's gates
    are sent and their results in; its Interview stage is under way, its
    gate entered but not yet sent, its pairs being worked on Evaluations
    (AD1G rung 6), so no interview results or finalists yet.
30. **The model exercise is the author's residential assistants'
    recruitment** (author, 2026-11-17; segment AD1H), mid Stage 3, its
    staff interview gate entered and its pairs being approved. It needs,
    and so gets: rules with **ordered branches**, a condition on a **form
    answer**, and **the best N** by a result, the app proposing and the
    operator approving; a mean **ignoring 0** (a *Don't know* score); and
    **a page per gate** under Evaluations, its assignments paged 200 at a
    time, since one gate pairs 30 reviewers with 100 applicants. Its
    sample drops nominations; Gate 3's pairs are *Suggested, then
    approved*; *not Major concerns* means no one chose it.

31. **The rule engine stays in the MVP** (author, 2026-11-18, on the
    assessment's AD-61 to AD-63): branching rules, *the best N* and
    Automatic's even spread are confirmed, overriding the functional
    spec's "no decision engine" (§15.3) and "no balancing" (§7.7). How
    it is evaluated, and where (a server-side evaluator at AD2), needs
    thinking through before AD2.
32. **The dossier is its own table at AD2** (author, 2026-11-18; AD-44):
    pairs, cells, results, parts and the alias key hang off it, not the
    application. Proposed: minted at submit, so a draft has none.
33. **What a reader sees is set per dossier part** (author, 2026-11-18;
    AD-64): the parts of ruling 26, each with its audiences, are the one
    vocabulary; per-card *shown* and section *Shown / Not shown* go, and
    the terms are standardized to *part*.
34. **Approval is per dossier** (author, 2026-11-18; AD-47): under
    *Suggested, then approved*, the operator approves a dossier's
    evaluators together, not pair by pair.
35. **Each stage has its own status: Draft, Published, Completed**
    (author, 2026-11-18): what locks, locks when its stage is published
    (blind review among it, AD-05). A published stage may be reverted to
    draft, audited.
36. **A Review Robin gate comes in two types** (author, 2026-11-18):
    *Review Robin*, the default, its instrument locked as today; and
    *Review Robin (advanced)*, whose instrument starts with the gate's
    response fields, which Review Robin may not delete, but may reorder,
    require or not, add fields to and branch between (e.g. a
    *Familiarity* rating, Score and Comments shown only above a
    threshold). Its own segment: `guide/segment_23G_linked_advanced_instrument.md`.
37. **A gate's handle is a stable key** (author, 2026-11-18; AD-48): its
    URL and Extract file names use a per-exercise key that never moves;
    the number is for display only. Built at AD2, when gates are stored.
38. **An outcome's *Decided* is derived; release is per audience**
    (author, 2026-11-18; AD-34, AD-21): *Decided* shows when every reached
    cell has a value, and is not stored; release is recorded for each
    audience (applicants, reviewers) with its own time.
39. **Every panel is generic** (author, 2026-11-18; AD-50): what a panel
    does comes from where it is used; the sample's *pool* and
    *interviewers* keys lose any special meaning at AD2.
40. ***Results expected* is free text** (author, 2026-11-18; AD-56): typed
    on Details, shown to applicants as an estimate, never computed.
41. **A Closed exercise stays on `/me`, read-only** (author, 2026-11-18;
    AD-37, AD-28): the operator closes it after the last release, and
    applicants keep seeing it with their released results; Archived drops
    it from `/me`.
42. **A confidential gate hides names on its page and files** (author,
    2026-11-18; AD-65, completing ruling 35's open part): its page and
    files show Dossier IDs, as blind review does exercise-wide; its
    evaluators' dossier is unchanged.
43. **The confidential identity is the Dossier ID** (author, 2026-11-18;
    AD-67): Review Robin receives the Dossier ID in place of the
    application ID; Extract's *Alias key* maps it back. No per-handoff
    alias.
44. **One term: *evaluator*; the root stays *Operator Lobby*** (author,
    2026-11-18; AD-89, AD-90, AD-102): operators and applicants alike
    read *evaluator*.
45. **Withdrawal ends when a gate holding the dossier is sent** (author,
    2026-11-18; AD-30, AD-08): until then an applicant may withdraw
    (Outline-amber, with a confirm). The operator's *Return to draft* is
    a per-row action on Dossiers, and in bulk through the ticks;
    *Generate dossiers* goes.
46. ***Shown to applicants* is modelled per stage** (author, 2026-11-18;
    AD-09): a stage left unticked is hidden from the applicant's
    timeline.
47. **Pills pick many, a segmented control picks one** (author,
    2026-11-18; AD-68, AD-69): multi-select chips use the `.pn-show`
    pill, one-of choices the `.seg` control; no other variant.
48. **A gate reverts to draft until it completes** (author, 2026-11-18):
    as a Review Robin session, a gate may go back to draft while it is
    not closed or completed (*Results in*): not advisable, but kept for
    the extreme case. What is locked is an evaluator fill that is not
    idempotent: once made, it is never regenerated, only edited by hand.
49. **Withdrawal and Return to draft follow the gate** (author,
    2026-11-18, amending ruling 45): an applicant may withdraw, and the
    operator return an application to draft, until a gate holding its
    dossier completes, not merely once it is sent.
50. **Checkboxes stay for now; a UI consistency sweep comes later**
    (author, 2026-11-18): the assessment's consistency rows (AD-69's
    checkboxes, AD-70 to AD-86, AD-91 to AD-98) wait for that sweep.
51. **A gate page's pairs can be ticked** (author, 2026-11-19): ticked
    rows narrow *Approve* and *Discard* to themselves, their labels
    saying so (*Approve ticked (n)*, *Discard ticked (n)*); a row's own
    buttons sit at its end, flush right.
52. **Dossiers' columns sort** (author, 2026-11-19): under the stages,
    an information row (kind, counts, rule, lock, *Released*) and then
    the column headers on one line, each with a sort handle. Dossier by
    ID, Applicant by name, Status in its order then date, a gate by its
    chip then its headline result (highest first), an outcome by its
    values in Process's order then date; ties keep the page's order;
    the sort is kept in the tab.
53. **One body per template; paragraphs with a small gap** (author,
    2026-11-19, on AD1L's open question): a template has one subject
    and one body, `[Outcome]` naming the value, never a body per value.
    The body holds paragraphs, separated by a blank line, each shown
    with a small gap (Preview now, the sent email at AD7); a single line
    break stays a line break.

## What a linked Review Robin gate needs (2026-11-16)

Review Robin's side is built and closed (RRW segment 23F): a gate sent
from Apply Desk becomes a **linked** Review Robin session, locked to what
Apply Desk sends (`spec/linked_sessions.md`, `spec/handoffs.md`; the
working reference sender is Utilities' `utilityapps/interop_poc/`). Apply
Desk has no sender yet. What it needs, in three layers (author: UI first,
rulings after this list):

**A. Process > Gates: what the operator enters for each gate**
- **Name** (built) and a **description** (new): the instrument's name
  and description in Review Robin.
- **Start and End**, the gate's **stage's** (ruling 28), as real
  date-times in the exercise's **timezone** (stage dates are free text
  today, `stages.py`); Start before End. A sent Start activates the
  session once prepared, which ends re-sends.
- **Help contact** and **timezone**: the exercise's, on Home's Details, each
  defaulted from Apply Desk's operator settings, as Review Robin's are
  (author, 2026-11-17); shown on each gate.
- **Each response field** (ruling 28): label, type and bounds or
  options, **required** and **help text**, and a stable **field key**
  (Review Robin reports answers under it); **each result** names the
  field it collates and its derivation.
- **Evaluators**: the ranked sources and their tags (AD1G). Every pair
  carries its source as the relationship tag, no comma.
- **Confidential** (per gate, author 2026-11-17): whether the gate is blind, which decides what
  Review Robin shows as each reviewee's name and key.

**B. Evaluations > Gates: what the operator does with each gate**
- **Send** (now disabled): live when the gate is Ready; opens Review
  Robin's holding tab, posts the bundle, lands on the new session;
  refusals shown with their reason.
- **Re-send** while the session is unopened: after any change to the
  dossiers, pairs, results, dates or description; refusals shown
  (`session_opened`, `session_has_responses` → Review Robin's *Delete
  data*, `not_linked`, `session_code_conflict`, `invalid_setup`).
- **Status** (now *Pull*, disabled): state, progress and each reviewer's
  completion; *Unavailable* when the read fails or its version differs.
- **Results**: `results.csv` and `completion.csv`, each answer mapped to
  its dossier and result, each gate result derived (ruling 21).
- **Link state**: linked, or detached after an Unlink in Review Robin
  (no re-send then).
- **Invite and remind**: Review Robin emails no one on a linked session;
  Apply Desk emails reviewers a link to Review Robin's `/me`, where they
  sign in (their `ReviewerEmail` is their sign-in address).

**C. Underneath**
- **Persistence (AD2)**: stages with date-times and timezone, gates,
  results with their metadata, pairs, and per gate the **transfer
  record** (the creating `transfer_id` every later call is keyed by,
  the session code, what was sent).
- **Bundle builders**: reviewers (name, email; no tags), reviewees (key,
  name, `ProfileLink` as an absolute URL), relationships
  (`PairContextTag1.Apply-Desk-Link`), settings rows (the session's
  description, help contact, timezone, Start, End, the tag `applydesk`;
  one instrument and its response fields). `source_app` exactly
  `applydesk`. Never: observers, release, branching, rules, layouts.
- **The browser-mediated calls**: create, re-send, status, results, with
  retry and replay as `spec/handoffs.md` §6–7 say.
- **Results mapping and derivation** into dossiers (ruling 21), raw
  results as dossier parts when the gate concludes (ruling 26).
- **Dossier access (AD5)**: a reviewer opens only the dossiers paired to
  them (ruling 9); the version frozen at send (ruling 25); blind
  redaction matching what Review Robin shows.
- **Emails (AD7)**: the gate invitation and reminder templates; release
  through dossier parts (Review Robin releases nothing).

**Rulings to settle (after the list)**
- ~~Ruling 24's "after opening, made in Review Robin"~~: superseded by
  ruling 29; a linked session stays locked; changes come by
  revert-and-re-send or Unlink.
- ~~A sent gate read-only (AD1F, AD1G) versus re-sending before it opens~~:
  re-sent until it opens (ruling 29).
- Confidential identity: 23F's "Name redacted" plus the Dossier ID, or
  ruling 10's per-handoff alias key.
- Each gate's Review Robin session name and code (unique there).
- ~~Where the help contact comes from~~: the exercise's (author,
  2026-11-17); the description is the gate's.
- What marks a gate concluded, for writing results.
- Panels' *Sent* chip still marks a gate sent, not one whose session has
  opened (ruling 29); the spec says the same. Align when Panels is next
  touched.
- + Pair on a blind gate cannot leave out the candidate themself without
  saying which dossier is whose: the server checks the pair at AD2
  (AD1G rung 6b's cold read).
- How Apply Desk's operators line up with Review Robin's.
- Scores entered by hand (an interview held outside Review Robin): every gate's scores come from Review Robin today and only outcomes are set by hand, on Dossiers; not on Extract data (author, 2026-11-18, AD1J). Where they belong is open.
- ~~Ruling 9's and AD6's "tags decided at AD6"~~: settled by 23F.

**Order** (UI first): A done in AD1G (closed 2026-11-17),
then B on Evaluations > Gates as a new segment; then AD2's persistence; AD5; AD6 as rungs (builders,
Send, re-send, status and results, Unlink); AD7's emails.

## MVP roadmap

Segments in order; each gets a plan in this folder when it starts.

| Segment | Lands | Gates and dependencies |
|---|---|---|
| Layer B — Gates to Review Robin | Send, re-send, status, results, link state, invite and remind, on Evaluations > Gates (the "Order" above) | Next |
| AD2 — Database and identity | The `applydesk` database and Alembic history; people bound by Entra tenant and object ID; operator grants; audit | Cordware: the database and its runtime principal (private) |
| AD3 — Exercises | The exercise and its public ID, configuration, draft → published → closed → archived, Validate, the form closing and the next stage opening (ruling 15) | G2 (published changes), G3 (stages) |
| AD4 — Applicant forms and portal | The applicant form with *Shown* / *Not shown to reviewers* sections, versioned; drafts, submit, withdraw; open or invitation-only exercises | G1 narrowed to applicant forms (shared package or fork); G4 (allowance) |
| AD5 — Panels and dossiers | The rosters on Panels (rulings 19, 22), each gate's evaluators from its ranked sources (ruling 27); dossiers made from the form or by *Create dossiers* (rulings 25, 26), the dossier with its access check, audit and blind redaction | — |
| AD6 — Assessment in Review Robin | Rosters from dossiers (rulings 25, 26), the pairs as `relationships.csv` (ruling 27, 23F), `ProfileLink` to the dossier, the blind alias key (ruling 10), results back into ApplyDesk | The open items below |
| AD7 — Timeline and outcomes | Milestones, announcements, outcome import, embargo on read, release, correction | G5 (sender), G7 (publication) |
| AD8 — Dashboard | Counts by state; the export bundle is Extract data, built in AD1J (ruling 14) | — |
| Later | Blob storage, then uploads and referees | G8, with IT |

## Follow-ups from closed plans (AD-124)

- **AD5:** a list headline (Result 1) has no value on Dossiers (AD1F).
- **AD5:** a panel used twice in one gate, or a max above its panel's
  size, is not flagged (AD1G).
- **Layer B:** a gate's progress line is canned beside counted pairs
  (AD1I; AD-32).
- **Form:** card drag has no Escape and no auto-scroll (AD1B).

## Open decisions

- **Process's Preview** (AD1E): held until the builder is complete
  (author, 2026-11-13); what it shows is decided then.
- **What a gate before the form evaluates** (AD1D, AD1E): its rows
  before any application exists.
- **Applications in parts (ruling 15's next extension):** when it lands,
  and whether a part may be optional or repeated (references from more
  than one referee are their own case, with uploads and referees, G8).

- **The 23A open items (AD6):** ~~`reviewees.unreachable_for_results` on
  every application ID~~ (not raised under the `release` lock, RRW 23F);
  two concurrent first posts of one transfer; the
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
  versions, the dossier and exports. If needed, the smallest shape:
  a section shown when one earlier *Choose one* list has a given option,
  one condition per section, hidden answers discarded on submit.
  Revisit when a real exercise would otherwise need two near-identical
  forms, or operators keep writing "skip this if…" in help text.
- **A panel shared across exercises** (AD1F): an institution's standing
  pool, the author's when AD5 stores panels.
- **Raise early with IT:** Blob storage (spec §5.3) and the `applydesk`
  database, beside 14G's mailbox question.
