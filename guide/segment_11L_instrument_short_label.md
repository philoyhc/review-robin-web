# Segment 11L — Instruments page: friendly short label

Single-PR segment. Adds `Instrument.short_label` (`String(32) | None`)
to the schema and a Setup-side editor on the Instruments page so
operators can author a short, reviewer-facing framing for each
instrument.

This segment is **independent of any reviewer-side work**. It ships
the operator-side foundation. The reviewer surface picks up the new
column when its own multi-instrument rewrite lands (see the
follow-on plan in `guide/segment_11D_v2_sweep_non_session.md` →
"Follow-on: Reviewer surface — multi-instrument rewrite", PR γ).
That dependency runs one direction: 11L can ship without the
reviewer rewrite; the reviewer rewrite needs 11L.

## Status

Planning. **One PR.** Plan can ship in parallel with any other
in-flight Segment 11 work — it touches the Instruments page +
schema only, no overlap.

## Scope

In:

- New nullable `Instrument.short_label String(32)` column.
- Service-layer `update_short_label(...)` helper with audit emit.
- Extension of the existing `_instrument_label(instrument)` helper
  in `app/services/instruments.py` to prefer `short_label` over
  `description.strip()` over `name`. (Audit-event summary copy
  picks up the prettier label automatically.)
- Operator UI: a short-label input on each per-instrument card on
  the Instruments index page, alongside the existing description
  textarea. Saves in the same round-trip as description.

Out:

- Any reviewer-side work. The reviewer surface continues to
  ignore `short_label` until the multi-instrument rewrite picks
  it up. (`Instrument.description` keeps its current role on the
  reviewer surface — it drives `views.reviewer_instrument_heading(...)`.)
- Bulk-set UI / CSV-of-labels import.
- Uniqueness checks across instruments in a session. Duplicates
  are acceptable; the reviewer surface's position prefix
  disambiguates on multi-instrument sessions.
- Tightening `Instrument.name` itself or retiring it. The system
  handle stays as is (`String(255)`, auto-generated `instrument_N`
  on create, never reviewer-facing).
- Tightening `Instrument.description`. The 2000-char ceiling
  stays.

## Why a new column rather than tightening `Instrument.name`

Three strings now have distinct jobs:

| Column | Length | Audience | Role |
|---|---|---|---|
| `Instrument.name` | `String(255)` (unchanged) | Operator-internal / audit copy | System handle. Auto-generated `instrument_N`. Never reviewer-facing. |
| `Instrument.short_label` (new) | `String(32) \| None` | Reviewer | Operator-set framing. Lands on Page button labels and the per-instrument H2 title when the reviewer rewrite ships. Capped at 32 chars at the schema layer. |
| `Instrument.description` (unchanged) | `String(2000) \| None` | Reviewer | The longer per-instrument blurb. Already drives the reviewer-surface heading; will become the H2 subtitle when the reviewer rewrite ships. |

Tightening `name` to do double duty (system handle + reviewer
framing) would tangle audit copy with reviewer copy and force the
auto-generated `instrument_N` default to get clever. A new column
keeps the three concerns clean.

## Schema

```sql
ALTER TABLE instruments ADD COLUMN short_label VARCHAR(32);
```

Nullable; default NULL. Existing rows pick up NULL automatically;
no data migration needed. The column accepts trimmed non-empty
strings ≤ 32 chars or NULL. (No CHECK constraint at the DB layer
— the service layer is the source of truth for validation.)

Alembic migration:

- New revision under `alembic/versions/`.
- `op.add_column("instruments", sa.Column("short_label", sa.String(32), nullable=True))`.
- Down migration drops the column.
- Round-trips clean on both SQLite (local) and Postgres
  (`ci-postgres` job). String length on SQLite is advisory; on
  Postgres it's enforced — that's the bedrock guard.

Model change:

```python
# app/db/models/instrument.py
short_label: Mapped[str | None] = mapped_column(String(32))
```

## Service layer

New helper in `app/services/instruments.py`:

```python
def update_short_label(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    value: str | None,
    actor: User,
    correlation_id: str,
) -> None:
    """Update an instrument's short label. value=None clears it.

    Trims whitespace; persists None when the trimmed value is
    empty. Raises ValueError when len > 32. Emits an audit event
    on change.
    """
    new_value = (value or "").strip() or None
    if new_value is not None and len(new_value) > 32:
        raise ValueError(f"short_label exceeds 32 chars: {len(new_value)}")
    if instrument.short_label == new_value:
        return  # no-op; no audit
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor,
        reason="instrument_short_label_updated",
        correlation_id=correlation_id,
    )
    old_value = instrument.short_label
    instrument.short_label = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.short_label_updated",
        summary=f"Updated short_label on instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id,
        session_id=review_session.id,
        detail={
            "instrument_id": instrument.id,
            "old": old_value,
            "new": new_value,
        },
        correlation_id=correlation_id,
    )
    db.commit()
```

`_instrument_label(instrument)` extension (line ~1004 today):

```python
def _instrument_label(instrument: Instrument) -> str:
    short = (instrument.short_label or "").strip()
    if short:
        return short
    desc = (instrument.description or "").strip()
    if desc:
        return desc
    return instrument.name
```

Existing audit-summary call sites (~10 of them) pick up the
prettier label automatically. No call-site changes needed.

## Route

The Instruments index page already has a per-instrument edit POST
that handles the description textarea — see
`update_instrument_description(...)` in
`app/services/instruments.py:2255` and its route handler. **Extend
the existing edit POST** to accept an optional `short_label` form
field alongside `description`. Both update in one round-trip.

The route reads the form, calls `update_short_label(...)` and
`update_instrument_description(...)` in sequence, and 303s back to
the Instruments page with the same anchor. Validation errors (len
> 32 from `update_short_label`) re-render the page with an inline
error banner near the offending instrument's card; `description`
errors keep their existing handling.

Lifecycle gate: the existing `_require_instrument_editable(...)`
on the route stays. Editing is rejected when the session is
`ready` (HTTP 400 with the lock-card explanation, same as today).

## Operator UI

On each per-instrument card in
`app/web/templates/operator/instruments_index.html`, the existing
edit form gets a new short-label input above the description
textarea:

```html
{% if is_editing %}
  <input form="dfsave-{{ instrument.id }}"
         type="text"
         name="short_label"
         maxlength="32"
         placeholder="(optional short label, e.g. Skills)"
         value="{{ instrument.short_label or '' }}"
         style="width: 100%;">
  <textarea form="dfsave-{{ instrument.id }}" name="description"
            placeholder="(no description)"
            style="width: 100%;">{{ instrument.description or "" }}</textarea>
{% else %}
  {% if instrument.short_label %}
    <p class="short-label-text">{{ instrument.short_label }}</p>
  {% endif %}
  <p class="description-text">{{ instrument.description or "(no description)" }}</p>
{% endif %}
```

Read-only mode shows the short label as a small heading-style line
above the description, or omits it when unset. The Section A
`<h2>Instrument #{{ loop.index }}</h2>` stays — that's the
operator's positional reference and is independent of the new
short-label field.

CSS for `.short-label-text`: small caps or bold body weight, sits
between the H2 and the description in the read-only display. Tight
margin so the three lines (H2, short label, description) read as
one identity block. (Tweakable; the spec doesn't pin specific
treatment beyond "above the description, distinct from the H2".)

## Tests

Unit:

- `tests/unit/test_instrument_builder.py` (or a new
  `tests/unit/test_short_label.py`) — unit tests on
  `update_short_label`:
  - Empty / whitespace-only value persists as NULL.
  - 32-char value persists as is.
  - 33-char value raises `ValueError`.
  - No-op when `short_label` is unchanged (no audit event).
  - On change, audit event has correct `old` / `new` detail.

Integration:

- `tests/integration/test_segment_11l.py` — new file:
  - The Instruments edit POST accepts `short_label` alongside
    `description` and persists both.
  - Validation: 400 when `short_label` is > 32 chars.
  - Lifecycle gate: 400 when the session is `ready`.
  - The read-only render shows the short label when set; omits
    when unset.
  - The audit-summary helper (`_instrument_label`) prefers
    `short_label` over `description` over `name` — exercised
    indirectly via an audit-event summary read.

Migration:

- `tests/db/test_models.py` — confirms the additive column lands
  and existing-row creation paths default to NULL.

CI: the `ci-postgres` job runs the migration round-trip and the
full suite against Postgres, so dialect divergence on the
`String(32)` length cap surfaces before merge.

## Doc impact

- **`docs/status.md`** — gains a 2026-MM-DD timeline entry
  "Segment 11L shipped (Instruments page: `Instrument.short_label`
  column + Setup-side editor; reviewer-side picks up the column
  in the multi-instrument rewrite)".
- **`spec/reviewer-surface.md`** — "Friendly short label vs. long
  description" subsection updates to flip the PR-S references to
  Segment 11L; describes the column as "shipped" rather than
  "forthcoming".
- **`spec/visual_style_rrw.md`** — same flip in "Implications for
  the reviewer surface".
- **`guide/todo_master.md`** — gains "Segment 11L" in the
  Upcoming list before the work starts; moves to Shipped on
  merge.
- **`guide/segment_11D_v2_sweep_non_session.md`** — the "Follow-on:
  Reviewer surface — multi-instrument rewrite" section's PR γ
  references Segment 11L as a hard prerequisite.
- **`spec/instruments_setup_spec.md`** (still forthcoming as a
  bigger doc) — when written, it documents `short_label` as
  already-shipped behaviour and reaches further into the rest of
  the Instruments Setup surface.

## Cross-references

- `spec/visual_style_rrw.md` "Implications for the reviewer
  surface" — describes the role each of the three columns plays.
- `spec/reviewer-surface.md` "Friendly short label vs. long
  description" — same role split, with the helper composition
  rules for the reviewer surface.
- `app/db/models/instrument.py` — model.
- `app/services/instruments.py` — service-layer (`_instrument_label`,
  the existing `update_instrument_description`, the new
  `update_short_label`).
- `app/web/templates/operator/instruments_index.html` — UI.
