# Sweep — spec/ + docs/ (2026-09-05)

**Swept:** 2026-09-05 · **Scope:** `spec/` + `docs/` + root practice docs
(64 files) · **Previous sweep:** `guide/archive/spec_sweep_18Aug.md` and
`guide/archive/docs_sweep_19Aug.md` (and, for carry-forward,
`guide/archive/spec_sweep_11may.md`) · **Trigger:** not due — 18 days of
56, 151 merges of 500. Run anyway as the first sweep under
`guide/sweep_template.md`, to validate the template (Segment 19A Item 2
PR 3).

**Deliberately partial.** This sweep reconciles the three prior sweeps and
reads the files staleness flagged. It does not read the other 51. Section
7 says which.

## 0. Carried forward

The reason this section exists, demonstrated on its own first run: of the
six notes `spec_sweep_18Aug.md` filed as "minor / cosmetic
(non-actionable)" eighteen days ago, **four are still true, one was
wrong, and one has become worse than filed.** None had been re-read until
now. The mechanical dead-reference pass below rediscovered one of them
(C3) from scratch, which is what carrying findings forward is meant to
save.

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| Tier 1 #4 — Email Template editor has no spec | 2026-05-11 | 117 d | **done** | `spec/email_template_editor.md`, #2101 |
| Tier 1 #5 — Permissions has no spec | 2026-05-11 | 117 d | **done** | `spec/permissions.md`, #2101 |
| Tier 2 #6 — Relationships page could be standalone | 2026-05-11 | 117 d | **declined** | Still a section in `setup_pages.md`; the original condition was "if pilot feedback drives it", and there has been no pilot |
| Tier 2 #7 — Assignments page could be standalone | 2026-05-11 | 117 d | **done** | `spec/assignments.md` covers the engine *and* the page (written 2026-05-26) |
| Tier 2 #8 — Operator Settings page could be standalone | 2026-05-11 | 117 d | **declined** | Now covered across `settings_inventory.md` §1 + `timezone_display.md` (the Date & time card). Adequate; revisit if the page grows |
| Tier 3 #9 — Edit Session page | 2026-05-11 | 117 d | **moot** | The page was retired in 18R; there is nothing left to spec |
| Tier 3 #10–#12 — new-session form, drill-in pages, outbox | 2026-05-11 | 117 d | **declined** | Deferred on the same reasoning as when filed; `session_outbox.html` remains explicitly out of the operator taxonomy |
| C1 — `preview_hub.md` dates the `/preview` 308 repoint anachronistically | 2026-08-18 | 18 d | **re-diagnosed** | See finding 2.1 — the note had it backwards |
| C2 — `lifecycle.md` §1 state diagram omits `expired` | 2026-08-18 | 18 d | **still open** | See 2.2 |
| C3 — `assignments.md` names `app/services/assignments.py` (now a package) | 2026-08-18 | 18 d | **still open** | See 2.3; independently rediscovered by the dead-reference pass |
| C4 — `visual_style_general.md` green-marker is one shade off | 2026-08-18 | 18 d | **superseded** | Worse than filed: the token is not a different shade, it no longer exists. See 2.4 |
| C5 — `operator_ui_concept.md` user card omits the admin suffix | 2026-08-18 | 18 d | **still open** | See 2.5 |
| C6 — `domain_assumptions.md` "1–6 Instruments" implies a cap | 2026-08-18 | 18 d | **still open** | See 2.6 |

`spec_sweep_18Aug.md` §A and §B and `docs_sweep_19Aug.md`'s four buckets
were all executed at the time; nothing carried from them beyond §C above.

## 1. Write or deepen

Nothing. Every routing module has a governing spec as of #2109, and no
surface read in this sweep was found undocumented. The 2026-05-11 sweep's
two Tier-1 gaps were the last of this kind and closed on 2026-09-05.

This is the disposition that produced the 117-day gap, so its emptiness is
worth stating rather than omitting.

## 2. Update in place

**2.1 — `app/web/routes_operator/_preview_surface.py` misattributes its
segment (not `spec/preview_hub.md`).** The 2026-08-18 note assumed the
code was right and the spec anachronistic. It is the other way round: the
module docstring opens "Operator-side full preview of the reviewer surface
(Segment 18Q)", but git shows the file was created 2026-05-28, and Segment
18Q is *Blob storage* — an unrelated, no-code deferral segment from August.
`preview_hub.md`'s 2026-05-28 dating is correct throughout. Fix the
docstring; leave the spec alone.

**2.2 — `spec/lifecycle.md` §1 state diagram omits two of five states.**
The ASCII art shows `draft ⇄ validated ⇄ ready` only; `expired` and
`archived` are absent, though the state table and §2.7 document both. Left
intact in August "to avoid mangling"; it is the first thing a reader of
the lifecycle spec sees, so the mangling risk is worth taking.

**2.3 — three `app/services/assignments.py` references are stale**, in
`spec/assignments.md`, `spec/lifecycle.md` and `spec/setup_pages.md`. The
18O split made it the package `app/services/assignments/`. Function
references still resolve through the package `__init__`, so nothing is
broken — but the path is now a lie, and the same is true of
`app/services/session_config_io.py` (`quick_setup_card_spec.md`) and
`app/services/scheduled_events.py` (`settings_inventory.md`).

**2.4 — `spec/visual_style_general.md` predates the 19C token reorg.** It
names the `accent-*` vocabulary — `accent-blue`, `accent-amber`,
`accent-green-marker` and a dozen more — and `base.html` defines none of
them; the Item 6 semantic-token work (#2047 → #2062, 2026-08-23) renamed
the primitive families. The doc was last edited **2026-08-20**, three days
before. `visual_style_rrw.md` and `color_tokens.md` were both refreshed on
2026-09-04 and are current.

*Judgement required, not a mechanical fix.* This doc is deliberately the
**portable** design system, so generic names may be intentional. But
`spec/README.md` sets the reading order general → rrw → `ui_elements.md`,
and a reader following it meets a vocabulary that no longer exists
downstream. Either repoint the names or state in the doc that its token
names are illustrative and `color_tokens.md` is authoritative.

**2.5 — `spec/operator_ui_concept.md` understates the shipped user card.**
Line 211 documents "Signed in as {user name}" plus a sign-out control.
`base.html` also renders ` (super admin)` / ` (sys admin)`, which
`audience_and_identity_model.md` §4 documents. The spec is not wrong, it
is incomplete about a role-visible affordance.

**2.6 — `spec/domain_assumptions.md` implies an instrument cap.** "1-6
Instruments and their associated Response Forms" reads as a bound; there
is none in code, and `rrw_functional_spec.md` says "any number". Either
say "typically 1–6" or drop the range.

**2.7 — `docs/security_posture.md` points at a retired file.** It
references `docs/authentication.md`, which the 2026-08-19 docs sweep
folded into `security_posture.md` itself and deleted. A doc pointing at
the file it absorbed is the sharpest kind of dead reference.

**2.8 — `spec/visual_style_rrw.md` names two specs that do not exist**
(`spec/instruments_setup_spec.md`, `spec/response_form_component_spec.md`),
both superseded in the 2026-05-26 consolidation into `spec/instruments.md`.

## 3. Consolidate

Nothing. The 2026-08-19 docs sweep did the consolidation work
(`cli_setup_notes` → `cli_setup`, `authentication` → `security_posture`,
`codespace_setup` → `local_setup` §9) and no new overlap has appeared in
the eighteen days since.

## 4. Retire

Nothing. `spec/blob_storage.md` is the only candidate a reader might
propose — it is a stub for infrastructure that does not exist and its
reference to `app/services/blob_store.py` is to a module never written —
but it is deliberate, labelled "**Stub / not built**", and records how
each need is met today. Keeping it is the decision; noting it here is so
the next sweep does not re-propose it.

## 5. Move

Nothing.

## 6. Read, no action

Opened and compared against code; found current:

- `spec/email_infra_options.md` (117 d stale) — its Option A/B/C/D framing
  and the `SmtpEmailTransport` / typed-stub status still match
  `app/services/email_send.py`. Stale by date, correct in substance.
- `spec/timezone_display.md` (111 d) — the lobby and archived-page
  Timezone columns and the resolver order still hold.
- `spec/role_navigator.md` (95 d) — flagged by the retired-`/reviewer/`
  scan, **rejected as a false positive**: the two hits are the template
  directory `app/web/templates/reviewer/`, which is genuinely still named
  that. The URL prefix remodel (#1668 / #1669) renamed routes, not
  template folders.
- `spec/color_tokens.md`, `spec/visual_style_rrw.md` — refreshed
  2026-09-04; 200 of 203 named tokens resolve in `base.html`, the three
  that do not are named as retired.
- `spec/assignments.md` — the Assignments *page* is covered here (closing
  carried Tier 2 #7); only the path strings in 2.3 are stale.

## 7. Not read

**51 of 64 in-scope files.** They were covered only by the four mechanical
passes (staleness, dropped commitments, orphan specs, dead references),
which see broken references and absent specs but cannot see a paragraph
that quietly stopped being true. Those passes returned nothing further on
these files; that is weaker than having read them, and this sweep does not
claim otherwise.

The next sweep should start here rather than re-running the same
mechanical passes over the files this one already opened.

## Findings ledger

Kept current as the findings close, so the **next** sweep reads this table
as its §0 carry-forward input rather than re-deriving eight findings. This
makes a dated snapshot a living file; that cost was accepted deliberately
(19C Item 7, `## Status`).

| # | Finding | Status | Closed by |
|---|---|---|---|
| 2.1 | `_preview_surface.py` misattributes Segment 18Q | **done** | 19C Item 7 PR 1 — now attributes the 2026-05-28 follow-on to 11F (PRs #1530 / #1531) |
| 2.2 | `lifecycle.md` §1 diagram shows 3 of 5 states | **done** | Item 7 PR 2 — all five states, with the archive edge from any non-archived state |
| 2.3 | five `app/services/*.py` paths are now packages | **done** | 19C Item 7 PR 1 — five specs renamed; `docs/status.md` left as dated history |
| 2.4 | `visual_style_general.md` names a retired `accent-*` vocabulary | **done** | Item 7 PR 3 — names declared the portable system's *role* names, with `spec/color_tokens.md` stated as authoritative for RRW's shipped identifiers and `base.html` / the customizer as where values change |
| 2.5 | `operator_ui_concept.md` understates the user card | **done** | Item 7 PR 2 — the `(super admin)` / `(sys admin)` suffix, super winning when both apply |
| 2.6 | `domain_assumptions.md` implies an instrument cap | **done** | Item 7 PR 2 — 1-6 restated as typical usage, not a bound |
| 2.7 | `docs/security_posture.md` points at a retired file | **declined** | Not drift: the reference is a dated provenance note ("formerly …, retired 2026-08-19"), not a live pointer. Filed by the mechanical pass, which sees that a path is absent but not why it is named. Manifest bullet waived with this reason |
| 2.8 | `visual_style_rrw.md` names two specs that do not exist | **re-diagnosed**, open | Both were marked "(forthcoming)" and have **never existed** (zero commits, ever) — unwritten aspirations, not specs "consolidated away in 2026-05" as filed here. Repointing them is a content judgement; moved to Item 7 PR 2. **Done there** — repointed to `spec/instruments.md` and `spec/reviewer-surface.md`, with their content lists kept as open design notes rather than promises, since neither spec covers them yet |

**All eight findings are closed: seven actioned, one declined.**

**Two of this sweep's own eight findings did not survive re-verification
at build.** Both came from the dead-reference pass, and both failed the
same way: the scan can tell that a path is absent, not why the document
names it. The sweep's §6 rejected one candidate on exactly that ground and
should have caught these two as well. The next sweep's §0 should treat a
mechanical hit as a lead, not a finding.

## Headline numbers

| | |
|---|---|
| In scope | 64 (38 `spec/`, 17 `docs/`, 9 root) |
| Read | 13 |
| Findings | 8 (write 0 / update 8 / consolidate 0 / retire 0 / move 0) |
| Carried in / closed / still open | 13 / 6 / 7 |
| False positives rejected | 1 (`role_navigator.md`) |
| Untouched since the previous sweep | 13 of 64; stalest 117 d |

**Two observations for the cadence itself.** First, the four
"non-actionable" notes from August that were still true are the argument
for section 0 in one line — filing a finding without a mechanism to
re-read it is the same as not filing it. Second, this sweep found **no**
write-or-deepen work, which is the first time that has been true; the
coverage gate (#2109) now holds that ground, and the sweep's remaining
value is the eight update-in-place findings no constant could have named.
