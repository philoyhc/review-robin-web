# Apply Desk — findings register, 2026-11-18 assessment

Every operator and applicant screen was assessed on the five sample exercises through four lenses: UI consistency, intended actions, data model (pre-AD2) and spec gaps. The assessment was taken at `f5053a703` and was read-only; pages were rendered through the test host and driven in Chromium. To use the register, strike a row's ID (~~AD-nn~~) with the PR that clears it, or mark it *Ruled* or *Deferred (where)*. Rows are clustered by theme and ranked by severity within each theme.

Conventions: `.py` paths are relative to `applydesk/`, `.html` paths to `applydesk/templates/applydesk/`, and `spec/` / `guide/` / `docs/` to `applydesk/`. **R*n*** is ruling *n* in `guide/todo_master.md`; **LRG** is that file's "What a linked Review Robin gate needs"; **FS** is `docs/applydesk_functional_spec_v0.6b_agent_handoff.md`. Exercises: `wa9juxbc2t` (RA model, published), `c4xh2ndv6s` (draft), `n5wg8tjr3e` (blank draft), `k7mfr3pq8z` (blind/TEA), `r6tm4kq9wz` (open). Severity: **H** contradicts a ruling on live items, misleads into a consequential act, or would make AD2 persist a wrong shape. **M** means a page is dishonest, a step is missing, or a fact is duplicated and will drift. **L** means polish, wording, or a sample-only issue. The *Was* column cites the source reports: `UI-` (UI consistency), `ACT-` (intended actions), `DM-` (data model), `SP-` (spec gaps). ACT-45 and ACT-48 were checked and found correct, so they are not listed.

## Summary

| Theme | H | M | L | Total |
|---|---|---|---|---|
| 1. Locking once live | 4 | 1 | 0 | 5 |
| 2. Honest controls and copy | 0 | 7 | 7 | 14 |
| 3. Workflow gaps | 1 | 2 | 3 | 6 |
| 4. Applicant surface | 1 | 2 | 3 | 6 |
| 5. State and canned data | 4 | 4 | 3 | 11 |
| 6. Identity and keys | 5 | 5 | 3 | 13 |
| 7. Typed values | 3 | 2 | 0 | 5 |
| 8. Rules | 2 | 1 | 0 | 3 |
| 9. Visibility and confidentiality | 0 | 3 | 1 | 4 |
| 10. Component consistency | 1 | 11 | 9 | 21 |
| 11. Terminology | 0 | 2 | 8 | 10 |
| 12. Accessibility and navigation | 1 | 2 | 4 | 7 |
| 13. Layout and phone | 0 | 2 | 3 | 5 |
| 14. Spec and doc drift | 1 | 3 | 6 | 10 |
| 15. Roadmap and rulings | 0 | 2 | 2 | 4 |
| 16. Performance | 0 | 1 | 0 | 1 |
| **Total** | **23** | **50** | **52** | **125** |

- **Nothing locks once live.** A published exercise with a closed form and opened gates can still have its form restructured, its gates renamed or removed, its entries flipped and its blind flag changed (AD-01 to AD-05). Once AD2 wires saving, these become destructive.
- **Pages misdescribe themselves.** The banner says controls do nothing on pages where they work. Panels says "saved", the Extract page says "logged", and Emails says Review Robin sends invitations (AD-06, AD-07, AD-10, AD-12). Dossiers' *Lock* and the Panels table drop edits silently.
- **State is canned, not derived.** Gate state and progress, *Ready*, the missing *Decided* state and the counts are fixed sample values that contradict the computed pairs and cells, so pages disagree with each other (AD-32 to AD-34, AD-41).
- **Everything is referenced by display string.** People are keyed by email, questions by label, outcome values by label, gates by position, and rules by loose strings. AD2 must introduce stable keys before it persists anything (AD-43, AD-45, AD-48, AD-57, AD-62).
- **Rules exist only in page JS.** There is no server-side evaluator or validator; seeded cells agree with the rules by construction, not by enforcement (AD-61). The scope of the rule engine itself needs a ruling against FS §15.3 (AD-63).
- **One form, two models.** The applicant and dossier pages read hand-kept lists that disagree with the Form page, and print the title against the wrong question (AD-26).
- **Primitives and words fork per page.** There are five on/off controls, two chip systems, four table looks, three searches and five empty states. The overloaded terms are dossier/application, evaluator/reviewer/assessor and the gate labels (themes 10 and 11). A pressed toggle is indistinguishable from Primary (AD-68).
- **The spec's homes are stale.** The normative URL map lives in an unclosed plan, three plans are still "Building", and the roadmap describes retired designs (AD-111, AD-114, AD-121).

## Register

### 1. Locking once live

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| ~~AD-01~~ | H | An opened gate says "its settings are fixed here", yet *Name*, *Edit the rule* and *Remove the gate* stay live, as do *Remove the outcome* on a released outcome and the stage's *Delete*. Removing Gate 1 (*Results in*) takes one click with no prompt, and orphans its Dossiers column and its Extract file. | Process `wa9juxbc2t`; `operator/_process_cards.html:193,266,311,353` | Code: put `sent_attr(sent)` and a title on name, rule, remove-gate, remove-outcome and the stage's Delete/Replicate source. | ACT-01, UI-10 |
| ~~AD-02~~ | H | The stage that holds a **Closed** form with 100 submitted applications deletes at one click, with no prompt or undo; *Remove the form* is enabled too. | Process; `operator/_process_cards.html:44` | Code: disable both once `workflow.form_state` is Open or Closed, with the reason in the title. | ACT-02 |
| ~~AD-03~~ | H | The whole Form builder (type, Delete, Replicate, drag, Required, visibility) is live on a published exercise whose form is Closed; a card deletes with no prompt. `_form.html` reads no `form_state`. R14 says the form locks when it goes live. | Form `wa9juxbc2t`; `operator/_form.html` | Code: when the form is not Draft, render the builder read-only with a line ("changes wait for re-publishing, G2"); leave Preview live. | ACT-03 |
| ~~AD-04~~ | H | After *Unlock*, Dossiers lets an operator flip entry on a gate whose results are in. Every `data-ap-adm` cell carries `data-ap-locks` whatever the gate's state, so Process says "fixed" while Dossiers edits it. | Dossiers; `operator/_dossiers.html:~92` | Code: keep an opened gate's cells disabled ("Its session has opened"), and exclude them from *Set ticked rows* and rule proposals. | ACT-04 |
| ~~AD-05~~ | M | *Blind review* stays editable on a published exercise with gates sent and results in, unlike Code and Who may apply. Flipping it after an alias handoff breaks R10's mapping. | Home Details; `operator/_details.html:36` | Code: lock it at publish or at the first send (Ruling needed: For the author 6). See AD-65. | ACT-26 |

### 2. Honest controls and copy

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-06 | M | The banner "nothing here is saved, and the controls do nothing yet (segment AD1)" shows on Home, Process, Panels, Evaluations, Extract and `/me`, where controls do work (Details locks, Process and Panels edit, Extract downloads real files). There are five wordings with different segment tags. Extract does not say its files ignore this visit's on-screen edits. | `_placeholder.html:1` (via `operator/home.html:5`, `section.html:5`, `operator/exercises.html:5`, `me/*.html`); `operator/gate_evaluations.html:19`; `operator/form_preview.html:10` | Code: one line per section ("works on screen; nothing saved until AD2"; Extract: "files built from sample data, not from on-screen edits"; Emails: inert); drop rung tags. | UI-05, ACT-20, ACT-37, SP-13 |
| AD-07 | M | Unsaved edits are lost silently on three surfaces. After Dossiers' *Lock* the page says "2 changes kept", hides the count and gives no leave warning. Panels' ✓ announces "saved", and table edits or × (with no prompt, even on a member of a sent panel) show no marker and no warning. The gate page has no `beforeunload`. | Dossiers, Panels, gate page; `operator/_dossiers.html`, `operator/_panels.html`, `_gate_ops_js.html` | Code: a page-level "N changes on this page, not saved" marker plus `beforeunload` on all three; ✓ says "kept on this page"; ask before × on a sent panel's member. | ACT-07, ACT-16, ACT-21, ACT-22 |
| AD-08 | M | *Generate dossiers* (Primary) and *Return to draft* (`btn-alert`, the retired Alert name) render unconditionally, disabled with no title, including on drafts. R26 has no generate step (only *Create dossiers* / *Add dossiers*), and a test pins the button. Return to draft sits under the Dossiers table, while Publish is on Home. | Dossiers; `operator/_dossiers.html:126-129`; `tests/test_pages.py:389-393` | Code: remove or replace *Generate dossiers* per R26; gate Return to draft on state, give it Outline-amber and a title ("AD3"), and move it beside Publish on Home. | UI-06, ACT-10, SP-09 |
| AD-09 | M | The stage's *Shown to applicants* (always checked) and the outcome's per-audience *Update timeline* ticks set Unsaved but change nothing. The spec contradicts itself (timeline: "not modelled: every stage shows"), and nothing in todo_master tracks it. | Process; `operator/_process_cards.html:301-307,337`; `spec/applications.md` l.223-224 vs l.260-261 | Code: disable them with "Not modelled yet", or remove them. Spec: align. Track in todo_master. | ACT-31, SP-08 |
| AD-10 | M | Emails says "Panel members' invitations and reminders come from Review Robin". LRG B says Review Robin emails no one on a linked gate and Apply Desk does. | Emails; `operator/_emails.html:6` | Code copy: "come from Apply Desk (AD7); Review Robin sends none for a linked gate". | ACT-33, SP-11 |
| AD-11 | M | *Send to Review Robin* and *Pull results* are disabled with no reason. The copy says a gate is sent "when its stage opens", which contradicts R24 (it may go before), and says results come back "by application" from "its panel", where R26 and R27 say by dossier and from its pairs. | Evaluations; `operator/_evaluations.html:8,33` | Code: `title="Sending comes with AD6"`; copy "Ready, even before its stage's dates", "its pairs", "by dossier". | ACT-19, SP-12 |
| AD-12 | M | The *Alias key* card says "every download is logged" in the present tense; `extract_file` logs nothing. It overclaims an audit control on the one file that undoes blind review. | Extract; `operator/_extract.html` | Code copy: "Downloads will be logged from AD2". | ACT-35 |
| AD-13 | L | Inert controls with no reason title: *New exercise* (Lobby), Emails' *Preview* and *Reset to default*, *Start an application* (`/me` exercise), and the preview's *Submit*. | `operator/exercises.html`; `operator/_emails.html`; `me/exercise.html`; `operator/form_preview.html` | Code: title each ("Exercises are created from AD3", "Applying opens with AD4", "Preview: nothing is submitted", …). | ACT-30, ACT-34, ACT-42, ACT-46 |
| AD-14 | L | The release confirm says "set with the Timeline" and the note says "as the Timeline sets"; that page is now Process (R14). | Dossiers; `operator/_dossiers.html` | Code copy: "as Process sets". | ACT-06 |
| AD-15 | L | Panels' *Sent* note on an opened gate says "changes apply from its next send", but R29 forbids re-sending an opened gate. | Panels; `operator/_panels.html` | Code copy: "Gate 1's session has opened: it keeps the roster it was sent with" (already in LRG's open list). See AD-49. | ACT-23 |
| AD-16 | L | On an Automatic gate, *Re-run* promises a recompute ("every dossier filled as its sources give"), but all it does is clear an empty change set. | Gate page | Code: hide it, or say "Nothing to re-run: the pairs are the fill's", until rosters feed the fill. | ACT-17 |
| AD-17 | L | *Extract setup* says it lets you "clone it into a new exercise", but no import exists. *Zip all* with every Carries chip off downloads a ZIP holding only `manifest.csv`. | Extract; `operator/_extract.html` | Code: "for a later import (not built)"; disable Zip all when it carries nothing. | ACT-36 |
| AD-18 | L | Ticking *Send email* or *Receipt* on Process sets Unsaved, but Emails and the status row's Emails pill read the sample, so the owed template never appears and nothing says why. | Process → Emails | Code: one line on Emails ("ticks made on Process since are not shown until AD2"). | ACT-32 |
| AD-19 | L | An operator opening a dossier from Dossiers is told "You can open this page because you are asked to review this application". | `me/dossier.html` | Code: word the line by viewer, or omit it for operators. | ACT-13 |

### 3. Workflow gaps

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| ~~AD-20~~ | H | The Publish card checks only Code, Description, Who may apply, Dates and Form (`setup_missing`). On `c4xh2ndv6s` it lists "Dates" while Process's Outline names "Gate 1 has no evaluators" and "No panel yet", against R24 ("refused while the Outline names a problem"). The spec states only `setup_missing`. The Publish button is Primary and disabled with no title. | Home; `sample_data.py:956-971`; `operator/home.html` | Code: feed the Outline's problems, owed emails and empty panels into `setup_missing`; title the button "Publishing comes with AD3". Spec: state the rule (or Ruling needed: the scaffold defers it). | ACT-28, SP-05 |
| ~~AD-21~~ | M | *Released* releases *Selection* after one confirm while every cell is undecided and both of its emails are **Owed**. Neither R16 ("an outcome with an owed email is not ready to release") nor decidedness is checked. | Dossiers | Code: disable Released while any of the outcome's emails is Owed; warn or refuse while any reached cell is undecided. | ACT-05 |
| AD-22 | M | There is no tick-all or tick-shown control, so entering 40 dossiers takes 40 clicks; *Set ticked rows* with nothing ticked does nothing and says nothing. | Dossiers | Code: a header tick for rows in view; "No rows ticked". | ACT-08 |
| AD-23 | L | The gate page, where pairs are approved, shows no gate state and no Send; the operator must return to Evaluations. | Gate page | Code: state plus a disabled *Send to Review Robin* (AD6) in the head. | ACT-18 |
| AD-24 | L | Home's *Go to Evaluations* links to the list, not to the running gate's page, where the work is. | Home | Code: link the running gate's page when there is one. | ACT-29 |
| AD-25 | L | A single approval can be undone only by Remove or by *Discard changes*, which drops everything with no prompt. *Approve all* approved 79 pairs with no prompt, including ones on a dossier just left Short. | Gate page `…/evaluations/gate_3` | Code: a second click on *Approved* revokes it; confirm Discard when more than a few changes are pending. | ACT-14 |

### 4. Applicant surface

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-26 | H | The applicant and dossier pages read hand-kept lists (`form_of`), not the Form cards. They show absent questions (*Relevant experience*, *Expected graduation*, *Financial aid*), omit present ones (*Months*, *Field of study*, *GPA*, *Photo*), print the application title against the first field ("Year of study: RA application…"), and show help text as the "answer", while Dossiers and Extract read seeded `answers`. Empty fields give an empty `<dd>` on one side and "—" on the other. | `/me` application and dossier; `me/application.html:10`; `me/dossier.html:14`; `sample_data.py:516-546,947-953`; `routes_me.py:62-63,80,383-401` | Code: render both pages from `form_cards` plus `answers`, with the title only in the header and "—" for empty; delete the lists (AD2/AD4). Until then, note the divergence in the spec. | UI-02, UI-44, DM-12, SP-14 |
| AD-27 | M | The lobby shows only `APPLICATIONS[:1]`. The applicant's draft `f2ps7nyh4k` has a page but no link, and the exercise page has no "Your application" link, so the applicant cannot get from the exercise to their own application. | User Lobby; `me/home.html`; `me/exercise.html` | Code: list each of the applicant's applications on the exercise page and in the lobby. | ACT-38 |
| AD-28 | M | *Shortlisting* is "released 6 Nov", but the applicant sees only the possible values, never their own, here or on the application page. The path ends at "released". | `/me/exercises/<id>`; `timeline.py` | Code: a *Your result* line once released to applicants (placeholder until AD7). | ACT-41 |
| AD-29 | L | A draft on an exercise whose form is Closed still shows *Save draft* / *Submit* (disabled, no title), and nothing says applications have closed. | `/me/…/applications/<draft>` on `wa9juxbc2t` | Code: replace them with "Applications closed on …". | ACT-39 |
| AD-30 | L | *Withdraw* is `btn-destructive`, where the AD1 plan gave Outline-amber; withdrawal after close or mid-review is undefined. | `me/application.html` | Code: Outline-amber; add a confirm when wired. Ruling needed: when withdrawal is allowed (FS §6, G3). | ACT-40 |
| AD-31 | L | The reviewer's dossier says "Score it in Review Robin." with no link. | `me/dossier.html` | Code: link Review Robin's `/me` (LRG B). | ACT-43 |

### 5. State and canned data

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-32 | H | Gate state and progress are canned per (exercise, key) and contradict the computed pairs. For TEA the gate is "Sent · 3 of 5 reviewed" with 2 entered dossiers and 4 pairs, while its cells already hold finished results. "Opened" is inferred from the progress string being non-empty, yet it decides editability and whether the Extract file exists. | `workflow.py:19-28,108-112`; `home_ops.py:44-61`; `extract.py:106`; `routes_operator.py:102-103` | AD2: store the gate lifecycle enum with timestamps plus `gate_transfer`; compute progress from Review Robin status pulls, never as display text. | DM-03, DM-05 |
| AD-33 | H | *Ready* is asserted, not derived. The model's Gate 3 shows Ready with all 80 pairs *Suggested* and 0 approved (R27: Ready only when every entered dossier is assigned or approved); R24's checks are unimplemented. Evaluations' card and Gates table ignore the gate page's tab work ("40 filled" against "39 filled · 1 short"). The spec never states when a gate is Ready. | `workflow.py:25`; `stages.py:1199-1210`; Evaluations vs `…/evaluations/gate_3` | Code: make readiness a service predicate (R24 + R27), or label g3 *Not ready*; reconcile Evaluations' counts or mark them sample. Spec: state Ready. | DM-04, SP-06, ACT-15 |
| AD-34 | H | R14's *Pending → Decided → Released* is reduced to Pending/Released, held in one free-text field (`released = "6 Nov · to applicants"`) and re-parsed in three places with different audience logic. No surface ever shows *Decided*. Process's per-audience release ticks have no model home, and the applicant timeline tick is hard-wired `checked`. | `stages.py:199-211,327`; `home_ops.py:68-72`; `timeline.py:129-136`; `extract.py:345`; `workflow.py:271` | AD2: `outcome.state` enum with `decided_at`/`released_at`, plus `outcome_release_audience`. Spec: name the states. Ruling needed: For the author 7. | DM-06, SP-07 |
| AD-35 | H | Page JS edits things with no model home: Details, Process cards, Form cards, Panels add/rename/retire, the Dossiers grid (cells, rules, CSV, release), gate pairs (sessionStorage) and Emails "Written". | `operator/_details.html:1-6`; `operator/_process.html:57`; `operator/_dossiers.html:7-8,198-276,705`; `operator/_panels.html:500-542`; `_gate_ops_js.html:5-11` | AD2: a save endpoint per surface. R23's granularity maps to transactions (one Save per Form/Process version as replace-the-draft, one Lock per Dossiers batch with a proposal record, ✓ per roster row). | DM-32 |
| AD-36 | M | The form state comes from `Exercise.state` + `form_open`, so a published form that has not opened reads "Closed"; drafts carry a meaningless `form_open=True`. No control opens or closes a form, though R24 needs both. | `workflow.py:101-105`; `sample_data.py:162,192` | AD2: `form.state` enum (draft/open/closed) with `opened_at`/`closed_at`. | DM-22 |
| AD-37 | M | Exercise Draft/Published/Closed/Archived are strings with no transitions. Closed and Archived have no sample, no guard and no control (R14 ends there; AD3). "Closed" means different things for the exercise and the form. `/me` hides non-Published exercises, so after Close applicants lose their released outcomes (FS §6 keeps them visible). The spec does not say Close/Archive are absent. | `sample_data.py:20`; `workflow.py:283-293`; `routes_me.py:20,36-37` | AD3: an enum with a transition table, audited, and distinct labels. Spec: "not built: AD3". Ruling needed: For the author 10. | DM-23, SP-27 |
| AD-38 | M | Application Draft/Submitted/Withdrawn is a string. `submitted` holds a date even for drafts and withdrawn applications (it acts as last-touched), and `submitted_rank` parses it. There is no withdrawn_at, return-to-draft, version or allowance per applicant. | `sample_data.py:69-70,232,378-387`; `stages.py:658-672` | AD2: `application` state enum with `submitted_at`/`withdrawn_at`/`withdraw_reason`, plus `application_transition`, `application_version`, `exercise.allowance_per_applicant`. | DM-24 |
| AD-39 | M | Emails are two canned sets per exercise keyed by (item, audience string). Template names derive from the stage label, so renaming a stage renames every template. Reminder timing is fixed text, and there is no body. | `workflow.py:53-88,126-146` | AD2: `email_template(item_kind, outcome_id NULL, audience enum, subject, body)`, unique (item, audience); compute the display name. | DM-28 |
| AD-40 | L | Three "todays": the timeline's fixed `TODAY` (17 Nov), Dossiers' hard-coded "13 Nov" stamps, and Extract's `date.today()` in ZIP names (18 Nov). Stage state is computed against the sample date. | `timeline.py:18,142,157-162`; `extract.py:142`; `operator/_dossiers.html` | Code: inject one clock (`timeline.TODAY` for now) and compute stage state in the exercise's time zone. | ACT-12, DM-33 |
| AD-41 | L | Counts disagree. The Lobby's 104 and Home's "104 received" include drafts and the withdrawn application; the status row says "100 submitted · 3 drafts". Dossiers' header says "3 draft" and the status row "3 DRAFTS". | `workflow.py:186-191,231`; `operator/exercises.html:17` | Code: one counting service with named measures and one pluralize helper. | UI-36, DM-34 |
| AD-42 | L | The sample "Institution-wide" pool is the union of every exercise's panels plus assessors (56 people for a fresh exercise). | `sample_data.py:810-826` | AD2: Institution-wide is a Graph search only, never a DB union. | DM-27 |

### 6. Identity and keys

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-43 | H | Every person (applicant, member, evaluator, nominee, pair) is keyed by an email string, normalized with `.lower()` in some places and `.casefold()` in others. There is no Person entity, and FS §2.1 requires binding by tenant and object ID. | `sample_data.py:63-71,93-100,875-891`; `stages.py:571-577,978-997,1185` | AD2: `person(tenant_id, object_id unique, email/upn/display_name snapshots)`, with every person FK pointing to it; casefold only for directory matching. | DM-01 |
| AD-44 | H | The dossier is a field on Application (1:1), but R25 and R26 make it its own record: it can exist without an application, it is built in parts and it is frozen at send. Drafts already carry dossier IDs and appear in the alias key, though R24 makes dossiers at submit or at form close. | `sample_data.py:62-71,230-233,388`; `extract.py:416-422` | AD2: `dossier`, `dossier_part`, `dossier_snapshot` tables; mint the ID at dossier creation. Ruling needed: For the author 2. | DM-02 |
| AD-45 | H | `FormCard` has no stable key or version. Rules (`form`), nominated sources, `nominees()`, answers and Extract columns all reference the question **label**. FS §5.2 requires each application to keep its form version. | `sample_data.py:562-577,829-851,866-878`; `stages.py:151-161`; `extract.py:85-92` | AD2: `form_version` (immutable once published) plus `form_field(key, …)`; answers carry (application, form_version, field_key). | DM-11 |
| AD-46 | H | Answers and nominees are seeded random draws; the model exercise's *Residence* is parsed out of `Application.title`, and Extract fabricates text, number and photo answers. Nominations (ranked, immutable after submit, audited operator changes; FS §15.3) are not modelled. | `sample_data.py:829-851,866-878`; `extract.py:228-254` | AD2: `answer` and `nomination(application, field, rank, person, added_by, removed_at)`; remove the title-encoded residence. | DM-14 |
| AD-47 | H | Pairs are recomputed by `fill()` on every request and depend on row order and the current roster, so a roster edit silently reshuffles every gate, sent ones included. Operator edits live only in sessionStorage. The server approves per dossier, the JS per pair. | `stages.py:959-1067,1199-1210`; `_gate_ops_js.html:16-51`; `routes_operator.py:100` | AD2: persist `pair(…, state, made_by)`; `fill()` becomes a one-shot proposer; snapshot at send. Ruling needed: For the author 4. | DM-15 |
| AD-48 | M | Gate keys (`g1`) repeat across exercises, and new ones are minted client-side (`gnew3`). The gate **number** is positional (JS renumbers by order), yet it is the public handle in `/evaluations/gate_<n>` and in Extract file names, so inserting a gate re-points links. | `stages.py:278-354,1070-1073`; `routes_operator.py:95-97,203-208`; `operator/_process.html:320,818,944` | AD2: a surrogate PK plus a per-exercise unique key; URLs use a stable handle, with the number for display only. Ruling needed: For the author 5. | DM-18 |
| AD-49 | M | A gate keeps both a legacy `panel` and `sources`. `panel_uses` and `panels_sent` read only `.panel`, so a second-rank or nominated source is invisible to *Used by*, the Retire guard and *Sent*; *Sent* also keys off Sent, not opened (R29, already recorded). The sample hides this (`panel == sources[0]`), and a stale comment says "until AD1G rung 3". | `stages.py:180-186,737-750,858-869`; `workflow.py:314-323`; `operator/_panels.html:65` | Code: read `sources`; key *Sent* off opened; fix the comment. AD2: store only `gate_source` plus `gate.total_min/max`. | DM-16, SP-26 |
| AD-50 | M | One concept has four shapes: Panel, Member, Evaluator (a copy of Member) and Assessor (`asked_to_review`, a second assignment model). The keys "pool" and "interviewers" carry special meaning. A per-membership `note` is merged per person, there is no `retired` flag (retire is JS-only), and FS caps (5 panels × 200) are not modelled. | `sample_data.py:74-112,414-417,507-511,881-901,986-991` | AD2: `panel(…, retired_at)` and `panel_member(panel, person, note)`; drop Assessor and Evaluator (pairs replace them, R27); enforce caps in the service. Ruling needed: For the author 8. | DM-26 |
| AD-51 | M | `GateResult.field` duplicates the `ResponseField` it collates. A gate with no fields gets synthesized keys `f1…` that would become Review Robin's prescribed field keys. Result keys `r1..r3` are positional, and `r1` is special-cased into `Cell.result`. | `stages.py:104-137,627-634,1230-1254` | AD2: `gate_field(key stable, …)` and `gate_result(key, position, field_id FK, …)`, with the headline as position 1. | DM-17 |
| AD-52 | M | "Invitation only" is a display string with no invitee list, though FS §4.3 requires a server-side check. | `sample_data.py:22` | AD2: `exercise.eligibility` enum plus `exercise_invitee`. List upkeep (manual/CSV) has no roadmap home. | DM-31 |
| AD-53 | L | Exercise, application and dossier IDs share one namespace in practice; the sample's de-dup set omits two written application IDs and every written dossier ID (no collision today, 221/221). | `ids.py:15-28`; `sample_data.py:363` | AD2: a unique index per table on `public_id`, with retry on conflict; keep the dossier ID unrelated to the application ID (R13). | DM-36 |
| AD-54 | L | Help contact and time zone fall back to module constants. Details marks the time zone "the default" when it *equals* Asia/Singapore, so explicit and inherited look the same. Code uniqueness is checked client-side only and allows "". | `sample_data.py:31-59`; `operator/_details.html:19-20,96`; `routes_operator.py:57-61` | AD2: an `operator_settings` row, nullable exercise columns resolved in the service, a unique index on `lower(code)` where not null, and server-side IANA validation. | DM-29 |
| AD-55 | L | The field is `summary`, but every page calls it "Description" (`data-dt="description"`). FS §4 also lists purpose and public instructions separately. | `sample_data.py:27,963-964`; `operator/_details.html:16,32` | AD2: name the column `description`; decide whether purpose and instructions are columns. | DM-30 |

### 7. Typed values

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| ~~AD-56~~ | H | Stage dates are free text ("1 Sep – 30 Sep") with no year or time zone, read by three parsers (a regex in `timeline._dates`, `split("–")`, and `split(" – ")` in a template). Outcome `due` and `expected_outcome` ("Early March 2027") are free text too. | `stages.py:205,220,393-395`; `timeline.py:87-106`; `workflow.py:282`; `operator/_process_cards.html:319,335-336` | AD2: `stage.starts_at`/`ends_at` (timestamptz, in `exercise.timezone`) and `outcome.due_on` (date); keep `expected_outcome_text` only if explicitly labelled text. Ruling needed: For the author 9. | DM-19 |
| AD-57 | H | Outcome values are bare strings: cells, rules (`then`/`otherwise`, `out … is X`) and emails store the label, so a rename orphans them. Whether a value "takes the application on" is positional (every value but the last). | `stages.py:204,479-492,545-549,562` | AD2: `outcome_value(key, label, order, advances)`; cells and rules reference keys. | DM-07 |
| AD-58 | H | `Cell.value` holds admittance or outcome value as display text, with two different "nothing" values ("" and "—"). `note` mixes dates, reasons and result summaries; `r1` is a float while `r2`/`r3` are text in `extra`. There is no who, when, or proposal history (R13). | `stages.py:21-25,230-238,475-492,627-655` | AD2: split into `gate_entry`, `gate_result_value` and `outcome_decision` (with set_by, reason, by, at), and audit each Lock. | DM-08 |
| AD-59 | M | The form window lives in three places (`Exercise.opens`, `application_stage_ends`, the form stage's `dates`); the timeline's milestone reads one and its track another. | `sample_data.py:24-25`; `stages.py:514-522`; `timeline.py:116-123` | AD2: one source, the form-holding stage's start and end (FS §6 hard deadline). | DM-20 |
| AD-60 | M | "Not set" and "Dates not set" are stored as data values and tested by string comparison. | `sample_data.py:163-167,193-197,965-968`; `timeline.py:120,137`; `stages.py:518-520` | AD2: NULL; presentation maps NULL to "Not set". | DM-21 |

### 8. Rules

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-61 | H | There is no server-side rule evaluator. Python only renders rules and seeds cells; branches, `form`, `top` and `last`, and the validity checks, run only in page JS. Agreement between seeds and rules (1 mismatch in 100, the by-hand cell) is designed in, not enforced. | `stages.py:683-734`; `operator/_dossiers.html:372-560`; `operator/_process.html:474-490` | Code/AD2: a `services/rules.py` that is the one source; the page asks it for proposals, saving re-validates, and it is unit-tested against the JS until the JS retires. | DM-09 |
| AD-62 | H | Rules reference entities by loose strings ("g1.r1", outcome key, gate key, question **label**). A removed target reads "(removed)" and is never rejected; "a gate never reads another gate" is enforced only in JS. | `stages.py:28-56,592-596,683-718`; `sample_data.py:854-863` | AD2: validated JSON with typed references, a dependency index (refuse or cascade deletes and renames), and scope validation on save. | DM-10 |
| AD-63 | M | FS §1, §10.2 and §15.3 say "no decision engine", but R13 and R30 add a branching engine with best-N. Ruling 27's Automatic mode "spreads the work evenly", against FS §7.7's ban on balancing quotas. Neither override is recorded, and a persisted rule shape is hard to retract. | `spec/applications.md`; FS §7.7, §15.3; `stages.py:28-56` | Ruling needed: confirm the engine and the even-spread override (For the author 1). If confirmed, keep rules as proposals (AD-58, AD-61). | DM-37 |

### 9. Visibility and confidentiality

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-64 | M | There are three visibility vocabularies: a per-card `shown` flag (meaningless on text cards), FS §5.1's section Shown/Not shown, and R26's parts with audiences and a visible-from stage. The roadmap's AD4 and the open decision "Card visibility beyond Shown / Not shown" still ignore R26, and the spec gives no notice of the change. | `sample_data.py:577`; `spec/applications.md` l.129-130; `guide/todo_master.md` l.545, 574-576 | Ruling needed (For the author 3), before AD4: model `form_section → dossier_part`; reword AD4 and narrow the open decision. | DM-13, SP-15 |
| AD-65 | M | `Exercise.blind` and `Gate.confidential` overlap. Blind redacts the dossier and hides names on the gate page; confidential changes only Extract defaults, so a confidential gate's page still searches and sorts by name. `outcomes.csv` names applicants by default even when blind. | `routes_operator.py:108,133`; `stages.py:1096-1149`; `extract.py:123-137`; `routes_me.py:67-81` | Code/AD2: one visibility policy service; record which identity form each gate sent. Ruling needed: For the author 6. Lock: AD-05. | DM-25 |
| AD-66 | M | Dossiers' client-side *Download CSV* writes cells with no guard on `=`, `+`, `-`, `@`, ignores the filter, and is named `applications.csv`, clashing with Extract's differently shaped file of the same name. | Dossiers; `operator/_dossiers.html:~710` | Code: reuse Panels' `csvCell` guard; name the file `<code>_dossiers_<date>.csv`. | ACT-09 |
| AD-67 | L | The confidential identity (Dossier ID or R10's per-handoff alias) is listed as open, yet the UI presumes both: Extract's *Alias key* maps `dossier_id ↔ application_id`, while Details and Evaluations promise "an alias key in place of each application ID". | `extract.py:34`; `operator/_details.html:27`; `operator/_evaluations.html:33`; `guide/todo_master.md` l.513-514 | Ruling needed (For the author 11); then align the copy. | SP-23 |

### 10. Component consistency

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-68 | H | A pressed `.btn-toggle` is identical to Primary (bg rgb(190,18,60), white text), so the Carries chips read as more Zip buttons. The off state (rose outline) is a look Review Robin §6 does not have. | Extract; `base.html:466`; `operator/_extract.html:12-14` | Code: off = Secondary tokens per §6; better, reuse `.pn-show` pills for these multi-select chips (ask first per CLAUDE.md). | UI-03 |
| AD-69 | M | Five on/off primitives (`.seg` 34px, `.btn-toggle` 36px, `.pn-show`, `.tl-switch`/`.theme-toggle`, checkboxes). Like flags get unlike controls: Form's "Shown" is a `.seg` but Process's "Shown to applicants" is a checkbox; "Required" is a toggle but "Blind review" is a checkbox. | `operator/_form_cards.html`; `operator/_process_cards.html`; `operator/_details.html`; `operator/_extract.html:12-14` | Code: `.seg` for one-of-N, the §6 Toggle for per-row flags, pills for multi-select chips; ask before any new variant. | UI-04 |
| AD-70 | M | Lock/unlock varies: revert is "Discard changes" (Details, gate page) or "Undo changes" (Dossiers); Lock is Primary on Details, Secondary on Dossiers. The dirty marker has three forms (`.fb-unsaved` bold amber, `.ap-changes` "N changes since unlocked", `.pn-unsaved` 12px). | `operator/_details.html:10,38`; `operator/_dossiers.html:25-27,228,238`; `operator/gate_evaluations.html:30-31`; `operator/_panels.html:602,840`; `base.html:340,530,558` | Code: one vocabulary (Unlock / Lock / Discard changes), one Lock role, one marker class. Spec: record it. | UI-09 |
| AD-71 | M | Removal roles and verbs vary: Delete (Destructive) for stage and question cards; "Remove the gate/outcome/field/result" (Destructive); "Remove the form" and the gate page's "Remove" (Secondary); "Retire" (Destructive). | `operator/_process_cards.html:44`; `operator/gate_evaluations.html:84`; `operator/_form_cards.html:106`; `operator/_panels.html:65` | Code: one rule ("removing a builder item → Destructive 'Remove …'"; Delete only for whole cards). | UI-11 |
| AD-72 | M | Creating a panel is "Add panel" (Secondary) on Panels but "Create panel" (Primary) inline on Form and Process. "Add" appears as "+ New", "Add new", "+ Pair" / "Add the pair", "+ Stage". | `operator/_panels.html:95,122`; `operator/_panel_pick.html:33`; `operator/_form_cards.html:11`; `operator/gate_evaluations.html:28,37` | Code: one label and role for creating a panel; "+ X" for builders, "Add new" for toolbars. | UI-12 |
| AD-73 | M | CSV verbs differ: Upload/Download CSV (Dossiers), Import/Export CSV (Panels), and "Download CSV", "CSV", "Download key", "Zip all", "Zip gates", "Zip setup" (Extract). | `operator/_dossiers.html:22,121`; `operator/_panels.html:101-102`; `operator/_extract.html:36-83` | Code: Upload/Download CSV (Review Robin's wording) and "Download ZIP". | UI-13 |
| AD-74 | M | Four Primary buttons in one Extract grid (Zip all, Download CSV ×2, Zip gates), with Alias key and Extract setup Secondary; §6 reserves Primary for a region's single main action. | `operator/_extract.html:16,76,83` | Code: Zip all the one Primary, per-file downloads Secondary. | UI-14 |
| AD-75 | M | The same state has different tones: "Draft" mute (Lobby) vs amber (status row, Home); "Closed" green (timeline), blue (status row) and amber (`_state_chip`); "Pending" mute (Home) vs amber (Dossiers). | `_state_chip.html:1`; `workflow.py:169-170`; `_timeline.html:23`; `home_ops.py:41,72`; `operator/_dossiers.html:155` | Code: one state→tone map in Python (`workflow.TONES`) read by every template. | UI-18 |
| AD-76 | M | Two chip systems sit on one Dossiers row (`.chip` uppercase 500 vs `.ap-adm`/`.ap-oc` sentence case 600, bordered). Panels turns uppercase off; Form puts whole option lists into uppercase chips. | `base.html:299,377-385,542` | Code: `.chip` for short states only; type summaries as muted text; document the cell pill as its own primitive. | UI-19 |
| AD-77 | M | Four table looks; none has Review Robin §7's row hover; rows use `--border-subtle` where §7 uses `--border-default`. Only Panels matches §7's header. | `base.html:235-236,305-307,354-357,585-586` | Code: base `th` to §7 (muted fill, 500, border-default) plus hover; remove restating overrides. | UI-20 |
| AD-78 | M | Three search patterns in three positions: Dossiers (placeholder-only, live), Panels (visible "Filter", live), the gate page (visible label, Find/Clear, server). | `operator/_dossiers.html:15`; `operator/_panels.html:121`; `operator/gate_evaluations.html:44-49` | Code: one toolbar search with a visible label; server paging may keep its submit. | UI-21 |
| AD-79 | M | Five empty-state shapes on the blank draft (h2 card, "No emails yet" card, muted line, table row, header-only table). Controls that act on nothing stay live: *Unlock* over "No applications yet", and Extract's chips while every download is disabled. | `operator/_evaluations.html:5-15`; `operator/_emails.html:15-19`; `operator/_extract.html:24`; `operator/_dossiers.html:101`; `operator/_panels.html:128-158` | Code: one empty-state block (muted card, title, one line, a link to the fixing page); disable controls over nothing. | UI-29, ACT-11 |
| AD-80 | L | Row counts are phrased three ways ("Showing 104 of 104" at the foot, "1–200 of 2,980" at the top, none on Panels), and assignments are "rows", "pairs" and "dossiers". | `operator/_dossiers.html:314`; `operator/gate_evaluations.html:56`; `operator/_evaluations.html:66-67` | Code: one count format; "pairs" for assignments. | UI-22 |
| AD-81 | L | `.btn` is weight 600 (Review Robin 500), contexts reshape it (28px, 13px, 38px, 34px), and only Secondary has a hover. | `base.html:310-320,471,563,656-667` | Code: hover tokens per role, weight 500, one documented "short" modifier. | UI-34 |
| AD-82 | L | The Primary side flips: right on Details, left on Dossiers' proposal and the gate page, middle on Panels' Manage (Cancel → Save → Close). | `operator/_details.html:38`; `operator/_dossiers.html:51`; `operator/gate_evaluations.html:37-38`; `operator/_panels.html:111-113` | Code: dismiss left, Primary right, everywhere. | UI-41 |
| AD-83 | L | Panels' column sort is two-state asc/desc with no clear or cascade; the gate page's is three-state with shift-cascade, "as Review Robin's". | `operator/_panels.html` | Code: reuse the gate page's behavior client-side. | ACT-24 |
| AD-84 | L | Panels exports `panels-<id>.csv` wide (a column per panel), while Extract setup's `panels.csv` is long (panel, name, email, note). | Panels; Extract | Code: share one shape, or note the difference on Extract setup. | ACT-25 |
| AD-85 | L | Page intros differ: `.lede` (Lobby), `muted pc-intro` (Process, Panels), a plain `<p>` (Emails), `.ap-help` at the bottom (Dossiers), and none on Form, Evaluations or Extract. | `operator/exercises.html:4`; `operator/_process.html:16`; `operator/_panels.html:40`; `operator/_emails.html:6`; `operator/_dossiers.html:124` | Code: one `.lede` under the h1 on every operator page. | UI-28 |
| AD-86 | L | `/me` application and dossier use `.section` (1px subtle) where the lobby uses `.card` (2px default); `.section p.muted` keeps 16px browser margins. | `base.html:120,321-323`; `me/application.html` | Code: use `.card`. | UI-42 |
| AD-87 | L | Blind dossier IDs are plain text on the gate page but `<code>` on Dossiers. | gate page vs Dossiers | Code: monospace everywhere. | UI-43 |
| AD-88 | L | Emails' Subject renders bold (inherits `.field label` 600 through `font: inherit`); its textareas show a resize handle, unlike every other `data-fit-box`. | `base.html:126-128`; `operator/_emails.html:11-12` | Code: `font-weight:400` on `.field input, .field textarea`; use `data-fit-box`. | UI-30 |

### 11. Terminology

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-89 | M | Dossiers mostly says "application": its group header, its "Application" column (showing the application ID but linking by `dossier_id`), its search label, its footer and its help. Elsewhere: "Applications:" (status row), "Dossier IDs" (Extract), "100 dossiers" (Evaluations), "Applications I am asked to review" (linking to dossiers). The dossier page never shows its Dossier ID. | `operator/_dossiers.html:15,58-63,84,108-110,124`; `operator/_extract.html:33,47`; `me/home.html:19`; `me/dossier.html` | Code: Dossiers rows named by Dossier ID (R13, R25); align header, search, footer and status row; show the ID on the dossier page. | UI-15 |
| AD-90 | M | Evaluators are "evaluators" (Process, Evaluations), "reviewers" (Form chips, Panels, `/me`), "assessors" (`/me` application, directly under "Shown to reviewers"; Details' blind note) and "Panel evaluators" (Emails); applicants are also "Candidate". The Lobby lede says exercises are "named by its own ID", though they are named by Exercise Code. | `me/application.html:7-9`; `me/home.html:18`; `operator/_details.html:27`; `operator/gate_evaluations.html:36,47`; `operator/_panels.html:40`; `operator/exercises.html:4` | Code copy: one operator term (evaluator, R16/R27) and one applicant-facing term, then sweep. Ruling needed: For the author 12. | UI-16, SP-25 |
| AD-91 | L | Gates are named six ways, including "GATE 1 · RRW" (an internal abbreviation and the leftover *Runs as* value, R28), "1 · Peer review", "Gate 1 Peer review" and a bare "Gate 1". The Type column says "Review Robin" where Dossiers says "RRW". | `operator/_dossiers.html:63,68`; `stages.py:177`; `operator/_extract.html:52`; `operator/_evaluations.html:44-45,64`; `_timeline.html:30` | Code: "Gate 1 · Peer review" everywhere; drop `via: "RRW"`. | UI-17, SP-24 |
| AD-92 | L | Developer jargon: "String" as a field type (Form, Process), "RRW" (Dossiers), and the identifier `ProfileLink` in Evaluations' copy. | `operator/_evaluations.html:53`; Form/Process type menus | Code: "Text" / "Long text"; spell out Review Robin; describe the link in words. | UI-38 |
| AD-93 | L | Visibility chips are asymmetric: "SHOWN TO REVIEWERS" / "NOT SHOWN" on cards but "SHOWN" / "NOT SHOWN" in the Outline. | Form | Code: "Shown" / "Not shown" in both; name the audience once in the intro. | UI-39 |
| AD-94 | L | "Exercise Code" is Title Case among sentence-case labels; the sample gate "Panel Review" (k7) is too. | `operator/exercises.html:9`; `operator/_details.html`; `sample_data.py:962` | Code: "Exercise code"; fix the sample label. | UI-37 |
| AD-95 | L | Email template names use an ASCII hyphen ("Applications: Receipt - Applicants"), where everywhere else uses " · ". | Emails (names from `workflow.py`) | Code: " · ". | UI-31 |
| AD-96 | L | "Applicants as" options are ordered Names \| Dossier IDs on one card and Dossier IDs \| Names on the next. | `operator/_extract.html:33` vs `:47` | Code: one order; let the default move the selection. | UI-32 |
| AD-97 | L | Many date formats: "30 Sep 2026, 23:59", "1 Sep – 30 Sep" (no year), "1 Sep to 4 Dec 2026", "3 Sep 2026", "Due 4 Dec", "EXPECTED DECEMBER 2026", and stage fields "1 Oct". | `timeline.py:18`; Home, Dossiers, Extract | Code: one short-date helper (`timeline.short`); ranges "1–30 Sep 2026". Clock: AD-40. | UI-35 |
| AD-98 | L | The switcher's *All applications* (host link to Cordware's landing) reads as "every application in this exercise" in an app whose records are applications. | Chrome switcher | Raise with the host chrome: "All apps" / "Cordware home". | ACT-44 |

### 12. Accessibility and navigation

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-99 | H | Keyboard focus is invisible on the chrome tabs, `.seg`, `.tl-switch` and `.theme-toggle`: `overflow:hidden`/`auto` containers clip the default ring, and only two `:focus-visible` rules exist. A focused "Names" shows no ring; "Process" shows a 1px sliver. | `base.html:89,141,269,278,463` | Code: `:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px }` on `.xnav-tab`, `.xnav-home`, `.seg button`, `.tl-switch button`, `.theme-toggle button`, `.pn-show` and `.btn`. | UI-01 |
| AD-100 | M | The gate page's breadcrumb ends at "Evaluations" with `aria-current="page"`, and a separate "← Evaluations" link repeats it. | `_exercise_nav.html:6`; `operator/gate_evaluations.html:16` | Code: a child crumb (Evaluations → Gate 1 · Peer review), as `operator_session_child` does; drop the back link. | UI-24 |
| AD-101 | M | The `/me` exercise, application and dossier pages have no breadcrumb or back link; the only way back is the switcher. | `me/exercise.html`; `me/application.html`; `me/dossier.html` | Code: "User Lobby / {page}" with `.crumbs`. | UI-26 |
| AD-102 | L | The crumb root is "Exercises", but the page it links to is "Operator Lobby" (h1, switcher, `<title>`). At 390px "Exercises /" sits alone on a line. | `_exercise_nav.html:6`; `operator/exercises.html:3`; `web.py` PLACES | Code: name one or the other consistently; wrap each crumb with its separator. | UI-25 |
| AD-103 | L | Headings skip h1 → h3 on Panels, Dossiers and `/me` application and dossier; the gate page has no section headings. | rendered outlines | Code: h2 for top-level card heads. | UI-27 |
| AD-104 | L | Esc does nothing in Details (Panels and + Pair close on Esc) or in Dossiers' proposal panel. Details' *Discard changes* says "Changes discarded." when nothing changed. | Home Details; Dossiers proposal | Code: Esc = Discard / Cancel; say nothing when nothing changed. | ACT-27, ACT-47 |
| AD-105 | L | In dark mode `--text-strong-subtle` equals `--text-subtle` (#a9b4c6), so the lede, group headers and mute chips lose their step. | `base.html:30` vs `:52` | Code: a lighter dark value (e.g. #c7d0de). | UI-45 |

### 13. Layout and phone

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| ~~AD-106~~ | M | The Publish card sits flush (0px) against the timeline/Details grid: `.hm-grid + .card` never matches because a `<script>` sits between them. | Home `n5wg8tjr3e`; `base.html:135`; `operator/home.html:17-38` | Code: move the script after the card, or give `.hm-publish` its own `margin-top:16px`. | UI-07 |
| AD-107 | M | Evaluations' "Assignments" h2 is 24px (browser default) against the page h1's 22px; `.ev-h` sets only margins. | `base.html:693` | Code: give `.ev-h` 17–18px, or make it a card head. | UI-08 |
| AD-108 | L | The gate page's pager is above the table only; it uses an undefined `.btn-icon` plus bordered link-blue `.ev-step` boxes; at 390px "›" and "»" wrap to a second line. | `operator/gate_evaluations.html:55-60`; `base.html:703-706` | Code: port `.btn-icon`, repeat the pager below, `flex-wrap:nowrap` on the step group. | UI-23 |
| AD-109 | L | Breakpoints at 959, 899, 736, 720, 640, 639 and 1116px; `.ps-row` collapses at 640 (off by one) and the chrome stacks at 720. | `base.html:100-101,110,136,241,291,328-329,547,690` | Code: ≤639 / ≤899 plus Form's documented 736/1116; move 640→639, 720→639 or 899. | UI-40 |
| AD-110 | L | `.xd-csv { min-height:30px }` loses to `.btn`'s 36px (same specificity, later), so By-gate CSV buttons sit low. | `base.html:237` vs `:310` | Code: `.btn.xd-csv`, or move the rule after `.btn`. | UI-33 |

### 14. Spec and doc drift

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-111 | H | The spec's normative URL map points into the unclosed AD1 plan, which lists `/gates` as live (404), strikes `/panels` (live), describes `/extract` as "every evaluation response collated", `/dossiers` as "generate applicant profiles", and `/me` as "My ApplyDesk". | `spec/applications.md` l.46-47 → `guide/segment_AD1_skeleton.md` l.20-48; `web.py:101-111`; `routes_operator.py:21,232-236` | Spec: move the current URL table (Home, process, form, form/preview, panels, emails, dossiers, evaluations, evaluations/gate_<n>, extract, extract/<file>, `/me` rows) into `spec/applications.md`; then close AD1. | SP-01 |
| AD-112 | M | The "Built so far" headers are stale. `spec/applications.md` names only AD1, AD1B and AD1E (it omits AD1F to AD1J). `spec/architecture.md`'s layout and the README index omit 7 of 16 modules (`stages.py`, `workflow.py`, `timeline.py`, `home_ops.py`, `extract.py`, `paging.py`, `lookups.py`), and both still call AD1 placeholders the whole product. | `spec/applications.md` l.3-8; `spec/architecture.md` l.3-24; `README.md` l.3-12 | Spec/README: rewrite the headers and add the modules. | SP-02, SP-03, SP-04 |
| AD-113 | M | Most of what Dossiers ships and tests has no spec text: search, status filter, *All / Last applications*, the CSV format (`Application ID` plus header-named columns, `-` for —), the Download/Upload round-trip, the *Released* confirm, and the lifecycle buttons. It lives only in the unclosed AD1C plan. | `spec/applications.md` l.494-518; `tests/test_applications_browser.py:95-215` | Spec: write the section from AD1C's Semantics and rungs 5–6; then close AD1C. | SP-10 |
| AD-114 | M | AD1, AD1C and AD1D are still "Building" though done or superseded, with seven later segments closed on top. Their prose cites dead paths (`rounds.py`, `operator/_workflow.html`, `me/file.html`, `operator/_applications.html`, `rounds.combined`) and retired terms (Gates, Applications, the Workflow card, rounds, *application file*, Reports, "My ApplyDesk"). The README rows (and the `docs/chrome/` row) still say "rounds of gates" and "the Workflow card". | `guide/segment_AD1_skeleton.md` l.77-85; `guide/segment_AD1C_applications.md` l.182-192; `guide/segment_AD1D_chrome.md` l.60-69; `README.md` l.17,21-25 | Plans: close all three with Status (intended vs done) and archive them; update the README rows. | SP-18, SP (stale prose) |
| AD-115 | L | The Operator Lobby, the User Lobby and the applicant's application page have no spec section, though their columns, counts and *Withdraw* are tested. | `operator/exercises.html`; `me/home.html`; `me/application.html`; `tests/test_pages.py:268-285,329-349,973-980` | Spec: a short section each. | SP-30 |
| AD-116 | L | The Emails section is two lines; it omits Subject/Body, *Preview*, *Reset to default* and the empty state. | `spec/applications.md` l.702-705 | Spec: extend with AD1K. | SP-31 |
| AD-117 | L | Seven tests pin the removed Workflow card's copy ("Send…", "Open form…", "Close…", "Extract data first", "Not ready: its emails…"); the spec says only that `workflow.steps` names the current stage. | `workflow.py:213-295`; `tests/test_pages.py:855-956,1019` | Tests: reduce to current stage and Next, or record the steps contract in the spec. | SP-29 |
| AD-118 | L | The README's photo row and `docs/photo_field_design.md` say the field is "not scheduled" with a fixed 4:5 / 480×600 ratio. R12 put it in the MVP with a ratio per question, and Form builds it. | `README.md` l.16; `docs/photo_field_design.md` l.3-7,40,68,76 | Docs: a superseded note on the design doc; fix the README row. | SP (stale prose) |
| AD-119 | L | Code comments describe removed behavior: "placeholders on sample data, controls inert"; "A placeholder until its own segment" (Evaluations, Emails). The `sample_data.py` comment on the two lists is true but untracked (AD-26). | `routes_operator.py:1-2`; `operator/_evaluations.html:2-3`; `operator/_emails.html:3-4`; `sample_data.py:541-546` | Code: update the comments. | SP (stale prose) |
| AD-120 | L | The test files `test_applications.py` and `test_applications_browser.py` still name the page Applications (R25: Dossiers). | `tests/` | Code: rename when next touched (cosmetic). | SP (stale prose) |

### 15. Roadmap and rulings

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-121 | M | Roadmap rows describe retired designs. AD8 is "Dashboard and Reports: every evaluation response collated" (Reports became Extract, R14; AD1J built the bundle; R11's text still says it). AD6 has "pairs as tags" (R27 sends `relationships.csv`) and "rosters from submitted applications" (R25/26: from dossiers). AD5 has "dossiers generated" (R26 replaced). R9's "decided at AD6" is unannotated. | `guide/todo_master.md` l.38-53, 546-549 | Roadmap: rewrite AD5, AD6 and AD8; annotate R9 and R11. | SP-16, SP (stale prose) |
| AD-122 | M | Layer B (Send, Re-send, Status, Results, Link state, Invite and remind) has no roadmap row, though "Order" says it is a new segment; the "AD1K onward" row names only Emails. | `guide/todo_master.md` l.529-531, 537-550 | Roadmap: add a row for B and one for Emails (AD1K). | SP-17 |
| AD-123 | L | Superseded rulings are not annotated or struck. "Ruling 24's 'after opening…'" and "tags… settled by 23F" are still listed as unsettled (R29 and 23F settled them). R15 cites stages *Call for applications … Decision* (the model has three, R30). R20's "control card floating on the right" is not how Panels works (R22, R23). LRG A says help contact and time zone are "on Setup" (they are in Home's Details). R15 l.129 and R24 l.279-281 still cite the "Dossiers item", which R26 struck; so does the spec (l.497-498). | `guide/todo_master.md` l.129-156, 211-212, 279-302, 456, 508-527; `spec/applications.md` l.497-498 | Rulings: strike or annotate each with its superseding ruling; drop "Dossiers item" from the spec. | SP-19, SP-20, SP-21, SP-22, SP (stale prose) |
| AD-124 | L | Follow-ups recorded only in closed plans are missing from todo_master: a list headline (Result 1) has no value on Dossiers (AD1F); a panel used twice or a max above its panel's size is not flagged (AD1G); canned gate progress beside counted pairs (AD1I; see AD-32); drag has no Escape or auto-scroll (AD1B). | `guide/archive/` Status blocks | todo_master: add them, or rule them accepted (For the author 13). | SP-28 |

### 16. Performance

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-125 | M | `plan_of` runs 4–14 times per request and `fill` 1–8 times (Extract page 12 + 3; `all.zip` 14 + 8). The gate page sorts all 2,980 pairs into a 151 KB page; Dossiers is 410 KB for 104 rows; the section route builds every section's data whatever the tab. No load test or over-envelope warning exists (FS §7.8, §14). | `routes_operator.py:232-321`; `extract.py:286-302,366-410` | AD2: a request-scoped loader with eager loads, stored pairs (AD-47), SQL paging and sorting for the gate page, and per-section context. | DM-35 |

## For the author

1. *Ruled (R31):* engine confirmed; evaluation design open. **Rule engine scope.** Is the branching, best-N engine (R13, R30) confirmed for the MVP despite FS §15.3's "no decision engine", and does Automatic's even spread override FS §7.7? Does evaluation move server-side at AD2? → AD-61, AD-62, AD-63
2. *Ruled (R32):* own table at AD2, minted at submit (proposed). **Dossier at AD2 or AD5?** Its own table at AD2, or a column until AD5? Is the ID minted at draft, at submit or at form close? → AD-44, AD-08
3. *Ruled (R33):* per dossier part. **Visibility vocabulary.** Per-card `shown`, section Shown/Not shown, or R26's parts with audiences: which one does AD2 persist? → AD-64, AD-26, AD-93
4. *Ruled (R34):* per dossier. **Approval granularity.** Under *Suggested, then approved*, is approval per pair (as the JS does) or per dossier (as the server reads)? Is it revocable? → AD-47, AD-25, AD-33
5. **Stable gate handle.** Should gate URLs and Extract file names use a stable key, not the positional number? → AD-48
6. *Ruled in part (R35):* blind locks when its stage is published; `confidential`'s reach still open. **Blind and confidential.** Is `blind` locked at publish or at the first send? Does a gate's `confidential` redact the dossier for its evaluators and hide names on its page? → AD-05, AD-65
7. **Outcome lifecycle.** Is *Decided* a stored state distinct from "every cell has a value"? Is release per audience with separate times? → AD-34, AD-21
8. **Panel roles.** Do "pool" and "interviewers" keep any special meaning, or are all panels generic? → AD-50
9. **`expected_outcome`.** A free-text estimate for applicants, or derived from the last outcome's `due_on`? → AD-56
10. **Exercise "Closed".** Is it the moment of the last release? What do applicants still see on `/me` once an exercise is Closed or Archived? → AD-37, AD-28
11. **Confidential identity.** Is it the Dossier ID or R10's per-handoff alias key? → AD-67, AD-12
12. **Terms.** Which term is the operator's (evaluator?) and which the applicant-facing one; and is the operator root "Operator Lobby" or "Exercises"? → AD-89, AD-90, AD-102
13. **Publish and scaffold debts.** Should the scaffold's Publish checklist carry Process's Outline problems now, or defer to AD3? Should the four untracked closed-plan follow-ups be tracked or accepted? → AD-20, AD-124
14. **Withdrawal and return to draft.** When may an applicant withdraw (FS §6, G3), and where does the operator's *Return to draft* (individual and bulk, FS §6) live? → AD-30, AD-08
15. **Shown to applicants.** Remove the per-stage tick, or model it? → AD-09
16. **New primitives.** May Extract's Carries chips become `.pn-show` pills, and which control is canonical per job (CLAUDE.md asks before a new variant)? → AD-68, AD-69

## Appendices

### (a) Proposed entity sketch (from the data-model lens)

Each table has a surrogate `id`, every `*_at` is timestamptz, and `→` marks an FK.

- **person**: tenant_id + object_id (u); email, upn, display_name snapshots. **operator_settings**: default help contact and time zone.
- **exercise**: public_id (u), code (u, nullable), name, description, eligibility enum, blind (locked at publish), timezone, help_contact, expected_outcome_text, allowance_per_applicant, anticipated_applicants, state enum + published/closed/archived_at. **exercise_operator** (→ person, role); **exercise_invitee** (→ person or email).
- **stage**: → exercise, position, name, starts_at, ends_at; at most one form and one outcome.
- **form**: → stage (u), state enum, opened/closed_at, sends_receipt, sends_reminder. **form_version** (immutable once used) → **form_section** (→ dossier_part) → **form_field** (key stable across versions, type, label, help, config JSON, required, order).
- **application**: public_id, → exercise, → person, → form_version, state enum, submitted/withdrawn_at, withdraw_reason. **application_transition**; **answer** (field_key, value JSON); **nomination** (→ form_field, rank, → person, added_by, removed_at).
- **dossier**: public_id, → exercise, → application NULL, source (form/upload). **dossier_part** (audience enum, visible_from → stage); **dossier_snapshot** (→ gate, frozen content).
- **panel** (key u per exercise, retired_at); **panel_member** (→ person, note; u panel+person).
- **gate**: → stage, key (u per exercise), position, label, confidential, mode, total_min/max, entry_rule JSON, state enum + sent/opened/results_in_at. Children: **gate_source** (rank, kind, → panel / → form_field, min, max); **gate_field**; **gate_result** (key, position, → gate_field, derive…); **gate_transfer** (transfer_id, rrw_session_code, payload_hash, link_state, last_status); **pair** (→ dossier, → person, source_rank, state, made_by, removed_at); **gate_entry** (admittance NULL = undecided, set_by, reason, by, at); **gate_result_value** (num, text, n_responses, pulled_at).
- **outcome**: → stage (u), key, label, due_on, rule JSON, state enum, decided/released_at. **outcome_value** (key, label, position, advances); **outcome_weight** (→ gate_result); **outcome_release_audience** (audience, update_timeline, send_email); **outcome_decision** (→ dossier, → outcome_value NULL, set_by, reason, by, at).
- **email_template**: → exercise, item_kind, → outcome NULL, audience, subject, body (u item+audience).
- **dossiers_lock / proposal**: the Lock batch and rule/CSV proposals, as changes JSON for audit. **audit_event**: Review Robin's envelope.

### (b) Functional-spec coverage (FS § → home)

| Requirement | Home |
|---|---|
| Entra sign-in by tenant + object ID (§2.1) | AD2 |
| Exercise configuration (§4.1-2) | AD3; Home Details scaffold |
| Application → Review hard deadline (§6, G3) | AD3, partly; not restated after R15 |
| Invitation-only, server-checked; list upkeep (§4.3, §13.1.2) | AD4; list upkeep **none** |
| Anticipated applicants 1–200 (§6, §15.3) | **None** |
| 1–5 applications per applicant (§6, G4) | AD4 |
| Typed, versioned form (§5.2, G1) | AD4; Form scaffold |
| Visibility partitions (§5.1) | AD4, AD5; replaced by R26 parts (AD-64) |
| Operator return to draft (§6) | **None** (inert button) |
| Withdrawal until timeline completes (§6) | AD4; cut-off **none** |
| Documents, Blob, PDPA retention (§5.3, G8) | Later (R2, R3) |
| Referees (§4.1, §7) | Later (R2) |
| Native instruments ≤3 (§4.1, §7.6) | Contradicted as intended (R1, R28) |
| Applicant nomination 0–10, ranked (§7.1) | Partly (R27 *Nominated*); caps and provenance **none** |
| Dispatch routes, `/me/sendMail` (§7.2, §7.4) | **None** |
| Declines and replacement (§7.3) | **None** |
| Confidentiality and waiver (§7.5) | Partly (R26); waiver **none** |
| Panels 5 × 200 (§7.7, §14) | **None** |
| ≤50 assessors per application (§7.1, §15.3) | **None** |
| Whole-panel assignment, CSV importer, no balancing (§7.7) | Contradicted by R27; override unrecorded (AD-63) |
| No ranking/decision engine (§1, §12) | Contradicted by R13, R30; override unrecorded (AD-63) |
| Consolidated invitations (§7.7) | Layer B, AD7; B has no row (AD-122) |
| Dashboard and metrics (§8) | AD8 |
| Export bundle, injection guard, audit, expiry (§8.1) | AD1J scaffold; logging AD2; expiry **none** |
| Outcome import with preview (§8.2) | AD7; Dossiers Upload CSV scaffold |
| Embargo, scheduled release, correction (§8.2, G7) | AD7 |
| Timeline milestones, announcements (§9) | AD7 (announcements dropped from Process, AD1E) |
| Announcement email on changed details (§4, §9.1, G2) | AD3/AD7; email row **none** explicit |
| Unattended send (§7.4, G5) | Open decision |
| Design envelope, load tests, over-envelope warning (§7.8, §14) | **None** |
| CSRF, no caching, rate limits, idempotent import/export (§11) | **None** explicit |
| Audit of every mutation (§1.1.7, §11) | AD2 |
| Applicant portal (§6) | AD4, AD7; `/me` scaffold |
| Form branching (§5.2) | Deferred (open decision) |

### (c) Walk-through dead ends

**Operator** (set up → publish → evaluate → decide → release → extract):

1. *Create*: *New exercise* disabled, no reason; set-up starts only from a sample (AD-13).
2. *Set up*: Process's *Shown to applicants* and *Update timeline* do nothing (AD-09); ticked emails never reach Emails (AD-18); Emails cannot be written, so an owed email can never clear (AD-21).
3. *Publish*: the checklist under-reports (AD-20); no Publish, *Open form* or *Close form* control (AD3; AD-36).
4. *After publish*: nothing locks (AD-01 to AD-05).
5. *Entry*: opened gates' entry editable (AD-04); no tick-all (AD-22); *Lock* drops the unsaved signal (AD-07).
6. *Evaluate*: Evaluations ignores the gate page's work (AD-33); *Send* and *Pull results* inert with no reason, and the gate page has no Send (AD-11, AD-23): a gate cannot move Ready → Sent or bring results back.
7. *Decide*: decisions stamped "13 Nov" against a 17 Nov timeline (AD-40).
8. *Release*: undecided outcomes with owed emails release (AD-21); the applicant then sees no result (AD-28).
9. *Extract*: files ignore on-screen edits (AD-06); unlogged alias key (AD-12); unguarded second `applications.csv` (AD-66).
10. *Close / archive*: no control anywhere (AD-37).

**Applicant** (lobby → exercise → apply → follow → result):

1. *Lobby*: only one of the applicant's applications is listed (AD-27).
2. *Exercise page*: *Start an application* disabled without reason (AD-13); no link to one's own application (AD-27).
3. *Application*: Save/Submit offered after close (AD-29); *Withdraw* in the wrong role, undefined (AD-30); the page shows the wrong questions (AD-26).
4. *Result*: the path stops at "released"; the applicant's own value is never shown (AD-28).
5. *Reviewer*: "Score it in Review Robin" has no link (AD-31); no breadcrumb back (AD-101).
