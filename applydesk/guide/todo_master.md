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
5. **Reviewers read an application on ApplyDesk's application profile
   page**, linked as each reviewee's `ProfileLink` in the handoff.
   ApplyDesk decides each view itself, from the signed-in Cordware
   identity and its own roster. The page shows only the *Shown to
   reviewers* section.
6. **Blind review is possible**: in a blind exercise the profile page
   redacts the applicant's name and identifiers.
7. **Every exercise has a 10-character public ID**, in RRW's alphabet
   (`app/db/models/review_session.py`, `PUBLIC_ID_ALPHABET`).
8. **The URL map follows RRW's.** Operators work under
   `/applydesk/operator/exercises` and
   `/applydesk/operator/exercises/<id>/…`; participants under
   `/applydesk/me` and `/applydesk/me/exercises/<id>/…`.
9. **A reviewer opens only the profiles of the applications they are
   asked to review** (AD5). ApplyDesk's roster holds that permission.
   **The exercise's operators open every profile** (author, 2026-11-12).
   How the same pairs reach Review Robin's assignments, through reviewer,
   reviewee or relationship tags, is decided at AD6.
10. **A blind exercise sends Review Robin an alias key** in place of the
    application ID, minted per handoff and mapped back only by
    ApplyDesk (AD6), since RRW shows `RevieweeEmail` under each name.
11. **The operator's pages are Home, Setup, Form, Applications, Panels,
    Review and Reports** (author, 2026-11-12). Home shows the timeline and
    the current stage; Setup holds the timeline's setup; Form builds and
    previews the application form; Applications generates applicant
    profiles. **Panels holds the rosters ApplyDesk keeps (ruling 4)**:
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
    Applications page** (author, 2026-11-12):
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
      and the Timeline. **Applications** is the control surface: who
      enters each gate (*Pending*, *Selected*, *Not selected*) and each
      outcome's value, set by hand, filled by a rule over an earlier
      gate's result (e.g. Rating ≥ 4.0), or uploaded as a CSV keyed by
      application ID. A rule or an upload is a proposal the operator
      reviews before saving; a hand change always remains possible.
    - The word **stage** stays with the exercise's timeline (Setup,
      Application, Review …); evaluation steps are **rounds**.
    - An applicant may send more than one application; the page shows
      all of them, or each applicant's last **submitted** one.
    - What a reviewer opens is the **application file**, one per
      application (ruling 5's "profile page"); it keeps its own ID apart
      from the application ID, for ruling 10's blind exercises.

## MVP roadmap

Segments in order; each gets a plan in this folder when it starts.

| Segment | Lands | Gates and dependencies |
|---|---|---|
| **AD1 — Skeleton** | Package, `/applydesk` mount, health, CI lane, the URL map as placeholder pages | `applydesk/guide/segment_AD1_skeleton.md` |
| **AD1C — Applications page** | The Applications tab as a working scaffold: rounds of gates and outcomes as columns, admittance and outcome chips, release switches, fill by rule or CSV as a proposal, all or last applications; the application file named; nothing saved | `applydesk/guide/segment_AD1C_applications.md` |
| AD2 — Database and identity | The `applydesk` database and Alembic history; people bound by Entra tenant and object ID; operator grants; audit | Cordware: the database and its runtime principal (private) |
| AD3 — Exercises | The exercise and its public ID, configuration, draft → published → closed → archived, Validate, the Application → Review stage boundary | G2 (published changes), G3 (stages) |
| AD4 — Applicant forms and portal | The applicant form with *Shown* / *Not shown to reviewers* sections, versioned; drafts, submit, withdraw; open or invitation-only exercises | G1 narrowed to applicant forms (shared package or fork); G4 (allowance) |
| AD5 — Panels and profile page | The rosters on Panels (ruling 11): assessment panels and the applications each assessor is asked to review (ruling 9), the reviewer pool, interviewers; applicant profiles generated, the profile page with its access check, audit and blind redaction | — |
| AD6 — Assessment in Review Robin | Rosters from submitted applications, the pairs as tags, `ProfileLink` to the profile page, the blind alias key (ruling 10), results back into ApplyDesk | The open items below |
| AD7 — Timeline and outcomes | Milestones, announcements, outcome import, embargo on read, release, correction | G5 (sender), G7 (publication) |
| AD8 — Dashboard and Reports | Counts by state; Reports: every evaluation response collated (ruling 11), the export bundle | — |
| Later | Blob storage, then uploads and referees | G8, with IT |

## Open decisions

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
  versions, the profile page and exports. If needed, the smallest shape:
  a section shown when one earlier *Choose one* list has a given option,
  one condition per section, hidden answers discarded on submit.
  Revisit when a real exercise would otherwise need two near-identical
  forms, or operators keep writing "skip this if…" in help text.
- **Raise early with IT:** Blob storage (spec §5.3) and the `applydesk`
  database, beside 14G's mailbox question.
