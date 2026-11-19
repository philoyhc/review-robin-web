# Segment AD1L — Apply Desk: Emails, a working scaffold

**Opened:** 2026-11-19 · **Theme:** the Emails page built out as Form and Process were: every template the exercise owes written, previewed and reset on screen, kept in the tab, nothing saved until AD2 or sent until AD7 · **Related:** `applydesk/guide/todo_master.md` (rulings 16, 23; the AD1L roadmap row), `applydesk/spec/applications.md` ("The Emails page"), `applydesk/guide/findings_2026-11-18_assessment.md` (AD-116)

## Opportunity

Emails is the last Setup page still static. It lists each template Process makes owed (ruling 16), but every control on it is disabled (`operator/_emails.html`):
- *Subject* and *Body* are read-only;
- *Save*, *Preview* and *Reset to default* are inert, with "comes with AD2/AD7" titles.

So an operator cannot try the one thing the page is for, writing the emails. An outcome whose email is owed cannot be released (AD-21), yet nothing on the page lets the operator write that email. AD-116 asked the spec to describe Subject and Body, *Preview*, *Reset to default* and the empty state; it now does, but only as disabled controls. Layer B and AD7 will send these templates, so their shape (fields, defaults) needs settling before then.

## Decision

1. **Each card is a template that stands alone**, with its own *Save* (ruling 23). There is no page Save.
   - *Subject* and *Body* are editable.
   - An *Unsaved changes* marker shows per card.
   - Leaving the page with any card unsaved asks first, as Form's does.
2. **Save keeps the template in the tab** (`sessionStorage`, by exercise), as the gate page keeps its pairs (AD1G).
   - A saved template with a subject and a body reads *Written*; an emptied one reads *Owed* again.
   - Nothing is saved until AD2.
3. **Merge fields are bracketed names from a fixed list per template kind**, e.g. `[Applicant name]`, `[Exercise]`, `[Outcome]`, `[Link]`.
   - The sample's bodies already write `[applicant name]`, and a bracketed name reads plainly in a sent email if it is ever left unfilled.
   - Each card has an *Insert field* menu that puts a field at the cursor in whichever box last had focus.
   - *Save* refuses a template naming a field its kind does not have, and says which.
4. **Defaults per kind**: receipt, reminder, an outcome to applicants, an outcome to evaluators. Each is a subject and body written with that kind's fields.
   - *Reset to default* puts the default in the card, asking first if the card has text.
   - An owed card offers the same button as *Start from the default*.
5. **Preview** opens under the card: the subject and body with each field filled from the sample.
   - Values come from the exercise's first submitted application (its applicant, the outcome's value in that row, the form's close date, and so on).
   - A field the kind does not have shows marked, as Save would refuse it.
   - Preview reads the card as it stands, saved or not.

**Alternative rejected:** `{{ applicant.name }}` template syntax. It reads as code to an operator, it invites expressions the sender (AD7) would then have to evaluate, and it collides with Jinja in the page itself. Bracketed names with a fixed list keep the sender a plain substitution.

## Semantics

- **Kinds and their fields** (`workflow.EMAIL_FIELDS`):

  | Kind | Fields |
  |---|---|
  | Receipt | Applicant name, Exercise, Application ID, Link, Help contact |
  | Reminder | Applicant name, Exercise, Closes, Link, Help contact |
  | Outcome · Applicants | Applicant name, Exercise, Stage, Outcome, Link, Help contact |
  | Outcome · Evaluators | Evaluator name, Exercise, Stage, Outcome, Link, Help contact |

  Fields match case-insensitively (`[applicant NAME]` is `[Applicant name]`). A `[` with no closing `]`, or brackets holding something that is not a field, is text, unless it names a field of another kind; that is refused.
- **Written:** non-empty subject and body after trimming. The chip and the release lock read the template as the tab holds it on this page only. Dossiers' *Released* lock reads the sample until AD2 (stated on the page, as now).
- **Kept in the tab:** a stored template is shown only if Process still makes that template owed (same name). A stale entry is dropped silently.
- **Empty exercise:** the *No emails yet* card is unchanged.
- **Blind exercise:** blindness hides applicants from evaluators, so Outcome · Evaluators has no applicant fields and an evaluator's email cannot name one. An applicant's own email names them, blind or not.

## Judgment calls — decided

- Save refuses an unknown field rather than warning: a broken token in an email to 100 applicants is worse than a blocked save (2026-11-19).
- Preview uses the first submitted application rather than a picker: one realistic sample suffices on a scaffold, and a picker can come with AD7 (2026-11-19).
- The written state stays on Emails until AD2; Dossiers' release lock keeps reading the sample, so two pages don't disagree through storage (2026-11-19).

## Blast radius (measured)

Taken 2026-11-19 at `cdded743c`.

- Templates: `operator/_emails.html` (20 lines), the only page; `base.html` for any new class.
- Python: `workflow.py` (`Email`, `emails`, `_WRITTEN`, new `EMAIL_FIELDS`, `DEFAULT_TEMPLATES`, `sample_values`); `routes_operator.py:341` passes `emails`; `locks.py:187` and `extract.py:568` read `emails` and are unchanged.
- Tests: `grep -rn "/emails" applydesk/tests/*.py | wc -l` → 7, all in `test_pages.py`; no browser test of Emails yet.
- Specs: `applydesk/spec/applications.md` "The Emails page" (one section).

## Status

**Closed 2026-11-19.** Built in three PRs after the plan (#4010): rung 2 (#4011), rung 3 (#4012), and this close. Every Definition-of-done line holds.

**What the ladder became:** as planned. *Insert field* became a menu and an *Insert* button: arrowing a closed menu fires its change, which inserted a field on every key (the item read).

**Decisions confirmed at build:**
- A written sample template shows its kind's default; an owed one starts empty and offers *Start from the default*.
- Until AD2 the status row's *Emails*, Home and Dossiers' *Released* read the sample's templates, said on the page (the item read).
- Preview shows a field with no sample value by its name, dimmed (a draft has no application), and everything as text.
- The evaluator in Preview is the first member of the first panel at that stage's gates; *Link* is built in the route, under the mount.

**Reads:** one `diff-reviewer` item read (rungs 2–3, from `1109dc203`) found 12 findings, the real ones fixed in #4011 and #4012. Codex found none.

**Spec:** `spec-writer` checked "The Emails page" at the close and fixed Process's line that template text came later.

**Owed:** saving (AD2), sending and a sent email's absolute link (AD7).

## PR ladder

1. **This plan.** Prose only.
2. **Write and save.** Editable *Subject* and *Body*; per-card *Save* kept in the tab; *Written*/*Owed* following; the unsaved marker and the leave warning; *Reset to default* / *Start from the default* with the defaults; server tests and a browser test. Must not touch Dossiers' release lock.
3. **Fields and Preview.** The *Insert field* menu; Save refusing unknown fields; *Preview* filled from the sample; tests. The item's last build rung, so the cumulative cold read runs here.
4. **Close.** `spec-writer` on "The Emails page"; Status compacted; the roadmap row deleted; the plan archived.

## Definition of done

- Every card's *Subject* and *Body* edit; *Save* keeps them in the tab; *Written*/*Owed* follow (a browser test).
- *Reset to default* and *Start from the default* fill the kind's default, asking first over text (a browser test).
- *Insert field* inserts at the cursor; *Save* names an unknown field and refuses (a browser test).
- *Preview* fills each field from the sample and marks an unknown one (a browser test).
- Leaving with a card unsaved asks first (a browser test).
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand, as AD1K's was.)

## Open questions

- **Conditional text by outcome value**: answered (ruling 53), one body per template, `[Outcome]` naming the value; paragraphs shown with a small gap.
- **A face in a blind exercise's emails** (the photo field): not reached here; the photo field's own open question.

## Out of scope

- Sending, scheduling and the sender's identity: AD7 (and the unattended-send question in `todo_master.md`, "Open decisions").
- Gate invitation and reminder templates: Review Robin's side, Layer B / AD7.
- Saving to a database: AD2.
- Rich text or HTML bodies: plain text only, as Review Robin's emails are.

## Doc impact

- `applydesk/spec/applications.md` — "The Emails page": editing, per-card Save in the tab, the fields per kind, defaults and Reset, Preview, the unknown-field refusal (rungs 2–3).
- `applydesk/guide/todo_master.md` — delete the AD1L roadmap row (at close).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
