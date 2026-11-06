# Findings — codebase assessment (2026-11-06)

**Found by:** the three reads run beside
`guide/codebase_assessment_06nov.md`: a spec-vs-code audit, a defect read
of the window's `app/`, `cordware/` and `alembic/` changes with scratch
tests, and a read of `cordware/`, `residentialapps/` and `utilityapps/`
with their suites and a route fuzz · **Read at:** `c912ae53` (#3657; the
reads ran on its pre-merge tree `c5d03d49`, identical) · **Open:** all but M1, L1, L3, N9, D1–D5, D7 and D12 (D8 half).

The checklist the fixes work through. **Nothing was edited by the
reads**, and their scratch tests were not kept: a fix PR writes its own
test. Strike a row when it is done, with the PR that did it, or mark it
declined with the reason. Retire the file to `guide/archive/` when no row
is open.

**Ids:** **M** and **L** are defects, medium and low, as the assessment's
§6 numbers them · **D** is spec drift, as its §3 does · **N** is a gap or
note, not a defect. **Decides:** *code* means the code is wrong against a
spec that is right; *author* means a choice between fixing the code and
changing the contract; *spec* means the spec is wrong. Line numbers are at
`c912ae53`.

**Related, already filed:** 14F's collected follow-ups
(`guide/archive/segment_14F_manual_email.md`, "Follow-ups, collected"): per-row
Send and Regenerate in `validated` (bears on D3), a reason on a disabled
row button, and `Reviewer.last_opened_at`'s comment.

## 1. High

None.

## 2. Medium

- ~~**M1 — A failed per-row Send or Remind still reads as sent, and the
  row loses its Send.**~~ **Done 2026-11-06**: `invitations.restore_after_failed_send` puts back, under the session lock, the stamps the refused send wrote and still holding, and writes `invitation.send_reverted` (`tests/integration/test_bulk_send_off.py`). Was: `invitations.send_invitation`
  (`app/services/invitations.py:395-399`) stamps the invitation `sent`
  and `sent_at` and commits before `_send_queued_row`
  (`app/web/routes_operator/_operations.py:362-391`) dispatches; on a
  refused send (Graph 503, 401, 403, a second 429, a network error) the
  outbox row reads `failed` but the invitation stays `sent`. The stepper
  moves on (`has_sent_invitations`), "Invitations sent" counts it,
  "Pending" drops it, and the row offers Send reminder and Regenerate but
  no Send (`session_invitations.html:376` shows Send only for `pending`).
  `send_reminder` does the same with `last_reminder_at`
  (`invitations.py:850`). Contradicts the 14F plan's "leaves the failed
  rows to retry". **Live on Azure since 2026-11-05.** *CONFIRMED by a
  scratch test* (a mailer raising `GraphError("server", 503)`: status
  `sent`, Send button gone). Code: stamp only on `sent`, or revert on
  `failed`.

## 3. Low

- ~~**L1 — A double-submitted per-row Send mails a dead link first.**~~ **Done 2026-11-06**: `send_one_invitation` refuses, under the session lock, an invitation no longer `pending` (`?email=already_sent`). Was:
  `invitations_send_one` (`_operations.py:878-934`) deliberately does not
  check `pending`, and `send_invitation` mints a new token on every call
  (`invitations.py:375-376`); each POST now really emails, so a double
  click sends two messages and the first link no longer resolves. A slow
  Graph call (20 s, plus up to 30 s on a 429) widens the window.
  *CONFIRMED* (two POSTs, two messages, `lookup_invitation_by_token` on
  the first is `None`). Code: refuse, or treat as Remind, an invitation no
  longer `pending`, decided under the session lock.
- **L2 — `RRW_BULK_SEND=true` records invitations as sent and emails
  nobody.** Send all and Remind incomplete pass the flag gate
  (`_operations.py:791-819`, `1187-1210`) and call
  `send_all_invitations` / `send_reminders_to_incomplete`
  (`invitations.py:425-453`), which queue and stamp but never dispatch:
  F12's "recorded, not delivered" state, behind a flag
  `docs/deployment.md:74` says makes the buttons "email every reviewer at
  once". Ships off. *CONFIRMED by trace.* Author: wire dispatch, keep the
  routes refusing until 14G whatever the flag, or say flag-on is
  record-only.
- ~~**L3 — A schedule the form accepts can never activate.**~~ **Done 2026-11-06, strict (author)**: `validate_schedule_ordering` refuses End ≤ Start and, with no End, Release-from ≤ Start; Session Home's save and the Settings CSV import now check the no-End pair too (the cold read found both skipped it); the client check matches; the specs say Start < End. Was:
  `validate_schedule_ordering` (`scheduled_events/_release.py:143-169`)
  and `spec/lifecycle.md` §8.2.7 allow Start == End (and, with no End,
  Release-from == Start); Validate's `session.end_passed`
  (`validation/_rosters.py:121-133`) errors when Start ≥ the end.
  *CONFIRMED by trace.* Author: make the ordering strict, or relax the
  rule.
- **L4 — End's close writes no `session.deadline_reached` when the
  instruments were already shut.** The already-shut branch of
  `observe_deadline` (`session_lifecycle.py:1210-1219`) calls
  `_expire_at_end(closed=0)` without the event, even with a real End;
  `spec/reviewer-surface.md:1131-1133` and `spec/lifecycle.md` §4
  (502-506) read as writing it there too. *CONFIRMED by trace.* Author:
  write it, or say it is skipped.

## 4. Spec drift

- ~~**D1 — The contract still says no email leaves the app**~~ **Done at 14F's close (2026-11-06)**, by its `spec-writer` pass across the named specs and `cordware/spec/identity.md`. Was: (high in the
  audit; it is 14F's close, unfinished). False now:
  `spec/rrw_functional_spec.md` §11.6 (1468-1478) and §9.13 (1194-1198,
  the Email settings card "planned"); `spec/architecture.md:716-718`;
  `spec/email_template_editor.md` §7 first row;
  `spec/operations_pages.md:168-177` (requires the retired "no email is
  delivered" note, now asserted absent by
  `tests/integration/test_page_guidance.py:486`), `:61`, `:404-412`;
  `spec/settings_inventory.md` §1 (32-35, 70-72);
  `spec/email_infra_options.md:51-58` (delegated Graph out of scope),
  `:120-136` (`GraphEmailTransport` a "typed stub"), `:300-303` (Reply-To
  "not built"); `spec/operator_ui_concept.md:405`;
  `cordware/spec/identity.md:252-257` (Graph "directory lookups only": no
  `/me/sendMail`, no-retry on 5xx, one 429 wait, `saveToSentItems`,
  `FakeMailer`). Spec, at 14F's close; **its Doc impact lacks**
  `rrw_functional_spec.md`, `architecture.md` and
  `operator_ui_concept.md`.
- ~~**D2 — Pages say things the app no longer does.**~~ **Done at 14F's close (2026-11-06)**: the Guide (launch controls, Start/End, *Give reviewers access*, the demo note), the outbox note, the composer's From (the operator sending), the drill-in's "Sent:", and Workflow States 5 and 6. Was: `guide.html:894`
  ("the email function is not implemented yet"), `:782-785` (Send invites
  "stamps … no mail leaves the app yet"), `:847-849` ("the app will
  prepare and activate the session at Start": scheduled activation never
  prepares, `scheduled_events/_activation.py:91-99`; predates the window);
  `partials/_sys_admin_outbox.html:11` ("No transport sends email yet");
  `session_setupinvite.html:91` ("From: … set when email sending is
  switched on"); `session_invitations_reviewer_detail.html:73-79` ("Send
  recorded … until email sending is switched on");
  `partials/next_action_card.html:140` (State 5 "Send them ahead of
  Activation", impossible with bulk off and per-row Send `ready`-only).
  Code (copy); State 5 rides on 14F follow-up 1.
- ~~**D3 — Before activation there is no in-app send, and the specs do not
  say so.**~~ **Done**: per-row Send works once prepared (14F follow-up 1), and `spec/operations_pages.md` and `spec/workflow_card.md` state it and the bulk-off state. Was: `spec/operations_pages.md:357-358` still names bulk Send
  invites "the one way to send before activation"; `spec/workflow_card.md`
  (:322, :635-680) has no disabled-behind-`RRW_BULK_SEND` state, title or
  bulk-off line (`next_action_card.html:324,339,428,501-509`). Author: 14F
  follow-up 1 changes the answer; `workflow_card.md` is not in 14F's Doc
  impact.
- ~~**D4 — `spec/settings_inventory.md` misses the window's stored state.**~~ **Done at 14F's close.** Was:
  §8 lacks `RRW_BULK_SEND`; §1 `preferences` lacks
  `email_save_to_sent_items`, `email_bcc_self`, `email_reply_to_help` (off
  by default) and `operator.email_preference_set`; §5 Reviewer lacks
  `last_opened_at`; §7 URL state lacks Invitations'
  `?email=sent|superseded|failed&kind=…`. Spec; only `last_opened_at` is
  in 14F's Doc impact.
- ~~**D5 — `spec/extract_data.md` has no Timestamps chip**~~ **Done at 14F's close.** Was: (375-420): no
  `?timestamps=1`, no `LastOpened` / `LastSaved` / `LastSubmitted`, and it
  says every chip is default-selected (Timestamps is off). Spec, at 14F's
  close.
- **D6 — `spec/visibility_policy.md` disagrees with itself.** §2.2 (:84)
  says a reviewer reads back their answers "always while the session is
  `ready`"; §3 (:101, rewritten by 14E) and the code
  (`visibility_policies.reviewer_sees_own_responses`, :432) say
  `is_ongoing`. Spec.
- ~~**D7 — `spec/lifecycle.md` §8.3 (1121-1124) claims End keeps a floor~~ **True as written since 14F rung 5a**: the reminder-offset checks run whatever the flag. Was:
  through reminder offsets**; with `RRW_SCHEDULED_SEND` off (the default)
  the offset checks are skipped (`_session_home.py:317-330`,
  `scheduled_events/__init__.py:184`) and End has none. Spec: qualify the
  sentence.
- **D8 — Reply-To shipped differently from its spec.** *Spec half done at 14F's close; the code half stays open: `SmtpEmailTransport` ignores `reply_to`, unflagged (SMTP is not the transport in use).*
  `spec/email_infra_options.md:295-296`: operator's address by default,
  per session. Shipped: a per-operator toggle naming the session's Help
  contact when it is an address (`email_dispatch.send_options_for`,
  78-87). `SmtpEmailTransport._build_message` (`email_send.py:181-199`)
  ignores `reply_to`, unflagged (only `save_to_sent_items` is). Spec, with
  D1.
- **D9 — Two layout modifiers are undocumented.** `spec/ui_elements.md`
  §10 (:930) defines `.bottom-grid` as start-aligned, natural height; the
  Invitations pair uses `.bottom-grid.is-equal-height` and Extract data's
  top grid `.extract-data-grid.is-row-aligned` (`base.html`, #3655,
  #3657). Spec.
- **D10 — `CONTRIBUTING.md` (15-16, 65) omits `ruff format --check .`**,
  which 22H made a CI gate (`ci.yml:91,167`) and `CLAUDE.md` lists. Spec.
- **D11 — `spec/rrw_functional_spec.md` keeps pre-14E wording:** "before
  its deadline" (:246, :708) where 14E means the review's end; §8.2
  (851-853) names an auto-archive offset with no consumer and "the lazy
  deadline-closure observer" (now the clock plus requests). Spec.
- ~~**D12 — The 14F plan says a send under fake auth refuses**~~ **Done at 14F's close**: the Semantics line is struck and annotated. Was: under fake
  auth `mailer_for` returns `FakeMailer` (`cordware/graph.py:621-627`) and
  the row reads `sent`. Plan, at 14F's close.

## 5. Noted gaps

- **N1 — No test that a mail failure's log line leaves out the token**
  (`cordware/tests/test_graph_mail.py`; the directory side has
  `test_graph.py:146`), and none drives the mailer's POST against a
  redirect. The shared `_NoRedirect` opener covers POST; only GET is
  proven.
- **N2 — `FakeMailer` logs recipient and subject at INFO**
  (`cordware/graph.py:611-618`), against the module's "never the address"
  stance (local only); and `mailer_for` builds a new one per call, so its
  docstring's "kept on `sent`" is unobservable outside direct
  construction.
- **N3 — A network failure after Graph accepted a message is recorded
  `failed`** (`graph.py:584-585`, by design); a re-send can duplicate.
  The failure copy could say "may have been sent".
- **N4 — A 429 can hold a request worker about 70 s** (20 s timeout, up
  to 30 s `Retry-After`, 20 s again; `graph.py:592-596`), now that per-row
  Send calls the mailer on the request thread.
- **N5 — Suspected, not confirmed** (the defect read): a past End saved on
  a `ready` session closes the live review on the next pass (14E; maybe
  intended); `_release._unstamped` compares `context.release_at` as a
  string where `_fired` compares instants; `observe_release_window` /
  `observe_deadline` can hold the row lock through a page render on a
  no-op; `mark_opened` stamps a pre-Start arrival; the SMTP transport
  sends a blank From (unreachable today).
- **N6 — System Status says "behind" for any schema mismatch**, a
  database ahead of the code included (`views/_system_status.py:109-115`;
  `spec/operator_ui_concept.md:157` names current, behind, none).
- **N7 — End's two close events spell `context.deadline` differently**
  (`session_lifecycle.py:1277` raw; `_end_context`, 1128-1135, aware):
  the strings differ on SQLite for the same moment.
- **N8 — The Postgres shards are uneven:** on `main` at `c912ae53`,
  `postgres (integration-b)` ran its tests in 2m54 against
  integration-a's 1m38, the slowest job in CI (the assessment's §2,
  "Test runtime"). Re-split `tests/integration` by time, not by letter.
- ~~**N9**~~ — **Done in #3662**: both tools count a squash commit whose subject ends `(#N)` as a PR (`code_metrics.pr_commits`; `pace_audit.load`), the pace audit marks a squash-merged PR's turn, iteration, commit count and review rounds `None`, says how many PRs were squash-merged, and splits the cycle over merge-committed PRs only (`tests/unit/test_pace_audit.py`, `tests/unit/test_code_metrics_guard.py`). Churn with them counted: 1.2× at `aab086fe`. **The repository's own measurements miss every squash-merged PR.**
  Since #3150 (2026-10-19) PRs reach `main` two ways: by `c912ae53`, 319
  merge commits and 188 squash commits on the first-parent line, and
  89 of this window's 91 PRs squash-merged. `tools/pace_audit.py`
  (`load`, `git log --merges`) and `tools/code_metrics.py`'s churn walk
  (`churn`, the same flags) read merge commits only, so neither sees the
  squash-merged ones, and a squash merge has also dropped the branch
  commits the pace audit times. The churn figure above leaves out almost
  all of this window, and a re-take of `rrw_sdd_in_practice.md` §6.4's
  cadence figures would measure only the merge-committed half (Codex on
  #3659 corrected an earlier "stops at #3149"). Found while re-taking
  that document's figures, not by the
  assessment's reads. Author: count squash commits by their `(#N)`
  subject in both tools, and decide whether the cadence figures are worth
  the PR timeline from the GitHub API, or merge commits back.
