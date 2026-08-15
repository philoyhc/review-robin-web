# Rehydrate an extracted session — functional spec

> **Status: proposed (not yet built).** This is a design spec for a new
> capability, written against the current code seams. `docs/` normally
> documents shipped behaviour; this file is the exception until the
> feature lands, at which point it should be trimmed to "how it works
> today." Companion to `spec/sessions_overview.md` (the lobby),
> `spec/setup_pages.md`, and `spec/assignments.md`.

## 1. What this is

**Rehydrate** turns a *complete set of extract CSV files* from a past
session back into a live, working session — same settings, same
populations, and with the collected response data repopulated. It is the
inverse of the Extract surfaces (`app/web/routes_operator/_extracts.py`).

The reconstructed session is always named **`<original name>_REHYD`**
(with a numeric suffix on collision — [§5](#5-naming-and-description)),
carries a provenance note appended to its Description, and is created
through a dedicated **"Rehydrate Extracted Session"** card on the *Add New
Session* page. When that card is used, **every other input on the Add New
Session page is ignored** — the extract files are the sole source of
truth.

### Why it's not just "clone"

`session_clone.clone_session` already deep-copies a session's config +
roster into a fresh draft, and `session_config_io.apply_session_config`
already round-trips settings via CSV. Both operate on an **in-database
source** and neither copies **responses**. Rehydrate differs on two axes:

1. its source is **external CSV files** (an extract taken earlier, possibly
   from a session that has since been purged or archived), not a live row;
2. it **repopulates response data**, which nothing in the codebase can do
   today.

## 2. Capability boundary — what rehydrate can and cannot reconstruct

Grounded in what the extract actually captures and what importers exist:

| Session facet | Extract source | Import path today | Rehydrate approach |
|---|---|---|---|
| Session metadata, instruments (+ display/response fields), rule sets, field labels, email overrides, data shapes | `settings.csv` | ✅ `session_config_io.apply_session_config` | Apply as-is |
| Reviewers / Reviewees / Observers | `reviewers.csv` / `reviewees.csv` / `observers.csv` | ✅ `csv_imports.save_*` | Import as-is |
| Relationships (reviewer↔reviewee pairs + status + pair tags) | `relationships.csv` | ✅ `relationships.save_relationships` | Import as-is |
| **Assignments** | derived (rule-generated) | ⚠️ no importer — regenerated from rules | Regenerate from imported rule sets, then backfill any pair present in `responses.csv` |
| **Responses** (the data) | `responses.csv` (in the responses bundle) | ❌ **none — output-only** | **Net-new importer** ([§6.4](#64-load-responses)) |
| Instrument visibility policies (`instrument_view_policies`) | `settings.csv` **(via prerequisite)** | ✅ once the [prerequisite](#prerequisite-extend-the-settings-round-trip) lands | Apply as-is |
| `relationships_enabled` / `observers_enabled` toggles | `settings.csv` **(via prerequisite)** | ✅ once the [prerequisite](#prerequisite-extend-the-settings-round-trip) lands | Apply as-is |
| Invitations, email outbox, `results_acknowledged_at`, participant tokens | not reconstructable / regenerated | — | Not restored ([§9](#9-limitations-and-known-gaps)) |

Rows one to three, plus the two rows closed by the
[prerequisite](#prerequisite-extend-the-settings-round-trip), reuse
existing (or prerequisite-extended) settings/roster seams. The **responses**
row is the genuinely new work.

## Prerequisite: extend the settings round-trip

**Separate work item, lands first — valuable on its own, and a hard
dependency of rehydrate.**

`instrument_view_policies` (the per-instrument 3×2 visibility grid) and the
session-level `relationships_enabled` / `observers_enabled` toggles are
currently serialized by neither `session_config_io` nor `session_clone`.
So they don't survive a plain `export settings.csv → import settings.csv`
today — a real gap in the **normal** settings round-trip, independent of
rehydrate. Close it there, not inside rehydrate:

- **Serialize** — extend `session_config_io._serialize` to emit
  `instruments[n].view_policies[audience].*` rows (the while-ongoing and
  after-release *granularity* + *identification* pairs and `observer_tag`,
  per `spec/visibility_policy.md`) and two `session.relationships_enabled`
  / `session.observers_enabled` rows.
- **Apply** — extend `session_config_io._apply` to parse and restore them
  within the existing instrument wipe-and-rebuild pass.
- **Test** — a round-trip test (`serialize → apply → assert view policies +
  toggles unchanged`), matching how the rest of the settings round-trip is
  covered.

Once this ships, `settings.csv` fully describes visibility policy and the
feature toggles, so **rehydrate inherits them for free** — no
rehydrate-specific view-policy code, and every session's export/import
(clone-by-config, backup/restore) also stops losing them. This is why it's
a prerequisite rather than a rehydrate sub-task.

## 3. Entry point — the "Rehydrate Extracted Session" card

**Location.** The *Add New Session* page, `GET /operator/sessions/new`
(handler `new_session_form`, `app/web/routes_operator/_session_home.py`;
template `operator/session_new.html`). Rehydrate is a **new card** on that
page, visually separated from (and below) the normal create form + Quick
Setup upload slots.

**Card contents.**

- **Heading:** "Rehydrate Extracted Session".
- **Warning block** (`.note`-style callout, Alert-tinted), verbatim intent:
  > Rehydrating rebuilds a past session — its settings, people, and all
  > collected responses — from a **complete set of extract files**. You
  > need: **`reviewers.csv`**, **`reviewees.csv`**, **`settings.csv`**,
  > and the CSVs from **Extract data → "Extract all data"** (the
  > responses bundle). If your session used relationships or observers,
  > include **`relationships.csv`** / **`observers.csv`** too.
  >
  > **Everything else on this page is ignored when you rehydrate** — the
  > name, code, description, and any files staged in the Quick Setup slots
  > above. The rehydrated session takes its identity and data entirely
  > from the extract files.
- **Upload control.** A single multi-file input **or** two ZIP inputs —
  accept whichever the operator has to hand ([§4](#4-required-file-set)):
  the Setup bundle (`{code}_setup.zip`) + the Responses bundle
  (`{code}_responses.zip`), and/or the loose CSVs. `multiple` file input;
  ZIPs are unpacked server-side.
- **Submit.** A single Primary button "Rehydrate session", posting to a
  new route **`POST /operator/sessions/rehydrate`** (multipart). This is a
  distinct handler from `create_session` (`POST /operator/sessions`) so
  the "ignore all other inputs" contract is structural, not conditional.

**Button style.** Primary (per `spec/domain_assumptions.md`). The warning
callout uses the Alert tint, not Danger — rehydrate is additive (it
creates a new session; it never mutates or deletes an existing one).

## 4. Required file set

Rehydrate needs the union of the **Setup bundle** and the **Responses
bundle**. The operator may upload the two ZIPs, the loose CSVs, or a mix;
the handler resolves files by name.

**Required always:**

| File | Header (must match) | Provides |
|---|---|---|
| `*_settings.csv` | `field,value,data_type` (`session_config_io._rows.HEADER`) | All config: session metadata, instruments + fields, rule sets, field labels, email overrides, data shapes |
| `*_reviewers.csv` | `ReviewerName,ReviewerEmail,ReviewerTag1..3,PhotoLink` | Reviewer population |
| `*_reviewees.csv` | `RevieweeName,RevieweeEmail,RevieweeTag1..3,PhotoLink` | Reviewee population |
| `*_responses.csv` | the 21-column responses header (`responses_extract.HEADER`) | The response data + `SavedAt`/`SubmittedAt`/`Version` |

**Required conditionally** (presence also *sets the feature toggle* — see
[§6.2](#62-apply-settings)):

| File | Needed when | Provides |
|---|---|---|
| `*_relationships.csv` | the session used relationships | `ReviewerEmail,RevieweeEmail,PairContextTag1..3,Status` pairs |
| `*_observers.csv` | the session used observers | `ObserverEmail,ObserverName,ObserverTag1,Status` |

**Completeness validation (the card's promise, enforced).** Before
creating anything, the handler verifies the four required files are
present and their headers match. On any miss it rejects the whole upload
with a specific, actionable error and creates **no** session — e.g.
*"Missing settings.csv — rehydrate needs the full extract set"* or
*"responses.csv header doesn't match the expected format; re-export via
Extract data → Extract all data."* Filenames are matched by suffix
(`*_settings.csv` etc.), tolerating the `{code}_` prefix the extracts
emit and any operator renaming that preserves the suffix.

**Ignored files.** `reviewer_stats.csv`, `reviewee_stats.csv`, the
per-instrument `*_instrument_{N}.csv`, saved data-shape CSVs, and
`participant_tokens.csv` may be present in the bundle but are **not read**
by rehydrate (stats/tokens are derived; per-instrument CSVs duplicate
`responses.csv`). They are silently ignored, not errors.

## 5. Naming and description

**Name.** Read the original name from the `session.name` row of
`settings.csv`. The rehydrated name is:

- `"<original name>_REHYD"` if no session with that exact name exists;
- otherwise `"<original name>_REHYD_1"`, `"_REHYD_2"`, … choosing the
  lowest free integer.

Collision is checked by exact-match against existing **session names the
operator owns** (`session_operators` for the caller). Names are **not**
unique in the schema (only `code` is — `review_session.py`), so this is a
service-level scan, mirroring how `session_clone` derives a unique *code*.
If appending the suffix would exceed the 255-char `name` limit, the base
is truncated to fit. Rehydrating an already-`_REHYD` session yields
`…_REHYD_REHYD` (literal rule; acceptable).

**Code.** The original `session.code` from `settings.csv` **cannot** be
reused — `sessions.code` has a unique index. Derive a fresh unique code
the way `session_clone._unique_code` does: `"<original code>-rehyd"`, then
`"-rehyd-2"`, … until free.

**Description.** Take the original `session.description` and append a
provenance paragraph:

```
[Rehydrated on {YYYY-MM-DD} from an extract of "{original name}"
(code {original code}). Populations, settings, and responses were
reconstructed from extract CSV files.]
```

(The date is stamped by the caller, not inside any pure/deterministic
layer.)

## 6. Reconstruction pipeline

Order matters — responses key onto assignments, which key onto instruments
+ rosters, which key onto the applied settings. The whole pipeline runs as
one logical unit; on any failure the partially-built session is hard-deleted
so no half-rehydrated session survives ([§7](#7-atomicity-and-audit)).

### 6.1 Create the shell session

Parse `settings.csv` first to learn the original name/code, then create a
new **draft** via `sessions.create_session` with:

- `name` = the computed `_REHYD[_n]` name,
- `code` = the derived unique code,
- `description` = original + provenance note,
- `relationships_enabled` / `observers_enabled` = presence of the
  respective CSV ([§6.2](#62-apply-settings)).

`create_session` adds the owner `SessionOperator`, seeds a default
instrument (immediately replaced by the settings apply), and writes
`session.created`.

### 6.2 Apply settings

Call `session_config_io.apply_session_config(db, new_session, rows)` with
the parsed `settings.csv` rows, **after rewriting two rows**: replace the
`session.name` value with the `_REHYD` name and the `session.code` value
with the derived code (otherwise apply would restore the original name and
collide on code). `apply` rebuilds instruments (+ display/response
fields), session rule sets, field labels, email overrides, and data
shapes, and restores per-instrument runtime flags including
`accepting_responses` and `responses_visible_when_closed`.

With the [prerequisite](#prerequisite-extend-the-settings-round-trip) in
place, `relationships_enabled` / `observers_enabled` **and** the instrument
visibility policies are carried in `settings.csv` and restored by `apply` —
no rehydrate-specific handling. (Defensive fallback for a legacy extract
taken before the prerequisite: infer the toggles from file presence and
leave view policies at defaults.)

### 6.3 Import populations and regenerate assignments

1. **Reviewers / Reviewees / Observers** via `csv_imports.save_reviewers`
   / `save_reviewees` / `save_observers` (observers only if enabled). Same
   dedup + email-lowercasing + cross-table-identity rules as normal
   import; `reviewees` keep their `email_or_identifier` (non-email handles
   allowed).
2. **Relationships** (if enabled) via `relationships.save_relationships`,
   resolving emails against the just-imported rosters.
3. **Assignments** — regenerate from the imported rule sets via the
   canonical `assignments.generate` path (deterministic given seed + rules
   + populations, so it reproduces the original assignment graph for
   rule-driven sessions). Then **backfill**: for every distinct
   `(reviewer, reviewee, instrument)` that appears in `responses.csv` but
   has no generated assignment, create one (`include=True`,
   `is_self_review` = reviewer-email == reviewee-email,
   `created_by_mode="manual"`). This guarantees every response has a home
   even where a manual per-pair toggle diverged from the rules
   ([§9](#9-limitations-and-known-gaps)).

### 6.4 Load responses

**New machinery** (no importer exists). A responses parser reads
`responses.csv` and, for each data row, resolves identity to the
newly-created PKs and inserts a `Response`:

- **Reviewer** ← `ReviewerEmail` (lower-cased) → new `Reviewer.id`.
- **Reviewee** ← `RevieweeEmail` (lower-cased / identifier) → new
  `Reviewee.id`.
- **Instrument** ← `InstrumentShortLabel` (primary key for the match;
  unique per session), falling back to the positional `InstrumentName`
  = `instrument_{n}` → the instrument at `order = n`.
- **Response field** ← `(instrument, FieldKey)` →
  `InstrumentResponseField.id` (unique `(instrument_id, field_key)`).
- **Assignment** ← `(reviewer, reviewee, instrument)` → `Assignment.id`
  (guaranteed to exist by [§6.3](#63-import-populations-and-regenerate-assignments)).
- **Insert** `Response(assignment_id, response_field_id, value=Value,
  saved_at=parse(SavedAt), submitted_at=parse(SubmittedAt),
  version=Version)`, respecting the unique `(assignment_id,
  response_field_id)` constraint. `Value` maps straight to the `Text`
  column (no type coercion — numeric values are already stored as text).

**Format details.** `responses.csv` is *sectioned*: per-instrument
preamble rows (`instrument_{n}`, then `(field_key, help_text)` rows), a
blank row, then the 21-column header, then data. The parser walks
sections, using the preamble only to disambiguate instruments; the
`InstrumentShortLabel` column on each data row is the durable key.

**Scale.** `responses.csv` for a large session (e.g. 1,500 reviewers) far
exceeds the roster importer's `MAX_ROWS = 5000` / `MAX_BYTES = 1 MiB`
caps (`csv_imports.py`). The responses parser therefore **must not** reuse
those limits — it streams rows and inserts in batches
(`Session.bulk_save_objects` or chunked `add_all` + periodic flush),
with its own, higher bound. This is called out because reusing
`csv_imports`' guard rails here would silently truncate real data.

### 6.5 Land the session

Leave the session in **`draft`** — assignments are generated
([§6.3](#63-import-populations-and-regenerate-assignments)) and all data is
loaded, but the session is **not activated** ([§8](#8-target-lifecycle-state)) —
and write the `session.rehydrated` audit event.

## 7. Atomicity and audit

- **All-or-nothing.** If any step fails (bad file, unresolvable identity,
  constraint violation), roll back and **hard-delete** the new session
  (`sessions.delete_session`) so the lobby never shows a half-built
  rehydrated session. Report the failing step to the operator.
- **Audit.** Emit one `session.rehydrated` event on success, with a
  `counts` payload (`reviewers`, `reviewees`, `observers`, `relationships`,
  `assignments`, `responses`) and a `context`/`refs` recording the original
  name + code from the extract. Register `session.rehydrated` in
  `EVENT_SCHEMAS` (the strict-mode test gate rejects unregistered emitters
  — see `CLAUDE.md` "Audit events").

## 8. Target lifecycle state

The rehydrated session lands in **`draft`**, with **all assignments
generated** ([§6.3](#63-import-populations-and-regenerate-assignments)) and
all response data loaded, but **not activated**. The operator reviews the
rebuilt session and runs Validate → Activate themselves when ready.

Rationale for not auto-activating: `activate_session` has real gates (a
clean `ReadinessReport`, acknowledged warnings) that a rehydrate shouldn't
silently bypass, and activation force-flips **every** instrument to
`accepting_responses=True` — which would *re-open* a previously-closed
session for new input and overwrite the per-instrument runtime flags that
[§6.2](#62-apply-settings) just restored. A rehydrated draft with fully
generated assignments and loaded data is completely viewable and operable;
activation stays a deliberate, separate operator gesture.

## 9. Limitations and known gaps

Stated plainly so the card copy and the PR description can be honest:

- **Visibility policies + feature toggles** (`instrument_view_policies`,
  `relationships_enabled`, `observers_enabled`) round-trip through
  `settings.csv` once the
  [prerequisite](#prerequisite-extend-the-settings-round-trip) lands —
  which is a hard dependency of rehydrate, so by ship time these are not
  gaps. (Only a legacy pre-prerequisite extract would fall back to default
  view policies + presence-inferred toggles.)
- **Manual per-pair assignment toggles may not round-trip.** Assignments
  are regenerated from rules; a session where the operator hand-toggled
  individual `(reviewer, reviewee)` `include` flags on the Assignments
  page isn't captured by the standard extract set (only the never-imported
  coverage CSV holds it). Rehydrate backfills assignments for any pair
  that *has* responses ([§6.3](#63-import-populations-and-regenerate-assignments)),
  so no response is lost, but an *empty-but-included* manual assignment may
  not reappear.
- **Not restored:** invitations, email-outbox send history,
  `Reviewee.results_acknowledged_at`, and participant anonymization
  tokens (regenerated fresh for the new session, so they won't match the
  original `participant_tokens.csv`). These match `session_clone`'s
  existing exclusions and are acceptable for a working copy.
- **Group-scoped instruments / self-reviews** reconstruct correctly as
  long as the rule sets + `group_kind` in `settings.csv` regenerate the
  same graph; the responses backfill covers any residual pairs.

## 10. Resolved decisions

1. **Target lifecycle** — land as **`draft`** with all assignments
   generated but **not activated** ([§8](#8-target-lifecycle-state)). The
   operator activates deliberately.
2. **Visibility-policy / config gap** — closed **outside** rehydrate, as a
   separate [prerequisite](#prerequisite-extend-the-settings-round-trip)
   that extends the normal settings round-trip to cover
   `instrument_view_policies` and the feature toggles.
3. **Name-collision scope** — match `_REHYD` names against the **operator's
   own** sessions ([§5](#5-naming-and-description)).

## 11. New machinery to build

Grounded in the existing seams so the diff stays small:

- **Route.** `POST /operator/sessions/rehydrate` +
  card markup on `operator/session_new.html`
  (`app/web/routes_operator/_session_home.py` / `_quick_setup.py`
  sibling). Thin handler: unpack ZIPs, resolve files, call the service,
  redirect to the new Session Home.
- **Orchestrator service.** `app/services/session_rehydrate.py` —
  `rehydrate_session(db, *, files, user, correlation_id) -> ReviewSession`,
  running the [§6](#6-reconstruction-pipeline) pipeline and owning the
  all-or-nothing rollback. Reuses `sessions.create_session`,
  `session_config_io.apply_session_config`, `csv_imports.save_*`,
  `relationships.save_relationships`, and `assignments.generate`.
- **Responses importer.** `app/services/extracts/responses_import.py` (the
  net-new piece) — a streaming parser for the sectioned 21-column
  `responses.csv` and the identity→PK resolution + batched `Response`
  insert in [§6.4](#64-load-responses). Its own size limits, independent
  of `csv_imports`.
- **Audit.** Register `session.rehydrated` in `EVENT_SCHEMAS`.

## 12. Testing expectations

- **Round-trip integration test.** Build a session with reviewers,
  reviewees, relationships, multiple instruments, and submitted responses;
  run the real Extract routes to produce the CSVs; feed them to
  `rehydrate_session`; assert the new session has the `_REHYD` name, the
  appended description note, matching populations, matching instruments +
  fields, regenerated assignments covering every response, and byte-equal
  response values / `SavedAt` / `SubmittedAt` / `Version`.
- **Collision test** — rehydrating the same extract twice yields `_REHYD`
  then `_REHYD_1`, with distinct unique codes.
- **Incompleteness tests** — each missing required file (and a malformed
  header) is rejected with a specific message and creates no session.
- **Rollback test** — a mid-pipeline failure leaves zero new rows.
- **Scale test** — a `responses.csv` well beyond 5000 rows imports fully
  (guards the [§6.4](#64-load-responses) limit note).
- **Ignore-other-inputs test** — posting the rehydrate form with a stray
  name/code/staged file uses only the extract identity.

## 13. References

- Extract surfaces: `app/web/routes_operator/_extracts.py`,
  `app/services/extracts/` (`responses_extract.py`, `reviewers_extract.py`,
  `reviewees_extract.py`, `relationships_extract.py`, `observers_extract.py`,
  `zip_bundle.py`).
- Config round-trip: `app/services/session_config_io/`
  (`_serialize.py`, `_apply.py`, `_rows.py`).
- Roster import: `app/services/csv_imports.py`,
  `app/services/relationships.py`.
- Create / clone / lifecycle: `app/services/sessions.py`,
  `app/services/session_clone.py`, `app/services/session_lifecycle.py`.
- Assignments: `app/services/assignments/` + `spec/assignments.md`.
- Lobby / create UI: `spec/sessions_overview.md`,
  `app/web/routes_operator/_session_home.py`,
  `app/web/routes_operator/_quick_setup.py`.
