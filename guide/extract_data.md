# Extract data — new Operations tab + Session Home card split

> **Stub created 2026-05-29.** Captures the plan to split the
> current Session Home "Extract data" card into two surfaces:
> a slimmed-down **Extract setup** card on Session Home
> (porting-shaped CSVs only), and a new **Extract data** tab in
> the Operations strip whose job is fine-grained shaping of the
> response data for offline analysis.

## Why this exists

The Session Home **Extract data** card today is a one-shape
download grid: one CSV per entity (Reviewers / Reviewees /
Relationships / Session settings / Responses) plus a Zip-all
bundle. It conflates two jobs:

1. **Setup data** — Reviewers / Reviewees / Relationships /
   Session settings. These are the things an operator
   originally uploaded (or could re-upload via Quick Setup).
   The natural use case is **portability**: clone a session,
   hand off to a colleague, archive a snapshot.
2. **Response data** — what reviewers produced during the
   session. The natural use case is **analysis**: pivot in
   Excel, load into pandas, slice by reviewer / reviewee /
   instrument.

Today's card serves (1) well — every row round-trips through
Quick Setup unmodified (18N PR 5 closed the last gap). It
serves (2) only at the single-shape level: one giant
denormalised Responses CSV. Operators who want to analyse
"what each reviewer said across all instruments", or "what
each reviewee got across all reviewers", end up doing the
pivot in Excel because the export forces them to.

Splitting the surface lets each side specialise: the card
stays focused on porting, and a dedicated **Extract data**
page handles response-data shaping with three lenses
(instrument / reviewer / reviewee).

The aim of the new page is **not analysis** — it's to **shape
the data so that offline analysis is easier**. No charts, no
in-app pivots. Just CSVs cut along the dimension the operator
asks for.

## Recommended end state

### Session Home — rename "Extract data" → "Extract setup"

The card stays where it is (right column of Session Home,
two-column internal layout). Its row list shrinks to the
porting-shaped CSVs only, and the column placement mirrors
Quick Setup's slot layout so the two cards read the same way:

```
Extract setup
  Reviewers         Relationships
  Reviewees         Session settings
                    Zip all  (the four CSVs above)
```

**Drop the Responses row.** It moves to the new tab. The
**Zip-all** row stays — but bundles **only the four setup
CSVs** (`{code}_setup.zip`). This matches the card's
repositioned purpose (porting / cloning) and aligns 1:1 with
the **Apply Settings CSV** input on Quick Setup: what the card
exports is exactly what Quick Setup can ingest.

The card stays interactive in every lifecycle state (no
lock-card wrap), same as today.

### Operations strip — new "Extract data" tab after "Responses"

```
Operations:  Assignments  Validate  Previews  Invitations  Responses  Extract data
```

Lives at `/operator/sessions/{id}/extract-data`. Behaves like
the other Operations pages (read-mostly, no lock card, breadcrumbs
via `operator_session_child("Extract data")`).

### Page interaction model

Two interaction shapes coexist on the page:

- **Per-lens configure + download.** The "By instrument" /
  "By reviewer" / "By reviewee" cards (below) are the
  fine-grained surface. Each card is configurable — the
  operator picks which entities to include, what shape they
  want (single CSV vs zip-of-N) — and clicks Download on that
  card to get exactly those files. The page is **the
  operator's data-shaping workbench**; each card produces a
  scoped download.
- **Top "Zip all" button.** A one-click shortcut that
  downloads every response-side CSV in a single archive
  (`{code}_responses.zip`). Members: unified `responses.csv`
  + bundle-only `reviewer_stats.csv` + `reviewee_stats.csv` +
  one `instrument_{n}.csv` per instrument sorted
  reviewee-first. This is the "I just want everything"
  affordance — operators who don't want to fiddle with
  per-lens configuration can take the full set with one
  click. Sits in the top-right of the page intro card so
  it's the first affordance the operator sees on entry.

The two shapes are complementary, not redundant. Zip-all is
the operator's "I trust the default; give me everything";
the per-lens cards are "I want it shaped a specific way."
Per-lens downloads stay independent — Zip-all doesn't
require any per-lens configuration first.

### Shipped today

- **Page layout**: two half-width cards across the top — intro
  card (left) with the "Zip all responses" button, By-instrument
  card (right) with its own "Zip all" button. Remaining lenses
  (By reviewer / By reviewee) still placeholder cards below.
- **Top "Zip all responses" button** → `responses_bundle.zip`
  (unified Responses CSV + reviewer/reviewee stats +
  per-instrument long-format files).
- **By-instrument "Zip all" button** →
  `by_instrument_bundle.zip` containing one wide-format CSV per
  instrument, named `{code}_by_instrument_{slug}.csv` where the
  slug is the instrument's short label (or `Instrument_{N}`
  fallback) sanitised to alphanumerics / `_` / `-`. Each CSV
  carries a **meta header** (instrument identity + per-field
  type/constraint rows + assignment count + pool /
  unit-of-review / self-review configuration) + blank row +
  **wide data table** (one row per assignment, columns =
  identity + tags + one column per response field + SelfReview
  + SavedAt + SubmittedAt). Group-scoped instruments collapse
  the same way the unified Responses CSV does.

### The three lenses on the new page

| Lens | Shape | Use case |
|---|---|---|
| **By instrument** | One CSV per instrument; rows = (reviewee × reviewer) pairs for that instrument; columns = response fields side-by-side. Plus a "All instruments unified" download that matches today's `responses.csv`. | "How did everyone score on this rubric?" Cross-reviewer comparison on one instrument. |
| **By reviewer** | One CSV per reviewer; rows = every response that reviewer made; columns include instrument / reviewee / field / value. Plus a per-reviewer summary roll-up (one row per reviewer, completion + counts). | "What did this reviewer produce?" Individual reviewer audit / coaching. |
| **By reviewee** | One CSV per reviewee; rows = every response made *about* that reviewee; columns include reviewer / instrument / field / value. Plus a per-reviewee summary roll-up (one row per reviewee, aggregated counts / averages where numeric). | "What did everyone say about this reviewee?" Feedback packet for the reviewed person. |

Each lens offers:

- A **single combined download** (one CSV across all instruments / reviewers / reviewees in that lens) for analyst-tool ingestion.
- A **per-entity zip** (one CSV per instrument / reviewer / reviewee) for human-readable handoff.

Self-review / group-scoped semantics carry over from the
existing `responses.csv`:

- `SelfReview` flag stays available in every lens.
- Group-scoped instruments collapse to one row per
  (reviewer × group × field), same as today's
  `serialize_responses_for_instrument`.

### What the new page does NOT do

- **No charts, no aggregates beyond simple roll-ups.** Means
  (averages, counts, completion %) only when they're cheap
  CSV columns. No histograms, no rendered tables-as-images.
- **No row-level filtering UI.** Operators get whole-session
  cuts along three axes; finer slicing happens offline. (If
  operator demand surfaces later, a future iteration can add
  filters; the stub deliberately leaves them out to keep the
  first version small.)
- **No exports of audit / lifecycle metadata.** Audit log
  download already lives at Sys Admin per industry best
  practice (`docs/status.md` Segment 16A notes); the new
  page stays response-data only.

## Open design questions

These are intentionally left open for the segment plan PR to
resolve:

1. **Per-reviewer / per-reviewee single CSV vs zip of CSVs.**
   The "by reviewer" lens could be one big CSV (rows tagged
   with `ReviewerName`) *or* a zip of N CSVs (one per reviewer).
   Same for "by reviewee". Single CSV is simpler; zip-of-N is
   better for handoff (you can email one reviewee their own
   file without leaking others'). Probably ship both — the
   download buttons live side-by-side on the same page.

2. **Numeric roll-ups.** Per-reviewee summary file likely
   wants `mean` / `median` columns for numeric response fields.
   How aggressive? Just `mean` and `count` to start; defer
   `median` / `std` until requested.

3. **Group-scoped reviewee semantics.** When the reviewee
   lens runs over a group-scoped instrument, the natural
   "row per reviewee" is ambiguous — the response is *about
   the group*, not any individual member. Default: surface
   one row per *group identity* (the composed name from
   `_compose_group_identity`), and a separate
   "by group member" expansion that fans the group response
   back out to each member. Keep both available.

4. **The Zip-all on Session Home** post-split. Today it's
   five CSVs; under the rename it's four (setup-only). Some
   operators may have scripts that expect the Responses
   file inside the bundle. Beta-state assumption → no real
   pipelines exist → break it cleanly. The new Extract data
   page offers its own zip downloads for response data.

5. **Settings.csv stays on Session Home?** It's also
   round-trippable (Quick Setup ingests it), so yes — it
   belongs in the Extract setup card. The Responses CSV is
   the one that moves.

## Blast radius (rough estimate, pre-execution)

- **New page surface** — `app/web/routes_operator/_extract_data.py`
  (new), `app/web/templates/operator/session_extract_data.html`
  (new), `app/web/views/_extract_data_page.py` (new — view-shape
  adapter). Three new files, maybe ~500-800 LOC total.
- **Existing card rename** — `app/web/views/_extract_data.py`
  (rename internal vars / strings to "Extract setup"; drop the
  Responses row; rewire bundle to four CSVs),
  `app/web/templates/operator/partials/_extract_data_card.html`
  (rename, drop responses row), `app/web/templates/operator/
  session_detail.html` (include path stays if file is renamed
  in place).
- **Top nav** — `app/web/templates/operator/partials/
  session_top_nav.html` (add the new tab + extend `_ops_pages`).
- **Bundle builder** — `app/services/extracts/zip_bundle.py`
  (drop responses from the home bundle; add new bundles for
  the response-data page lenses).
- **Tests** — likely 6-10 new tests (each lens × single vs zip
  × happy path; plus a few permission / lifecycle tests).
- **Spec docs** — `spec/session_home.md` (rename card),
  potentially a new `spec/extract_data.md` (or fold into an
  existing operator-page spec) for the new page.

Estimate: **3-4 PRs**:

1. Rename the Session Home card to **Extract setup**; drop
   the Responses row from it; rewire the Zip-all bundle to
   four CSVs. (Mechanical; no new routes.)
2. Add the new **Extract data** tab + route stub; render an
   empty page with the three-lens skeleton + tile placeholders.
3. Wire the **by-instrument** lens (mostly re-uses
   `serialize_responses_for_instrument`).
4. Wire the **by-reviewer** + **by-reviewee** lenses
   (new serialisers; reuse the response query / group-scope
   collapsing machinery).

PR 1 is independent of 2-4 and can land first to clean up
the Session Home surface.

## Sequencing

- **Independent of the queued schedule.** Doesn't block or
  depend on URL remodel / 14B / 19 / 20.
- **Best after URL remodel.** If URL remodel lands first,
  any internal links from the new page to the reviewer
  surface ship with `/me/` prefixes from day 1.
- **Independent of the participant model.** The new page is
  operator-only; nothing in it presumes reviewee or observer
  identities.
- **Independent of 14B.** No email surface; no outbox
  interaction.

## Risk acceptances

- **Operators who scripted against the Zip-all bundle
  expecting Responses inside.** Beta-state → no real scripts
  → break cleanly. The new page exports the same data
  shaped better; the responses Zip-all button is the direct
  replacement.
- **Filename change: ``{code}_bundle.zip`` →
  ``{code}_setup.zip``.** Same rationale — beta-state, no
  scripts to break. The new ``{code}_responses.zip`` covers
  the response-data side.
- **URL shape collisions.** `extract-data` as a tab slug
  doesn't collide with existing routes
  (`/operator/sessions/{id}/extract-data` is unused per
  `grep`).
- **Card vs page name confusion.** "Extract setup" (card on
  Home) vs "Extract data" (Operations tab) — distinct enough
  that the operator won't conflate them. The card label
  carries the setup-portability framing; the tab label
  carries the analysis-shaping framing.

## Done when

- Session Home card label reads **Extract setup**; its row
  list is Reviewers / Reviewees / Relationships / Session
  settings / Zip-all-of-four; the Responses row is gone.
- A new **Extract data** tab appears in the Operations strip
  between Responses and the end of the strip.
- The Extract data page surfaces three lens sections
  (by instrument / by reviewer / by reviewee) with at least
  a single CSV per lens and (recommended) a zip-of-N
  per-entity bundle per lens.
- Group-scoped collapsing and the `SelfReview` flag carry
  over to the new lenses.
- Existing `/operator/sessions/{id}/export/responses.csv`
  route stays live (the by-instrument unified CSV redirects
  here or reuses the same serialiser); operators with
  pre-existing direct-URL habits don't 404.
- Full suite passes (existing extracts tests unchanged;
  new tests added for the new lenses).
- `guide/extract_data.md` → `guide/archive/` per the
  segment-closeout convention; `spec/session_home.md`
  updated for the card rename; a new spec doc (or section)
  covers the page if not already.

## Related context

- `app/web/views/_extract_data.py` — the current Session
  Home card view adapter (becomes "Extract setup").
- `app/web/routes_operator/_extracts.py` — existing CSV
  routes (`/sessions/{id}/export/{kind}.csv`); new routes
  may reuse these or sibling-mount under
  `/sessions/{id}/extract-data/...`.
- `app/services/extracts/responses_extract.py` — existing
  serialisers: `serialize_responses` (unified),
  `serialize_responses_for_instrument` (by-instrument lens
  is mostly this), `serialize_reviewer_session_summary`
  (already wired for the reviewer-side surface; by-reviewer
  operator lens reuses the same shape).
- `spec/session_home.md` — Session Home page spec; the card
  rename lands here.
- `guide/url_remodel.md` — landing this first means internal
  links in the new page ship with the future-correct URL
  prefix on day 1.
