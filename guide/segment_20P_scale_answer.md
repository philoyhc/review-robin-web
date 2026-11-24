# Segment 20P — A scale answer for numeric response fields

**Opened:** 2026-11-23 · **Theme:** a bounded Integer or Decimal response field can answer as a scale, on Review Robin's reviewer surface and on Apply Desk's gates · **Related:** `guide/rrw_reviewer_phone_and_scale.md` §2–§3 (the investigation, settled with the author), its mockups `guide/rrw_scale_mockup.html` and `guide/rrw_scale_builder_mockup.html`, `spec/reviewer-surface.md`, `spec/instruments.md`

Two items, each closing on its own:
- **Item 1** builds the scale in Review Robin.
- **Item 2** offers it on Apply Desk's gates, which hand their response fields to Review Robin.

The order is the author's (2026-11-23): next after AD2G Item 1, with the gate hooks built alongside. Item 2's handoff needs Item 1's Settings CSV attributes, so Item 1 lands first.

## Item 1 — The scale in Review Robin

### Opportunity

A numeric response field with a Min and a Max is answered in a bare `<input type="number">` (`app/web/templates/reviewer/_response_control.html`). A rating from 1 to 5, the commonest case, reads as a form field rather than as a scale. On a phone it is a tiny box that opens a numeric keypad. Nothing like a slider exists in Review Robin (`guide/rrw_reviewer_phone_and_scale.md` §2, "What exists today").

### Decision

Settled with the author on 2026-11-23 (`guide/rrw_reviewer_phone_and_scale.md` §2):

- **The mode.**
  - A scale is opt-in per field, and a mode rather than a type: `data_type` stays Integer or Decimal, so validation, branching, both CSVs, collation and Apply Desk's derivations are untouched.
  - It is stored as new keys in the field's `validation` JSON (`scale`, `scale_labels`), so no migration is needed.
- **The control.**
  - Up to 11 points it snaps, with a numbered stop at each allowed value. Past 11 it slides: Min, the midpoint and Max are numbered, and a number box sits beside it.
  - Up to three labels (start, middle, end); numbers are always shown.
  - A scale requires a Step, and a Min and a Max that differ by a whole number of Steps.
- **Choosing it in Band 3.**
  - The Type menu gains *Integer (scale)* after *Integer*, and *Decimal (scale)* after *Decimal*.
  - A scale row takes a second line holding the label boxes and what the reviewer will get (*5 points · snaps*).
  - A row that cannot be a scale yet keeps Band 3's pending state, giving the reason.
  - *Integer (scale)* with no Step fills a Step of 1.
- **Progressive enhancement.** The server still renders the number box, and a script turns it into the scale. Without script the box remains, and it submits the same name and value.

**Rejected:**
- **A new `data_type`.** Every reader of `data_type` would need a branch, and nothing downstream differs.
- **A native `<input type="range">`.** It always holds a value, so "not answered" cannot be shown.

### Semantics

- **Unanswered:** no circle, and the text "Not answered". The first arrow key on an empty scale picks Min. Delete clears the answer.
- **A closed session:** the scale shows dimmed and read-only, as the box does.
- **Changing a field's bounds** so that it can no longer be a scale: Band 3 marks the row pending and saves it as a plain number. An existing answer stays valid if it is still in range, as today.
- **The Settings CSV:**
  - Two new `response_fields[m]` attributes: `scale` (`snap` / `slide` / blank) and `scale_labels` (`start|middle|end`).
  - The `scale` cell is derived on export. On import, `scale` with no Step, or with bounds that don't divide, is refused by name.
- **Group mode and both response layouts** render the scale. *Responses across* needs about 26 px a point.

### Judgment calls — decided

- `snap` or `slide` is stored, not derived, so a changed Step cannot silently flip a scale that the operator chose.
- The labels use one `|`-separated cell rather than three attributes, to keep the CSV narrow. An empty part is no label.

### Blast radius (measured)

Taken 2026-11-23 at `de266a3bf`.

| What | Count | Command |
|---|---|---|
| Templates including the response control | 1 (92 lines) | `grep -rln "_response_control.html" app/web/templates \| wc -l` |
| `data-rs-step` uses | 5 | `grep -rn "data-rs-step" app/web/templates \| wc -l` |
| Python files reading a field's `step` | 10 | `grep -rln '"step"' app/` |
| Band 3 `data_type` mentions | 15 in a 7,637-line template | `grep -n data_type app/web/templates/operator/instruments_index.html \| wc -l` |
| Tests touching step or field attributes | 17 and 41 | `grep -rln 'data-rs-step\|"step"' tests/`; `grep -rln 'response_fields\[' tests/` |

### Status

Closed 2026-11-24. **Built:** #4190 plan, #4191 scaffold, #4192 the scaffold as a resizable table, #4193 3a storage and the reviewer surface, #4194 3b Band 3 and Band 2, #4195 4 the Settings CSV and the cold read, #4196–#4198 the author's browser checks (5, 6, 7 the rollback of 6's label span), and the close (scaffold removed, its tests moved to the reviewer surface).

**Diverged from the plan:**
- Storage is two columns, `scale` and `scale_labels` (migration `e5f9b3a7c2d4`), mirrored into `validation` while the shape holds. Band 3's Save rebuilds `validation` from the columns, so keys kept only there would have been lost.
- The CSV `scale` is a boolean; snap or slide follows from the point count (11 or fewer snap). Nothing stores `snap`/`slide`, so the first judgment call fell away. Item 2's handoff therefore sends `scale=true`, not `snap`.
- A scale whose bounds can't be one refuses the card's Save with its reason (422), rather than saving as a plain number (author's ruling, 2026-11-24).
- Rung 3 split into 3a and 3b, and the scaffold stayed until the close for the author's checks.

**Added at build (author, 2026-11-24):**
- A field with saved responses may switch to or from its scale; every other type stays locked.
- In the stacked layout every scale in a table takes the widest one's width.
- A slide's number box sits to its right, and an answered slide's foot is empty.
- Band 3's label line sits under Min, Max and Step. A span from the Type menu to Step was built (#4197) and rolled back (#4198) because it squeezed the Type menu; a browser guard now holds its width.
- Start and End labels reach the scale's edges, Middle is centered on the bar, and "Not answered" lines up with Start.

**Found and fixed in review:**
- Codex, 12 findings over #4193–#4197: a governed scale's live state, scientific-notation steps, a Save without `scale` kept the stored one, reviewer and stacked columns widen to the scale, Band 2's stacked and padded floors, the linked re-send's row allowlist, and String staying off on an answered field.
- One cumulative `diff-reviewer` read (base `8b33d9ede`, at rung 4) found 10. It led to the live branch state, the re-send carrying the scale, the `|` in labels, `.btn-reset`, accessible names and stronger tests. One fix pushed with a failing test (rung 5's pinned row-script rule); the next push corrected it.

### PR ladder

1. **Plan** (this file), with the todo pointers. Prose only.
2. **Scaffold:** the control on a hard-wired field (a test page only the author's local run serves), for the browser check of snap, slide, keyboard and clear. Inert outside that page.
3. **The setting:**
   - the `validation` keys and their checks (`app/services/instruments/_response_fields.py`);
   - Band 3's two Type entries and the second line;
   - the reviewer surface renders the scale for a field set to one;
   - the scaffold page removed.
4. **The CSV and the tests:**
   - the Settings CSV attributes and their round trip;
   - a browser test of click, drag, keys and clear, for a snap and a slide;
   - a field missing a bound stays a box.

   This is the **last build rung**, so it carries `diff-reviewer` on the cumulative diff.
5. **Close:** `spec-writer`, Item 1's stub deleted from `guide/todo_master.md`.

### Definition of done

- A field set to *Integer (scale)* from 1 to 5 renders five stops on the reviewer surface. A click, an arrow key and *clear* each save as the box would.
- The Settings CSV round-trips `scale` and `scale_labels`. An import refusing a scale with no Step names the field.
- With script off, the field is the number box.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 20P.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- ~~The builder mockup's layout~~: confirmed at the browser checks: labels under Min, Max and Step (Status).

### Out of scope

- The phone layout: its own plan, `guide/rrw_mobile_responsive.md`.
- Showing a scale on the summary, results and collation pages: they show the number.

### Doc impact

- `spec/reviewer-surface.md` — the scale control, its keys and its unanswered state (Item 1).
- `spec/instruments.md` — Band 3's scale types and second line (Item 1).
- `spec/csv_contracts.md` — the `scale` and `scale_labels` attributes (Item 1).
- `spec/settings_inventory.md` — the two new per-field settings (Item 1).
- `guide/todo_master.md` — the scale stub deleted (Item 1).

## Item 2 — A scale on an Apply Desk gate

### Opportunity

An Apply Desk gate runs in Review Robin, and its *Response fields* card offers only Integer, Decimal, List and String (`FIELD_TYPES`, `applydesk/stages.py`). Once Review Robin has the scale, a gate should be able to ask for one (`guide/rrw_reviewer_phone_and_scale.md` §3).

### Decision

- **The menu is Band 3's:** Integer, Integer (scale), Decimal, Decimal (scale), List, String.
- **Storage:**
  - `gate_field` keeps `type` as the number type and gains `scale` and `scale_labels`. That is a migration on Apply Desk's chain.
  - Results derive, extract and hand off as now.
- **The row:**
  - A scale row takes Band 3's second line.
  - A field that cannot be a scale yet is a problem on the Outline, and the gate cannot be sent with it.
- **The handoff** writes Item 1's two attributes beside the field's other rows. `data_type` is unchanged.

### Blast radius (measured)

Taken 2026-11-23 at `de266a3bf`.

| What | Count | Command |
|---|---|---|
| Modules using `gate_field` | 2 | `grep -rln "gate_field\|GateField" applydesk/*.py` |
| Templates with the Response fields card | 1 | `grep -rln "FIELD_TYPES\|Response fields" applydesk/templates` |
| Checks on a field's type | 27 | `grep -rn "type ==\|type in (\|ALLOWED\[" applydesk/*.py \| wc -l` |

### PR ladder

1. **Model and save:** the migration, `process_save`'s checks, and the Outline problem.
2. **The card and the handoff:** the two Type entries and the second line; `handoff.py`'s attributes. This is the last build rung, so it carries the cumulative read.
3. **Close:** `spec-writer` on `applydesk/spec/`, and the item deleted from `applydesk/guide/todo_master.md`.

### Definition of done

- A gate field set to *Integer (scale)* from 1 to 5 hands off `scale=snap`, and its Review Robin session renders the scale.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 20P.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Out of scope

- The applicant Form's questions: they are answered in Apply Desk and have their own types.

### Doc impact

- `applydesk/spec/applications.md` — *Response fields* lists the two scale types and the second line (Item 2).
- `applydesk/spec/architecture.md` — `gate_field`'s two columns (Item 2).
- `applydesk/guide/todo_master.md` — the gate-scale item deleted (Item 2).
