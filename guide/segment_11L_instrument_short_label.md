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

- New revision under `alembic/versions/` with
  `down_revision = "b2c3d4e5f6a7"` (the current head as of
  2026-05-05; verify with `alembic heads` before drafting).
- Use the existing batch-alter-table convention (every prior
  migration in `alembic/versions/` opens a `batch_alter_table`
  context — the form is friendlier on SQLite where bare
  `ALTER TABLE` has limitations):

  ```python
  def upgrade() -> None:
      with op.batch_alter_table("instruments", schema=None) as batch_op:
          batch_op.add_column(
              sa.Column("short_label", sa.String(length=32), nullable=True)
          )

  def downgrade() -> None:
      with op.batch_alter_table("instruments", schema=None) as batch_op:
          batch_op.drop_column("short_label")
  ```

- Round-trips clean on both SQLite (local) and Postgres
  (`ci-postgres` job). String length on SQLite is advisory; on
  Postgres it's enforced — that's the bedrock guard.

Model change:

```python
# app/db/models/instrument.py
short_label: Mapped[str | None] = mapped_column(String(32))
```

## Service layer

New helper in `app/services/instruments.py`, modelled on the
existing `update_instrument_description(...)` at line 2255 so it
reads as a sibling — same arg shape, same lifecycle-invalidation
hook, same `write_event` import (the module already imports
`from app.services.audit import write_event`), same
`[old, new]` audit-detail list shape:

```python
def update_short_label(
    db: Session,
    *,
    instrument: Instrument,
    short_label: str | None,
    actor: User,
) -> Instrument:
    """Update an instrument's short_label. short_label=None clears it.

    Trims whitespace; persists None when the trimmed value is
    empty. Raises ValueError when len > 32. Emits an audit event
    only when the stored value actually changes.
    """
    cleaned = short_label.strip() if isinstance(short_label, str) else None
    new_value = cleaned or None
    if new_value is not None and len(new_value) > 32:
        raise ValueError(
            f"short_label exceeds 32 chars: {len(new_value)}"
        )
    if instrument.short_label == new_value:
        return instrument  # no-op; no audit, no invalidate

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_short_label_updated",
    )
    old_value = instrument.short_label
    instrument.short_label = new_value
    db.flush()
    write_event(
        db,
        event_type="instrument.short_label_updated",
        summary=(
            f"Updated short_label on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "short_label": [old_value, new_value],
        },
    )
    db.commit()
    return instrument
```

Three things to call out:

- **No `correlation_id` arg.** `update_instrument_description`
  doesn't take one either, and neither does its
  `lifecycle.invalidate_if_validated` call — so this helper
  matches.
- **Audit detail uses a `[old, new]` list**, not a `{"old": …,
  "new": …}` dict. Matches the convention in
  `update_instrument_description` (`detail={"description":
  [old_value, new_value]}`).
- **The summary uses `_instrument_label(instrument)`** (the
  prettier-label helper) rather than bare `instrument.name`.
  Most audit-summary call sites in this file already use
  `_instrument_label` — `update_instrument_description` is the
  one outlier still using `instrument.name` directly. Don't
  copy that outlier into the new helper; align with the
  majority pattern.

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

Existing audit-summary call sites (13 of them across
`app/services/instruments.py`) pick up the prettier label
automatically. No call-site changes needed. No tests pin
specific summary copy — verified via
`grep -rnE 'event\.summary' tests/` finding no instrument-summary
assertions.

## Route

**Where description gets persisted today.** Despite the orphan
`/edit` route at `app/web/routes_operator.py:1116` (which exists
but no template or test calls), the actual description-update
path runs through the **bulk fields-save handler** at
`app/web/routes_operator.py:1465` (`instrument_bulk_save_fields`)
— see lines 1684-1695:

```python
if "description" in form:
    submitted_desc = form.get("description")
    cleaned = (
        submitted_desc.strip() if isinstance(submitted_desc, str) else None
    ) or None
    if cleaned != instrument.description:
        instruments_service.update_instrument_description(
            db, instrument=instrument, description=cleaned, actor=user
        )
```

The description `<textarea>` in the template carries
`form="dfsave-{{ instrument.id }}"` so it submits with the bulk
Display-Fields form, posting to `/fields/save`.

**The 11L change.** Add a parallel block in
`instrument_bulk_save_fields` that processes `short_label`
identically:

```python
if "short_label" in form:
    submitted_label = form.get("short_label")
    try:
        instruments_service.update_short_label(
            db,
            instrument=instrument,
            short_label=(
                submitted_label
                if isinstance(submitted_label, str)
                else None
            ),
            actor=user,
        )
    except ValueError:
        # Inline-error path: see "Validation errors" below.
        ...
```

The handler already calls `_require_instrument_editable(review_session)`
at line 1473 — that lifecycle gate covers `short_label` updates
the same way it covers description. No new gate needed.

The orphan `/edit` route is **not** 11L's problem. Leave it
alone (or retire it as separate cleanup; out of scope here).

**Validation errors.** A 33-char `short_label` raises `ValueError`
in the service helper. The bulk handler doesn't currently
re-render with inline errors — failures elsewhere (e.g. a missing
required field) cascade through normal exception handling. For
11L, two viable paths:

- **(a)** Catch the `ValueError` in the handler, attach a
  `?short_label_error={instrument.id}` flash to the redirect, and
  re-render with an inline `.banner.banner-warning` near that
  instrument's card. Mirrors the `?saved=` flash already in place
  at line 1700.
- **(b)** Lean on the HTML5 `maxlength="32"` attribute (already
  in the plan's UI spec) so the browser prevents oversized input
  from being submitted in the first place. Server-side cap is a
  defensive fallback; if it ever fires, return HTTP 400 with a
  generic error message.

Path (b) is simpler and adequate — the `maxlength` attribute is
the user-visible guardrail, and a 400 from server-side enforcement
should be effectively unreachable. Recommend (b) for PR scope.

Redirect: same as today — 303 back to the Instruments page with
`?saved={instrument.id}#instrument-{instrument.id}`.

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
  - No-op when `short_label` is unchanged (no audit event,
    no `invalidate_if_validated` call).
  - On change, audit event detail carries `short_label:
    [old, new]` shape (matching `update_instrument_description`'s
    convention).
  - Audit summary uses `_instrument_label(instrument)` (so a
    short-label set on an unrelated previous edit shows up in
    subsequent audit copy).

Integration:

- `tests/integration/test_segment_11l.py` — new file:
  - The bulk fields-save POST
    (`/operator/sessions/{id}/instruments/{instrument_id}/fields/save`)
    accepts a `short_label` form field alongside the existing
    `description` and persists both in one round-trip.
  - Server-side validation: a 33-char `short_label` returns
    HTTP 400 (the defensive fallback for the
    HTML5 `maxlength` attribute that browsers normally enforce).
  - Lifecycle gate: 400 when the session is `ready`. (Existing
    `_require_instrument_editable` on the handler covers this;
    no new gate to test in isolation, but verify it still
    catches `short_label`-only updates.)
  - The read-only render shows the short label when set; omits
    when unset.
  - The audit-summary helper (`_instrument_label`) prefers
    `short_label` over `description` over `name` — exercised
    indirectly by setting a short_label, doing some other
    instrument edit (e.g. add a field), and reading the
    resulting audit-event summary.

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
