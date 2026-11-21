# Apply Desk — findings deferred past AD2

The rows of the 2026-11-18 assessment (`applydesk/guide/archive/findings_2026-11-18_assessment.md`) that wait on a stage after AD2, moved here on 2026-11-21 and kept verbatim under the source's theme headings: Layer B (AD-31), AD3's exercise lifecycle (AD-37), AD4's dossier parts (AD-64, and AD-69's and AD-93's Shown controls, which ruling 67 leaves for the parts work) and AD7's emails and release (AD-09). The rows waiting on AD2 itself are in `applydesk/guide/ad2_deferred_findings.md`.

Whichever plan opens that stage takes its rows: it absorbs, rules or drops each, and strikes it here with the PR. Conventions are the source's: `.py` paths are relative to `applydesk/`, `.html` paths to `applydesk/templates/applydesk/`, and `spec/` / `guide/` / `docs/` to `applydesk/`; **R*n*** is ruling *n* in `guide/todo_master.md`.

### 2. Honest controls and copy

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-09 *Stage tick modelled (R46); the outcome's per-audience ticks Deferred (AD7, R38)* | M | The stage's *Shown to applicants* (always checked) and the outcome's per-audience *Update timeline* ticks set Unsaved but change nothing. The spec contradicts itself (timeline: "not modelled: every stage shows"), and nothing in todo_master tracks it. | Process; `operator/_process_cards.html:301-307,337`; `spec/applications.md` l.223-224 vs l.260-261 | Code: disable them with "Not modelled yet", or remove them. Spec: align. Track in todo_master. | ACT-31, SP-08 |

### 4. Applicant surface

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-31 *Deferred (Layer B)* | L | The reviewer's dossier says "Score it in Review Robin." with no link. | `me/dossier.html` | Code: link Review Robin's `/me` (LRG B). | ACT-43 |

### 5. State and canned data

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-37 *Ruled (R41); `/me` built, transitions Deferred (AD3)* | M | Exercise Draft/Published/Closed/Archived are strings with no transitions. Closed and Archived have no sample, no guard and no control (R14 ends there; AD3). "Closed" means different things for the exercise and the form. `/me` hides non-Published exercises, so after Close applicants lose their released outcomes (FS §6 keeps them visible). The spec does not say Close/Archive are absent. | `sample_data.py:20`; `workflow.py:283-293`; `routes_me.py:20,36-37` | AD3: an enum with a transition table, audited, and distinct labels. Spec: "not built: AD3". Ruling needed: For the author 10. | DM-23, SP-27 |

### 9. Visibility and confidentiality

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| ~~AD-64~~ *Done in #4100: ruling 68 names the one vocabulary, grants per item; AD4's roadmap row reads it and the open decision is closed* | M | There are three visibility vocabularies: a per-card `shown` flag (meaningless on text cards), FS §5.1's section Shown/Not shown, and R26's parts with audiences and a visible-from stage. The roadmap's AD4 and the open decision "Card visibility beyond Shown / Not shown" still ignore R26, and the spec gives no notice of the change. | `sample_data.py:577`; `spec/applications.md` l.129-130; `guide/todo_master.md` l.545, 574-576 | Ruling needed (For the author 3), before AD4: model `form_section → dossier_part`; reword AD4 and narrow the open decision. | DM-13, SP-15 |

### 10. Component consistency

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-69 *Deferred (dossier parts, R33; ruling 67); grants per item, ruling 68: chips and the Toggle done (R47), Required a checkbox (U5, #4040); Form's per-card "Shown" two-button `.seg` goes with ruling 33's parts* | M | Five on/off primitives (`.seg` 34px, `.btn-toggle` 36px, `.pn-show`, `.tl-switch`/`.theme-toggle`, checkboxes). Like flags get unlike controls: Form's "Shown" is a `.seg` but Process's "Shown to applicants" is a checkbox; "Required" is a toggle but "Blind review" is a checkbox. | `operator/_form_cards.html`; `operator/_process_cards.html`; `operator/_details.html`; `operator/_extract.html:12-14` | Code: `.seg` for one-of-N, the §6 Toggle for per-row flags, pills for multi-select chips; ask before any new variant. | UI-04 |

### 11. Terminology

| ID | Sev | Finding | Where | Fix | Was |
|---|---|---|---|---|---|
| AD-93 *Deferred (dossier parts, R33; ruling 67); grants per item, ruling 68: cards read "Shown to evaluators" and the Outline "Shown"; both go with ruling 33's parts* | L | Visibility chips are asymmetric: "SHOWN TO REVIEWERS" / "NOT SHOWN" on cards but "SHOWN" / "NOT SHOWN" in the Outline. | Form | Code: "Shown" / "Not shown" in both; name the audience once in the intro. | UI-39 |
