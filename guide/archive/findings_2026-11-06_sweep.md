# Findings — the window sweep (2026-11-06)

**Found by:** the four `spec-writer` verify reads of
`guide/sweep_2026-11-06_window.md` · **Read at:** `78118652` · **Open:**
none; every row fixed in the PR that archived this file, N1 recorded.

What the sweep found and left standing; the fixes strike their rows with
their PR, or mark them declined with the reason. Retire the file to
`guide/archive/` when no row is open. **W** is write or deepen, **U** update
in place, **N** a note. Every row is the doc behind the code; none needs a
ruling, and where a choice of wording was the reader's, the row says what
the fix does.

## Write or deepen

- ~~**W1**~~ **Done** — **`docs/security_posture.md` says nothing of the outbound mail
  surface:** operator-initiated mail through the delegated Graph token,
  redirects refused (`cordware/graph.py:128`), no retry on a 5xx.
  `cordware/spec/identity.md` "Sending mail" owns it; a short pointer
  paragraph does.

## Update in place

- ~~**U1**~~ **Done** — **`spec/csv_contracts.md:619` (§3.2b)**: `save_observers`'s
  signature misses `directory`, `append`, `merge` and `columns`
  (`app/services/csv_imports/_saving.py:222-234`); its siblings at :357 and
  :572 were updated.
- ~~**U2**~~ **Done** — **`spec/ui_elements.md:930`**: the `.is-equal-height` sentence sits
  in a third cell of the two-column §10 table, with no closing pipe. The
  content is right (`base.html:1449-1454`); fold it into the Notes cell.
- ~~**U3**~~ **Done** — **`spec/architecture.md:1096`**: the `reason` slot's cascade close
  names `"deadline"` only; with no End it is `"release"`
  (`session_lifecycle.py`, `by_end`), as :665-667 already say.
- ~~**U4**~~ **Done** — **`rrw_design_rationale.md:197` (§7)**: "email is recorded, not
  sent". Per-row Send and Send reminder go from the operator's mailbox
  through delegated Graph since 14F; bulk and scheduled sends wait on 14G.
- ~~**U5**~~ **Done** — **`docs/known_limitations.md:42-48`**: "Email not yet wired … Sending
  is Segment 14B". As U4. Its next bullet, "Scheduled sends wait for an
  operator page view", predates 14E's clock (found while fixing U5).
- ~~**U6**~~ **Done** — **`spec/rrw_functional_spec.md` §9.14 (1200-1215)**: the sys-admin
  surface lists Accounts, Sessions Diagnostics and the per-session viewers,
  not System Status (22G; `spec/operator_ui_concept.md` describes it).
- ~~**U7**~~ **Done** — **`docs/deployment.md:33`**: the delegated token serves "the
  directory features"; it also sends mail now. The scope it needs is named
  where the deployment is configured, not here.
- ~~**U8**~~ **Done** — **`spec/csv_contracts.md:1243` (§5a)**: the sample rosters'
  `example.edu` addresses keep anything from reaching a person "once sending
  is switched on"; per-row sending is on. The reason stands; the tense does
  not.
- ~~**U9**~~ **Done** — **`spec/csv_contracts.md:897`**: "past-deadline reminders are
  skipped"; the skip reasons are `not_ready`, `no_invitations` and
  `outside_response_window` (`scheduled_events/_reminders.py:210-216`).
- ~~**U10**~~ **Done** — **`spec/visual_style_rrw.md:509`**: the example closed copy ("no
  longer accepting responses. The deadline passed on [date]") is not what a
  reviewer sees (`app/web/views/_refused_write.py:78-79`); quote the shipped
  copy, or point at `spec/reviewer-surface.md`'s refusal table.
- ~~**U11**~~ **Done** — **`spec/extract_data.md` (238-248, 461-477)**: the lenses filter
  `Assignment.include IS TRUE`, and the Timestamps columns, deliberately
  session-wide, do not (`entity_metadata_extract.py:587-615`). One clause
  says so.

- ~~**U12**~~ **Done** — **`cordware/spec/identity.md:310-311`**: `FakeMailer` "logs the
  recipient and subject"; since N2 (#3674) it logs a recipient count only
  (`cordware/graph.py:627-629`). Found while writing W1.

## Notes

- **N1 — Provenance tags in specs** ("(findings L3)", "(author,
  2026-11-06)"): new ones in `csv_contracts.md`, `lifecycle.md`,
  `ui_elements.md`, `extract_data.md`, `setup_pages.md`. The pattern is
  long-standing across `spec/`; a sweep of it would be a campaign the
  conventions do not ask for. Recorded, not acted on.
