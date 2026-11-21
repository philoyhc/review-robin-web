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

- **The dossier is its own record** (ruling 32). It carries its own ID, and pairs, cells, results, parts and the alias key hang off it, not the application. It is proposed to be minted at submit, so a draft has none.
- **What writes a dossier** (ruling 26): an application submitted through the form, or *Create dossiers*, an upload of candidates from upstream where no form comes first. *Add dossiers* takes late or paper entries by the same upload. A candidate with two applications has two dossiers.
- **Form answers**, as submitted. There are no uploads in the MVP (ruling 3).
- **Evaluators' responses**, pulled from Review Robin.
  - Review Robin keeps nothing visible after its window (ruling 26).
  - A gate's responses become final when the operator pulls them after the session closes (ruling 57).
  - A gate is keyed by a stable per-exercise key, not its number (ruling 37).
- **Derived values**:
  - **A gate's results:** up to three per gate, each derived from one response field. The derivation sets the result's type (ruling 21).
  - **An outcome's value and combined result:** *Decided* is derived, not stored. Release is recorded per audience, each with its own time (ruling 38).
- **Operator entries:** values set by hand on Dossiers, the panels and their people (ruling 4), and the setup on Process and Form. An operator entry is either a dossier item, with grants like the rest, or store-only. Both kinds exist (ruling 70), so each field an operator can enter is marked one way or the other at setup.

## 3. The dossier

The page a candidate's readers open. It is displayable, and every item on it carries its own grants.

- **Whose it is** (ruling 70): a dossier belongs to a **candidate**, the person or people it is about. An **applicant** is a candidate who submitted through a Form. A candidate from *Create dossiers* is not an applicant.
- **What it holds** (ruling 68): every section of the submitted form (when there is one), every gate's results and every outcome, plus any operator entry marked as a dossier item (ruling 70).
- **A photo is an item like any other** (ruling 70): subject to its grants.
- **Who sees an item** (ruling 68): only the grants set on it.
  - *Applicant*;
  - *Assigned evaluators*, from named panels or from all panels;
  - *Evaluators*, from named panels or from all panels.
- **When:** each grant opens from a stage. An item that opens to two audiences at different times carries two grants (rulings 26, 68).
- **Operators see every item**, whatever its grants (rulings 9, 68).
- **Where grants are set** (ruling 68): on the item itself. A form section's are set on Form; a gate's results and an outcome's on Process.
- **Which dossiers an evaluator may open at all:** only those they are paired with (ruling 9). An item's grants then say what they see on it.
- **A gate's panel reads a frozen version** (ruling 25). Sending a gate freezes the dossier as its panel sees it, and later items add to it without changing what an earlier panel read.
- **Blind and confidential identity:**
  - A blind exercise's dossier redacts the applicant's name and identifiers (ruling 6).
  - A confidential gate shows Dossier IDs on its page and in its files (ruling 42).
  - Review Robin always receives the Dossier ID in place of the application ID (ruling 43).
- **Release is per audience** (ruling 38). An outcome's grant to *Applicant* opening is its release to applicants.
- **Not the dossier:** the applicant's timeline shows only the stages ticked *Shown to applicants* (ruling 46). That is the stage's visibility, not an item's.

## 4. Extraction

Files for offline work, for operators only.

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

**Superseded and not to be built:**
- Ruling 5's "the dossier shows only the *Shown to reviewers* section" became ruling 26's parts, then ruling 68's grants per item.
- Ruling 10's per-handoff alias key became ruling 43's Dossier ID.
- Form's per-card *Shown* control goes when grants are built (AD-69 and AD-93, in `applydesk/guide/ad3_plus_deferred_findings.md`).

## 6. Open questions

- **Ruling 68's first grant: *Applicant* or *Candidate*?** By ruling 70's terms, a grant to the person a dossier is about is a grant to the *candidate*. That would let a *Create dossiers* candidate see their dossier, but only if such a candidate can sign in at all.
- **A photo in a blind exercise.** Ruling 6 has blind review redact name and identifiers automatically. If a photo follows only its grants (ruling 70), a blind exercise shows a face to evaluators whom an operator grants it. Is that intended, or does blind review still hide the photo whatever its grants? Related: the photo field's open question (`applydesk/docs/photo_field_design.md`).
- **How the operator picks extraction's mode and content**: one card per mode, or a mode chosen per file.
