# Apply Desk — the data and visibility model (draft)

**Status:** a draft, collected on 2026-11-21 from the author's rulings. It becomes a spec in `applydesk/spec/` once the store is built: AD2 for the tables, AD4 for the form, AD5 for dossiers. Until then the rulings in `applydesk/guide/todo_master.md` are the authority. This file gathers them in one place and says how they fit together; where the two differ, the ruling wins. Ruling numbers below are that file's.

## 1. Three places the data lives

Apply Desk's data comes from three sources:
- **Applicants** submit it through the form.
- **Evaluators** answer in Review Robin, and Apply Desk pulls the answers back.
- **Operators** type it in.

Some of it is derived from those: a gate's results, and an outcome's value and combined result. It lives in three places, each with one job (ruling 69).

| | Place | What it is for | Who reads it |
|---|---|---|---|
| 1 | **The store**: the database tables | The one source of truth. Everything collected or derived is kept here. | Apply Desk itself; people only through 2 and 3 |
| 2 | **The dossier**: a page per candidate | What people need to read on screen, item by item, each item with its own visibility grants | Operators, applicants and evaluators, as each item's grants allow |
| 3 | **Extraction**: CSV files | Data taken offline. By default the dossier's content; it may carry more from the store | Operators only |

The rule between them:
- Everything goes into the store.
- Only what must be read on screen goes into the dossier, each item marked at setup with who sees it and from when.
- Extraction follows the dossier by default and may add more from the store, for operators.

## 2. The store

Every value is kept, whatever is shown of it.

- **The dossier is its own record, with or without an application** (rulings 32, 81). It carries its own ID, and pairs, cells, results, parts and the alias key hang off it, not the application. From the form it is minted at submit or at the form's close, the operator's choice, so a draft has none; from a Candidates item feeding gates, at publish and on each later add.
- **What writes a dossier** (rulings 26, 77, 81): an application submitted through the form, or *Populate Dossiers* (Candidates renamed, ruling 83), an entry per dossier, when it is the exercise's first item; it absorbs ruling 26's *Create dossiers* and *Add dossiers*. A later Form adds to dossiers already populated, never mints one. A candidate with two applications has two dossiers.
- **Form answers**, as submitted. There are no uploads in the MVP (ruling 3).
- **Evaluators' responses**, pulled from Review Robin.
  - Review Robin keeps nothing visible after its window (ruling 26).
  - A gate's responses become final when the operator pulls them after the session closes (ruling 57).
  - A gate is keyed by a stable per-exercise key, not its number (ruling 37).
- **Derived values**:
  - **A gate's results:** up to three per gate, each derived from one response field. The derivation sets the result's type (ruling 21).
  - **An outcome's value and combined result:** *Decided* is derived, not stored. Release is recorded per audience, each with its own time (ruling 38).
- **Operator entries:** values set by hand on Dossiers, the panels and their people (ruling 4), and the setup on Process and Form. An operator entry is either a dossier item, with grants like the rest, or store-only. Both kinds exist (ruling 70).

## 3. The dossier

The page a candidate's readers open. It is displayable; what each reader sees of it is set where they read (ruling 79).

- **Whose it is** (ruling 70): a dossier belongs to a **candidate**, the person or people it is about. An **applicant** is a candidate who submitted through a Form. A candidate from the Candidates item is not an applicant.
- **What it holds** (ruling 68): every section of the submitted form (when there is one), every gate's results and every outcome, plus any operator entry marked as a dossier item (ruling 70).
- **A photo is an item like any other** (rulings 70, 71): shown as the views say, even in a blind exercise. Blind review's redaction (ruling 6) covers the name and identifiers, not a photo, because a blind exercise may ask for a photo or screenshot that does not identify anyone. An operator who wants a face hidden from evaluators leaves it out of their views, or sets its ceiling to *never to evaluators*.
- **Who sees an item, and when, is set where people read** (ruling 79, superseding the per-item grants of rulings 26, 33, 68 and 71):
  - **Each gate × panel** sets what that panel's evaluators see during the gate, assigned evaluators and the whole panel apart. Its window is the gate's review window: once the gate closes, its evaluators see nothing of it unless an outcome opens it to them.
  - **Each outcome** sets what becomes visible to candidates and to evaluators of past gates, from its release to that audience (ruling 38) until the next outcome updates it, or the end of the exercise. The next outcome **continues**, **adds** to it or **resets** it.
  - **A candidate always sees their own submitted form.**
  - **A new item starts hidden from every view**; the page flags an item in the dossier no view shows.
  - **Each field's ceiling** (*never to candidates*, *never to evaluators*) is set on the field, and no view passes it.
- **Operators see every item** (rulings 9, 68).
- **Which dossiers an evaluator may open at all:** only those they are paired with (ruling 9). Their gate × panel view then says what they see on it.
- **A gate's panel reads a frozen version** (ruling 25). Sending a gate freezes the dossier as its panel sees it, and later items add to it without changing what an earlier panel read.
- **Blind and confidential identity:**
  - A blind exercise's dossier redacts the applicant's name and identifiers (ruling 6).
  - A confidential gate shows Dossier IDs on its page and in its files (ruling 42).
  - Review Robin always receives the Dossier ID in place of the application ID (ruling 43).
- **Release is per audience** (ruling 38). An outcome's view for candidates opens at its release to them.
- **Not the dossier:** the applicant's timeline shows only the stages ticked *Shown to applicants* (ruling 46). That is the stage's visibility, not an item's.

## 4. Extraction

Files for offline work, for operators only.

- **In the dossier or not is set on the field** (ruling 71). Every field is set one way or the other where it is defined: a form section, a gate's result, an outcome, an operator entry. A field in the dossier is then meant to be seen: at least one view shows it (ruling 79). Dossier-mode extraction follows that setting; process-mode extraction carries what the store holds.
- **Two primary modes** (ruling 70), and both exist:
  - **Following dossiers:** organized around the data collected, one candidate's items as columns.
  - **Following the process:** organized around the exercise's stages, gates and outcomes.

  Either may carry more than any dossier shows, from the store. The exercise's settings are the clearest case: they are no candidate's item.
- **Identity follows the exercise's confidentiality.**
  - Files can carry Dossier IDs in place of names.
  - The *Alias key* maps Dossier IDs back to applicants. Review Robin never sees it (ruling 43).
- **File names use the gate's stable key** (ruling 37).
- **Downloads are to be logged** once the store exists.
- **Today** Extract data is built on sample data, card by card (`applydesk/spec/applications.md`, *Extract data*):
  - *By gate* and *Extract setup* are already process-shaped.
  - *Applications* and *Outcomes* sit nearer the dossier mode, but are not yet organized per dossier item.
  - *Alias key* serves both.

## 5. The rulings collected

| Ruling | What it adds to this model |
|---|---|
| 3 | No uploads in MVP applications: form answers only |
| 4 | Apply Desk keeps the rosters (panels), not Review Robin |
| 6 | A blind exercise's dossier redacts name and identifiers |
| 9 | An evaluator opens only the dossiers they are paired with; operators open all |
| 21 | A gate yields up to three results, each derived from a response field |
| 25 | The dossier is the record a panel opens; sending a gate freezes what its panel sees |
| 26 | A dossier per candidate entry, written in parts by the form, gates and outcomes, each with an audience and a from-stage; *Create dossiers* where no form comes first |
| 32 | The dossier is its own table at AD2 |
| 33 | One vocabulary for what a reader sees, per dossier part (refined by 68) |
| 37 | A gate's stable key names its URL and its files |
| 38 | *Decided* is derived; release is per audience |
| 42 | A confidential gate hides names on its page and files |
| 43 | The confidential identity is the Dossier ID; the *Alias key* maps it back |
| 46 | *Shown to applicants* is per stage, for the timeline |
| 57 | A gate's results are final when its final results are pulled |
| 68 | Grants per dossier item (form section, gate result, outcome), each from a stage; operators see all; set on Form and Process |
| 69 | The three places: the store, the dossier, extraction |
| 70 | Extraction's two modes; operator entries of both kinds; *candidate* and *applicant*; a photo subject to grants |
| 71 | The first grant is *Candidate*; a photo follows its grants in a blind exercise too; in-dossier or not is set on each field, and an in-dossier field needs grants (grants superseded by 79) |
| 79 | Visibility set where people read: each gate × panel for its window, each outcome for candidates and past evaluators (continue, add or reset); a candidate sees their own form; new items start hidden; each field keeps its ceiling |
| 81 | The dossier is its own record, with or without an application; minted at submit or form close, or at publish from Candidates, which absorbs *Create dossiers* |
| 82 | A change recomputes only the pairs of dossiers it touches that are neither approved nor hand-edited; none once the session opens |
| 83 | The first item populates dossiers: a Form (a dossier per submission) or *Populate Dossiers* (Candidates renamed; an entry per dossier, a person may hold several); a later Form adds to existing dossiers through an entry rule; dossiers per person set on the populating item |

**Superseded and not to be built:**
- Ruling 5's "the dossier shows only the *Shown to reviewers* section" became ruling 26's parts, then ruling 68's grants per item, then ruling 79's views where people read.
- Ruling 10's per-handoff alias key became ruling 43's Dossier ID.
- Form's per-card *Shown* control goes when grants are built (AD-69 and AD-93, in `applydesk/guide/ad3_plus_deferred_findings.md`).

## 6. Open questions

- **The extraction page's shape:** one card per mode, or a mode chosen per file. This is a layout question for the build that stores dossiers, not a ruling.
