# Segment AD2S — A scale on a Review Robin gate

**Opened:** 2026-11-25 (moved from Review Robin's segment 20P, Item 2, at the author's word) · **Theme:** a gate's *Response fields* card offers Review Robin's scale, and the handoff carries it · **Related:** `guide/archive/segment_20P_scale_answer.md` (Item 1, Review Robin's side, closed 2026-11-24), `spec/instruments.md` ("Scale"), `spec/handoffs.md`, `applydesk/spec/applications.md`

## Opportunity

A gate of type *Review Robin Session* runs in Review Robin, and its *Response fields* card offers only Integer, Decimal, List and String (`FIELD_TYPES`, `applydesk/stages.py`). Review Robin now answers a bounded Integer or Decimal field as a scale (20P Item 1: snaps at 11 points or fewer, slides past them, with optional Start / Middle / End labels), and its Settings CSV and linked re-send carry `scale` and `scale_labels`. A gate cannot yet ask for one (`guide/rrw_reviewer_phone_and_scale.md` §3).

## Decision

Reinforce the existing card (Process > Gate > *Review Robin Session* > *Response fields*); no new gate type.

- **The Type menu is Band 3's:** Integer, Integer (scale), Decimal, Decimal (scale), List, String.
- **Storage:** `gate_field` keeps `type` as the number type and gains `scale` (boolean) and `scale_labels` (`start|middle|end`). A migration on Apply Desk's chain. Results derive, extract and hand off as now.
- **The row:** a scale field's Min / Max / Step line stays; the labels take a second line, as Band 3's does. A field that cannot be a scale yet (bounds missing, or Max not Min plus a whole number of Steps) is a problem on the Outline, and the gate cannot be sent with it.
- **The handoff** writes Item 1's two attributes beside the field's other rows: `scale` = `true` and `scale_labels`; `data_type` stays Integer or Decimal, and Review Robin decides snap or slide from the bounds.

Rejected: **a separate scale type** in Apply Desk's storage. Review Robin keeps the number type and a flag; matching it keeps the handoff a copy, not a translation.

## Semantics

- **Switching to and from a scale** keeps the bounds; switching to List or String clears `scale` and its labels, as Band 3 does.
- **Labels** are optional; an over-long part is cut at Review Robin's limit (60 characters) on save, as the Settings CSV import does.
- **A gate already sent** re-sends the scale through the linked re-send, which owns the two rows (`spec/handoffs.md` §6a).
- **Results** are numbers, as any Integer or Decimal field's: derivations, means and extracts are unchanged.

## Blast radius (measured)

Taken 2026-11-25 at `3092a29ea`.

| What | Count | Command |
|---|---|---|
| Modules using `gate_field` | 2 | `grep -rln "gate_field\|GateField" applydesk/*.py` |
| Templates with the Response fields card | 1 | `grep -rln "FIELD_TYPES\|Response fields" applydesk/templates` |
| Checks on a field's type | 27 | `grep -rn "type ==\|type in (\|ALLOWED\[" applydesk/*.py \| wc -l` |

## Status

**Rung 2 (2026-11-25):** `ad2s1_gate_scale.py` adds `gate_field.scale` and `scale_labels`; `stages.Field` carries both, `process_save` reads them (a List or String keeps neither, labels cut to 60), and `stages.field_problems` names a scale Review Robin's `scale_shape_error` would refuse, which `locks.publish_problems` blocks on. Divergences: `scale_labels` is `String(200)` not null, `""` for none, as the table's other text columns, not nullable; the Outline's line is the page script's and lands with the card in rung 3, since nothing sets a scale before it.

**Rung 3 (2026-11-25):** the *Type* menu is `stages.FIELD_CHOICES` (a scale's value `<type>:scale`), the labels take a second line, and the page script's `scaleProblem` names on the Outline what `stages.field_problems` names at publishing. The handoff writes `scale` and, when set, `scale_labels`; the extract's field detail carries them. A result collating a scale field reads it as a number (`result_type`, `result_summary`), as the page script always has. `tests/integration/test_handoffs.py` posts the bundle to Review Robin and finds a 5-point scale.

## PR ladder

1. **Plan** (this file, moved from 20P Item 2). Prose only.
2. **Model and save:** the migration, `process_save`'s checks, and the Outline problem.
3. **The card and the handoff:** the two Type entries and the labels line; `handoff.py`'s attributes. The last build rung, so it carries the cumulative read.
4. **Close:** `spec-writer` on `applydesk/spec/`, the item deleted from `applydesk/guide/todo_master.md`, the plan archived.

## Definition of done

- A gate field set to *Integer (scale)* from 1 to 5 hands off `scale` = `true` with its bounds, and its Review Robin session renders a 5-point snap scale.
- A gate field that cannot be a scale is an Outline problem and blocks sending the gate.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2S` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row

## Open questions

None.

## Out of scope

- The applicant Form's questions: they are answered in Apply Desk and have their own types.
- **A gate whose instrument Review Robin may extend** (reorder, add fields, branch): segment 23G, *Review Robin (advanced)*, ruling 36 (`guide/segment_23G_linked_advanced_instrument.md`).

## Doc impact

- `applydesk/spec/applications.md` — *Response fields* lists the two scale types and the labels line.
- `applydesk/spec/architecture.md` — `gate_field`'s two columns.
- `applydesk/guide/todo_master.md` — the gate-scale item deleted (at close).
