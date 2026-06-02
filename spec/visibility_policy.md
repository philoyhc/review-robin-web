# Response visibility policy

Per-instrument, per-audience grants controlling **who** can see this instrument's responses, **in what form**, and **during which window**. The schema lives on `instrument_view_policies`; the resolver consumes one row per (instrument, audience) pair at view time (no materialisation onto `assignments`).

This spec is the operator-facing functional contract. The cross-cutting participant-model design lives in `guide/archive/participant_model_upgrade.md`; the per-page operator UI sits in `spec/instruments.md` (Band 3 of the instrument card).

## Scope of this policy — strictly per-pair flow

The visibility policy governs **the information flow from reviewers to the reviewees they are reviewing** (and the mirrors of that flow back to the reviewer themselves and out to the relevant observers). It is deliberately **not** a mechanism for surfacing cross-cohort summaries — e.g. *"every reviewer sees the cohort-wide average of every instrument, anonymised"*. That kind of cohort-aggregate publication belongs to a separate, future mechanism: an **Operator- or Observer-published report** that someone with cohort-wide standing explicitly makes available to one or more audiences.

Keeping the two mechanisms separate avoids loading the per-instrument audience policy with cohort-aggregate semantics it isn't shaped for (e.g. a reviewer who reviewed only Alice would otherwise need to see *"summarised across all reviewees"* they have no pairwise connection to). The pairwise flow is small and local; the resolver can be implemented cleanly against each `(reviewer, reviewee)` edge. Cohort-aggregate publication is a separate slice if and when it lands — design rationale in `guide/archive/participant_model_upgrade.md` §3.3.

A corollary: the **Reviewer scope is strictly self-only** in this policy table (§1.1). A future operator-level "Self only / All peers" toggle is sketched as **S13** in `guide/archive/participant_model_upgrade.md` Appendix A — parked, not actively in design, because the same use case is more likely to be served by an Operator- or Observer-published report instead.

---

## 1. Audiences

Three audiences are configurable per instrument. The **operator** is not a configurable audience — the operator always sees everything, identified and per-line. That is the baseline, not a policy.

| Audience | Stored as |
|---|---|
| Peer reviewer (reviewers viewing their own work + peers') | `audience = "peer_reviewer"` |
| Reviewee | `audience = "reviewee"` |
| Observer | `audience = "observer"` |

### 1.1 Audience scope

The audience name implies a **scope rule** the resolver applies in addition to the policy lookup. Scope is intrinsic to the audience identity; the schema does not store it.

| Audience | Scope of "responses they may see" |
|---|---|
| Peer reviewer | The reviewer's **own** submitted responses on this instrument — **never** responses keyed in by another reviewer. The schema name `peer_reviewer` is historical; the policy governs a reviewer viewing their own work post-submit / across pages of the review. |
| Reviewee | Responses **about this reviewee** — or about a group this reviewee is a member of, for group-scoped instruments. Never about another reviewee or another group. |
| Observer | All responses by all reviewers about all reviewees on the session, on instruments this observer is granted (subject to `observer_tag`). Observers are the only audience whose grant is cross-cohort. |

---

## 2. Form axes (what they see)

Two orthogonal columns on `instrument_view_policies` encode the form:

| Column | Values |
|---|---|
| `granularity` | `row` (each reviewer's response shown as its own line) / `aggregated` (summarised across reviewers) |
| `identification` | `identified` (reviewer name shown) / `deidentified` (reviewer name hidden) |

Of the four combinations, three are coherent for participant audiences and one is reserved as incoherent:

| Operator-facing mode | granularity | identification | Notes |
|---|---|---|---|
| **Raw** | `row` | `identified` | Each reviewer's response, attributed. |
| **Anonymized** | `row` | `deidentified` | Each reviewer's response, attribution stripped. |
| **Summarized** | `aggregated` | `deidentified` | Per-data-type aggregate stats; no individual rows. |
| *(reserved)* | `aggregated` | `identified` | Incoherent — "averaging Alice" isn't a thing. The service rejects this combination. |

### 2.1 Per-data-type "Summarized" semantics

"Summarized" needs a per-data-type interpretation:

| Data type | Summarized rendering |
|---|---|
| Integer / Decimal | Average, Median, Min, Max, (based on N responses). Em-dash placeholders at zero responses. |
| List (enum) | Per-choice frequency with percentage, e.g. `A: 2 (33.3%)`. Every declared option surfaces including zeros. |
| String (free-text) | Total length (characters) + Average length (characters), (based on N responses). Em-dash placeholders at zero responses. Also the fallback for unrecognised data types. |

The policy row carries `aggregated` regardless of data type. The per-type rendering lives in `app/web/views/_reviewee_results.py::summarize_field` (for the reviewee surface and the observer collation stats rows) and the corresponding template branches in `reviewer/results.html` + `reviewer/_collation_field_cell.html`. The Reviewee / Observer surfaces present the same per-type aggregate shapes.

### 2.2 Peer reviewer special case

The peer-reviewer audience is constrained per window:

| Window | Allowed modes |
|---|---|
| Session ongoing (`while_ongoing`) | **Raw only** — the baseline self-view-during-session guarantee. The editor renders this cell as a static "Raw responses" pill; the operator cannot turn it off. |
| Responses released (`after_release`) | `None` (off) / **Raw** / **Anonymized summaries** (`summarized`). The reviewer either sees nothing, their own raw submissions read-only (no recall / resubmit), or an Anonymized summary aggregating across the reviewees they reviewed on this instrument. |

`Anonymized` (row + deidentified) is **not** offered for peer reviewers — anonymising one's own work against oneself is incoherent. `Summarized` (aggregated + deidentified) is meaningful because a reviewer who reviewed multiple reviewees has a multi-row fan-out of their own responses, which the summary aggregates. The scope rule (§1.1) still holds: the reviewer's grant covers only responses they themselves keyed in.

---

## 3. Window axis (when they see)

One nullable column on `instrument_view_policies` encodes the window:

| `visible_when` | Window |
|---|---|
| `while_ongoing` | `[sessions.activated_at, sessions.deadline)`. The session-lifetime window. |
| `after_release` | `[sessions.responses_release_at, sessions.responses_release_until)`. The Release-responses window authored on Session Edit Details / Create New Session (W14 + S12). Operator-explicit Release-now / Stop-release buttons (forthcoming) write the same columns. |
| `throughout` | Union of `while_ongoing` and `after_release` — viewable in either window. Useful when the operator wants results visible during the review *and* after release without authoring two grants. |
| `always` | **Reserved.** Today this value is only meaningful for the operator (who is not a row in this table). The column accepts it for forward-compatibility. |

### 3.1 Per-audience valid `visible_when` values

| Audience | UI cycle | Stored values |
|---|---|---|
| Peer reviewer | `while_ongoing` ⇄ `throughout` (2-step toggle). | `while_ongoing` is the default. `after_release` and `always` are not exposed: a reviewer reading their own work after release is well-served by `throughout`. |
| Reviewee | `while_ongoing` → `after_release` → `throughout` (3-step cycle). | All three are valid. Default: `after_release`. |
| Observer | `while_ongoing` accepts only `None` (off) or `summarized` (Anonymized summaries). Raw / Anonymized rows are gated on `after_release` — per-row downloads during a live session carry an unfinished-data risk that the summary view dodges. `after_release` accepts all three modes + off. | `None` / `summarized` for `while_ongoing`; all four for `after_release`. Default: `after_release`. |

### 3.2 Anchor-null inertness

The `after_release` and `throughout` windows depend on `responses_release_at`. When the anchor is `NULL`, the §8.2.2 anchor-null rule applies — the after-release half is treated as "no scheduled fire". Per the view-time predicate:

> *Release window is open* ⇔ `responses_release_at IS NOT NULL` AND `now() ≥ responses_release_at` AND (`responses_release_until IS NULL` OR `now() < responses_release_until`).

A policy with `visible_when = "after_release"` and no anchor is **inert** — the resolver returns "not viewable" until the operator sets the anchor. Saving the policy without an anchor is allowed and harmless.

### 3.3 Archive overrides

When `sessions.status = "archived"`, the resolver treats every per-window pair as `(NULL, NULL)` ≡ off for every non-operator audience regardless of window state. No schema change — pure view-time gate. Mirrors how archive retires a session out of reviewer reach today.

---

## 4. Storage shape

```
instrument_view_policies
  id              PK
  instrument_id   FK -> instruments.id    (indexed, NOT NULL)
  audience        String(16)  NOT NULL    'reviewee' | 'peer_reviewer' | 'observer'

  -- Per-window mode pairs. NULL in both members ≡ "off in this
  -- window". (aggregated, identified) is the reserved-incoherent
  -- combo and rejected by the service.
  while_ongoing_granularity     String(16)  NULL  'row' | 'aggregated' | NULL
  while_ongoing_identification  String(16)  NULL  'identified' | 'deidentified' | NULL
  after_release_granularity     String(16)  NULL  'row' | 'aggregated' | NULL
  after_release_identification  String(16)  NULL  'identified' | 'deidentified' | NULL

  observer_tag    String        NULL      (observer audience only — restrict the
                                           grant to observers carrying this tag;
                                           NULL = all observers on the session)
  created_at      DateTime(tz) NOT NULL
  updated_at      DateTime(tz) NOT NULL
  UNIQUE (instrument_id, audience)
```

- One row per (instrument, audience). Upserts cover both the create and update cases.
- Rows with both windows off (all four pair columns NULL) persist so the operator's `observer_tag` choice survives a toggle-everything-off / toggle-back-on cycle.
- `observer_tag` only carries meaning when `audience = "observer"`; the service layer enforces NULL otherwise (no DB CHECK constraint).
- The legacy single-mode encoding (`enabled` / `granularity` / `identification` / `visible_when`) shipped with Phase 1 and retired in the S14 contract step (Alembic `b8f4c2a91d35`) once the per-window pairs carried the operator's intent end-to-end.

### 4.1 Default state

Default on instrument create: no rows. Resolver treats a missing row as "off in both windows" — instrument is invisible to that audience. The operator opts each audience in deliberately on the Band 3 editor.

---

## 5. Audit

Every write emits `instrument.view_policy_set` per the canonical envelope (changes + refs). One event per (instrument, audience) row touched in a single save:

- `payload = audit.changes({field: [old, new], ...})` — every field that actually changed.
- `refs = {"instrument_id": …, "policy_id": …}`.
- `session = …`.

A no-op save (operator clicked Save with no changes) emits nothing.

---

## 6. Where this is wired

| Slice | What | Status |
|---|---|---|
| S2 (PR #1678) | `instrument_view_policies` table | ✓ shipped |
| S12 (PR #1724) | `visible_when` column (retired in S14 contract) | ✓ shipped, then retired |
| W15 — Band 3 editor (persistence half) | `app/services/visibility_policies.py` (mode encoder / decoder + per-audience vocabulary + `upsert_policy` + `upsert_many`); Band 3 template renders the chip table with hidden inputs that hitch on the card's main Save form (`form="dfsave-<id>"` → `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save` reads the visibility fields and calls `upsert_many`); `build_instruments_context` carries `band3_visibility_by_instrument`. The standalone `/view-policy` route + "Save visibility" submit retired once the card-level Save took over. | ✓ shipped |
| Band 2 preview of the reviewer-surface visibility card | `build_instruments_context` carries `band2_preview_visibility_rows_by_instrument` (same shape as the reviewer surface's `visibility_rows`); the Band 2 intro grid renders the read-only "Who can see what you wrote (other than admin)" card alongside the description card so the operator can preview the reviewer's view from the operator surface. | ✓ shipped |
| S14 — per-window mode pairs + Band 3 column-axis swap | Alembic `a7e3b1d92c64` (expand) adds the four pair columns; PR #1730 swaps service + route + view + template to read / write the pair columns and rebuilds Band 3 as 3 audiences × 2 windows of mode chips; Alembic `b8f4c2a91d35` (contract) drops the legacy `enabled` / `granularity` / `identification` / `visible_when` quadruple. | ✓ shipped |
| Reviewer-surface transparency card | `views.build_reviewer_visibility_rows` (in `app/web/views/_instruments.py`) + a half-width read-only "Who can see what you wrote" card in column 2 of each per-instrument intro grid on `review_surface.html`. Renders three rows (You / Reviewees / Observers) × two windows with the persisted mode labels (Raw responses / Anonymized responses / Summarized responses / —). | ✓ shipped |
| W7 — Resolver | `app/services/visibility_policies.py::resolve_mode` reads policies + applies the scope rules; consumed by the W16 reviewee surface. | ✓ shipped |
| W16 — Reviewee `/results` body | `build_reviewee_results_context` renders raw / anonymized / summarized modes. W19 Acknowledge card also live (PR #1750). | ✓ shipped |
| W17 — Observer `/collation` body | Renders the policy-permitted content. | ✘ pending |

---

## Cross-references

- `guide/archive/participant_model_upgrade.md` §3.3 — design rationale + the audience-scope table.
- `guide/archive/participant_model_upgrade.md` Appendix A — implementation-phase identifier glossary (S2 / S12 / W7 / W15 / W16 / W17).
- `spec/participant_model.md` — cross-cutting participant-model contract; release-window columns.
- `spec/instruments.md` — the per-instrument card layout; Band 3 visibility editor sits here.
- `spec/lifecycle.md` — schedule columns (`responses_release_at` / `responses_release_until`), §8.2.2 anchor-null, §8.2.7 save-time ordering.
