# Instrument card — control persistence audit

**Date:** 2026-08-16. **Scope:** the per-instrument card on the operator
Instruments page (`app/web/templates/operator/instruments_index.html`, the
live new-model card). **Question:** does every button / handle in the card
follow the "edit → persists when you click the card's **Save**" model, or do
some persist another way — and can any edit be silently lost?

**Method:** enumerated every `onclick=`, `form="dfsave-…"`, `fetch(` /
`sendBeacon`, and drag handler in the template; traced each
`window.<handler>` definition; cross-checked endpoints against
`app/web/routes_operator/_instruments.py`, `_instruments_band2.py`,
`_instruments_pagination.py`. Line numbers are from the template at audit
time.

---

## TL;DR

The card does **not** use a single "stage everything, persist on Save"
model. Three persistence paths coexist:

- **A — staged → Save.** The control's state rides the `dfsave-{id}` form
  (`form="dfsave-…"` inputs or hidden mirrors) and is written only when the
  card **Save** button submits (`POST …/fields/save`). This is the
  **Assignment rule (Band 1)** and the **Visibility (Band 3)** controls.
- **B — immediate async POST.** The control fires its own
  `fetch`/`sendBeacon` POST on click and persists **independent of Save**.
  This is **most of Band 2** (field pills, help text, column widths, sample
  short_label/description), the **Response-Field `R` / `✓` / `X` buttons**,
  the **instrument name/identity**, and every card-level server action
  (Replicate, Delete, +Instrument, page-break, Open/Close, reorder, …).
- **C — client-only.** Changes only what the browser shows; nothing is
  persisted (Cancel/reload, expand-all, the ↻ preview-sample refresh, and
  transient input handlers).

Because the card **Save** also *flushes* Band 2 state on submit
(`_newModelWireSaveFlushers`, line 3633 → `saveBand2State`), the practical
guarantee "**my edits are persisted after I click Save**" holds for every
live control **with one exception** — see *Lost-edit risk*.

> Note: this corrects an earlier informal description that the Response-Field
> **✓** merely "stages into the preview" and Save "persists it." In fact **✓**
> (`newModelRfSaveRow`) both registers the pill **and** immediately POSTs to
> `/band2-state`; Save is a belt-and-suspenders flush, not the sole commit.

---

## Persistence path by control

Path: **A** = staged → card Save (`POST …/fields/save`); **B** = immediate
async POST (endpoint noted); **C** = client-only / preview / UI-state.

### Instrument Name

| Control (handler) | ~Line | Path | Persist mechanism |
|---|---|---|---|
| Title ✎ (`cardTitleEdit`) | 768 | C | enters edit mode |
| Title ✓ (`cardTitleSave`) | 774 | **B** | `POST …/identity` (`short_label`) |

### Assignment rule (Band 1) — all path A

| Control (handler) | ~Line | Path | Persist mechanism |
|---|---|---|---|
| Link mode pill All/Filter/Not-set (`newModelToggleRuleMode`) | 898 | A | `*_mode` + `*_touched` hidden (form=dfsave) |
| Unit mode pill (`newModelToggleUnitMode`) | 1103 | A | `link3_mode`/`_touched` hidden |
| AND/OR combinator (`newModelToggleCombinator`) | 934 | A | combinator hidden |
| Operator IS/IS-NOT cycle (`newModelCycleOperator`) | 973 | A | operator hidden |
| + Add rule / X remove rule (`newModelAddRule` / `newModelRemoveRule`) | 929 / 1023 | A | clone/remove rule cell (form=dfsave) |
| + / X unit cell (`newModelAddUnitCell` / `newModelRemoveUnitCell`) | 1125 / 1164 | A | clone/remove cell |
| Field / operand-tag / operand-value / boundary selects | 965, 1004, 1019, 1155 | A | form=dfsave selects |

### Preview review instrument (Band 2)

| Control (handler) | ~Line | Path | Persist mechanism |
|---|---|---|---|
| Field pill toggle (`newModelToggleBand2Pill`) | 1783 | **B** | `saveBand2State` → `POST …/band2-state` (un-pin confirm guard) |
| Pill drag-reorder (`newModelBand2Drop`) | 1777 | **B** | display pill → `…/display-fields/order`; response pill → `…/band2-state` |
| Column-width drag handles (`newModelBand2ResizeStart`) | 2027, 2283 | **B** (+A mirror) | `POST …/column-widths`; **also** mirrors hidden `column_widths_snapshot` on the Save form (line 1568) |
| Help-text ✎ / ✓ / textarea (`newModelHelpCard…`) | 2488–2504 | **B** | ✓ → `saveBand2State` → `…/band2-state` |
| Intro short_label ✎/✓ (`newModelIntroShortLabel…`) | 2679 | **B** | `POST …/identity` |
| Intro description ✎/✓ (`newModelIntroEdit/Save`) | 1674, 2773 | **B** | `POST …/identity` |
| Sort buttons (`toggleSort`) | 491, 2092 | A | `_rebuildSortInputs` writes `sort_display_field_id`/`sort_dir` hidden (form=dfsave) |
| ↻ Refresh preview sample (`newModelBand2RefreshSample`) | 1554 | **C** | `POST …/preview-sample` — read-only render; **saves nothing** |

### Visibility (Band 3) — path A

| Control (handler) | ~Line | Path | Persist mechanism |
|---|---|---|---|
| Audience cell chip cycle (`newModelCycleVisibilityCell`) | 3715 | A | `*_mode` hidden (form=dfsave) |

### Response Fields

| Control (glyph / handler) | ~Line | Path | Persist mechanism |
|---|---|---|---|
| **R** required toggle (`newModelRfRequiredChanged`) | 3909 | **B** | `saveBand2State` → `…/band2-state` (rows with a saved pill) |
| ≡ help-visible toggle (`newModelRfHelpVisibleChanged`) | 3917 | B via flush | mutates pill/DOM; persists on next `saveBand2State` (✓ or Save flush) |
| **✓** save row (`newModelRfSaveRow`) | 3924 | **B** | registers/updates the pill **and** `saveBand2State` → `…/band2-state` |
| **X** delete row (`newModelRfDeleteRow`) | 3930 | **B** | removes row + `saveBand2State` (if it had a pill) |
| + Add row (`newModelRfAddRow`) | 4020 | **C until ✓** | clones an empty client row; **not serialized until ✓** — see risk |
| Row name/bound `oninput`, type `onchange` (`newModelRfFieldChanged` / `RfSyncBounds`) | 3854 | C | recompute button-enabled state / show-hide bound inputs |

### Card-level actions — path B (own POST form) unless noted

| Control | ~Line | Path | Endpoint |
|---|---|---|---|
| **Save** (dfsave submit) | 361, 814 | A commit point | `POST …/fields/save` (+ flushes `saveBand2State`) |
| Cancel (`newModelCancelEdits`) | 373 | C | reloads (intentional discard) |
| Lock / Unlock (`newModelLockClick`) | 434, 804 | — | URL nav `?editing`; confirm guard only |
| Replicate / Delete / +Instrument | 379 / 392 / 401 | B | `…/replicate` · `…/delete` · `…/add-new-model` |
| +Page break / delete page break | 414 / 677 | B | `…/page-break/create` · `…/page-break/delete` |
| Open / Close this instrument | 831 / 838 | B | `…/open` · `…/close` |
| Bulk Show / Don't-show when closed | 273 / 279 | B | `…/visibility/all-on` · `/all-off` |
| Instrument card drag-reorder (`data-instrument-drag-handle`) | 735 | B | `…/instruments/order` |
| Expand-all / Collapse-all | 266 | C | `details.open` + localStorage |
| Revert to draft | 301 | B | `…/revert` (only when ready) |

---

## Immediate-persist (path B) — the controls that do NOT wait for Save

Beyond the column widths and the instrument name (the two originally
suspected), **these also persist on click**: Band 2 field-pill toggle; Band 2
pill drag-reorder; help-text ✓; intro short_label/description; Response-Field
**R** / **✓** / **X**; the instrument-card drag-reorder; and every card-level
server-action form (Replicate, Delete, +Instrument, page-break add/delete,
Open/Close, bulk visibility, Revert). Endpoints: `/band2-state`, `/identity`,
`/column-widths`, `/display-fields/order`, `/instruments/order`, plus the
per-action routes.

`/preview-sample` (↻ Refresh) is path **C** — it re-renders the preview with a
sample reviewee and commits nothing.

---

## Lost-edit risk (one, actionable)

**A newly-added Response Field that is filled in but never `✓`'d is silently
dropped on Save.**

- `+ Add row` (`newModelRfAddRow`, line 4290) clones an **empty, pill-less**
  client row; its name/type/bounds live in `data-new-model-rf-*` attributes,
  not in any `dfsave` input.
- `saveBand2State` (line 2376) serialises response fields by iterating the
  **existing Band 2 pills** and looking each row up by `data-row-key`. A row
  with no pill yet (i.e. never `✓`'d) is **skipped**.
- The card **Save** flush also calls `saveBand2State`, so it skips the row
  too. Net effect: an operator types a new field and clicks **Save**
  (reasonably expecting Save to save it) → the field is **lost**. Same for
  toggling **R** / **≡** on an un-`✓`'d new row.

This is arguably the intended "✓ = register the row" staging, but it is an
easy-to-hit surprise because **every other** live control persists on either
click or Save. Recommended fix (small, fits **Segment 18R** Item 1's
instrument-card clarity work): on card **Save** (and/or on blur of a row with
a non-empty name), **auto-register** any named-but-un-`✓`'d row before
`saveBand2State` — or block Save with a "you have unsaved rows — register
them?" confirm. Clearer per-row affordance labelling would also help.

*(Non-risk clarified: the `≡` help-visible toggle on an **existing** (pilled)
row is not a lost edit — the row `✓` and the Save flush both persist it. It
only rides along with the risk above for brand-new un-`✓`'d rows.)*

---

## Dead code (not live controls — ignore for the card)

Defined in the template but **never invoked** here or imported elsewhere:

- Macros `response_fields_table` / `response_fields_help_table` / `sort_cell`
  (lines 511 / 609 / 477) and their handlers `moveRow` / `addRow` /
  `deleteRow` (5016 / 5070 / 5112) with `form=dfsave` inputs (533–638) — the
  legacy checkbox-based Response-Fields editor. (This is the table with the
  "Required" checkboxes + ➕/✗ action buttons; it is **not** what renders on
  the live card.)
- `newModelToggleAudience` (4451) and `newModelCycleButton` (4464) — defined,
  bound to no `onclick`.

These should be deleted in a housekeeping pass to avoid future confusion
(candidate 18R / housekeeping item).

---

## Bottom line

- The user's expectation — *edits persist when I click Save* — **holds for
  every live control except a newly-typed Response Field that was never
  `✓`'d.** Most controls actually persist earlier (on click, path B); Save is
  a commit-point + flush.
- The **column-width handles** are indeed a distinct path (immediate
  `/column-widths` POST, with a Save-form mirror) — the suspected exception,
  confirmed, plus several more immediate-persist controls listed above.
- One fix worth scheduling (18R): close the un-`✓`'d-new-row lost-edit gap;
  and delete the dead legacy Response-Fields editor.
