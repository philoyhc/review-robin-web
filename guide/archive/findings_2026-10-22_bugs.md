# Findings — bug sweep (2026-10-22)

**Found by:** seven bug-hunting reads run beside
`guide/codebase_assessment_22oct.md` · **Read at:** `00501f2e` (#3225) ·
**Open:** none of 22 rows (S4, P3 and E4, each found by a fix's cold read, done in #3238); every author row ruled 2026-10-22 (R3, R4,
L1, O2, O3, S1, E2, C1), so each is now a fix.

Like the 2026-10-16 sweep (`guide/archive/findings_2026-10-16_bugs.md`,
all 46 rows done), this one read the code for defects rather than the
specs for drift. Each read took one area, wrote scratch tests against the
in-memory SQLite suite, and reported only what a test reproduced or a
reading of the code made certain. **Nothing in `app/` was edited.** The
scratch tests were deleted; a fix PR writes its own test. Strike a row
when it is done, with the PR that did it, or mark it declined with the
reason.

**Ids** carry the area of the read: **R** responses and participant data
· **L** lifecycle and scheduling · **O** operator pages, extracts and
email · **S** Setup, imports and instruments · **P** permissions and
identity · **E** the assignment engine · **C** the Cordware host and RRW
under `/reviewrobin` (new this sweep). Ids restart per sweep: R1 here is
not the 2026-10-16 R1. **Decides:** *code* means the code is wrong
against a spec that is right; *author* means a choice between fixing the
code and changing the contract; *spec* means the spec is wrong. Line
numbers are at `00501f2e`. Every read also re-ran last week's regression
files for its area; all held.

## 1. High

None.

## 2. Medium

- ~~**R1**~~ — **Done in #3229**: the page digest also covers how the page's group rows group (`spec/reviewer-surface.md` "Form HTML mechanics"; `tests/integration/test_review_form_ordinals.py`). **A stale group form writes into a different group after a
  regroup.** The page digest covers only the page's assignment-ID set
  (`app/services/responses/_form_keys.py:70`); a group row is fanned out
  by its representative member's *current* group key. Revert, move Ann
  from red to blue, re-activate, then Save an open tab: red's answer is
  lost and Ann, Cy and Di take blue's, with no refusal. An unedited
  re-save refills the group #3098 just cleared. *Reproduced.* Code:
  `spec/reviewer-surface.md` says a stale form is refused. Digest each
  row's group membership too.
- ~~**R2**~~ — **Done in #3230**: the change test and the reviewer surface read a stored value as a Save posts it, and a blank of a blank is no change (`spec/reviewer-surface.md` "Persistence semantics"; `tests/integration/test_change_after_submit.py`). **An unchanged re-save clears a Submit stamp** when the stored
  value is CRLF or a non-canonical number (`"04"`): the change test
  (`app/services/responses/_core.py:410`) compares the raw stored value
  with the normalized post (CRLF→LF, 19X; canonical numbers, #3106). The
  answer leaves `/results` and the observer's stats until the reviewer
  submits again, unprompted. Sources: answers saved before those fixes,
  and the responses import, which stores values verbatim. *Reproduced.*
  Code: normalize the stored value before comparing.
- ~~**R4**~~ — **Done in #3230**: the observer CSV carries a `Submitted` column (`spec/participant_model.md`; `tests/integration/test_observer_collation_body.py`). **Ruled 2026-10-22: include drafts, each marked as unsubmitted.** **The observer per-instrument CSV includes unsubmitted
  values** (`app/web/routes_reviewer/_collation.py:188`, no
  `submitted_at` filter) that the collation page's stats and `/results`
  leave out, so an edit R1's ruling says is "not released as submitted"
  reaches observers. *Reproduced.* Author: a submitted-only switch on the
  observer route, or `spec/participant_model.md` says drafts are
  included.
- ~~**L1**~~ — **Done in #3231**: Session Home skips the Release window's order and cap when neither box was edited (`spec/lifecycle.md` §8.2.7; `tests/integration/test_schedule_ordering_routes.py`). **Ruled 2026-10-22: skip the pair's checks when neither release box was edited, as for the other two pairs.** **An untouched Release window refuses every Session Home
  Save.** Save re-checks the Release-from / Release-until pair on every
  post (`app/web/routes_operator/_session_home.py:395`) against the
  365-day cap; the L6 skip covers only the other two pairs. A Settings
  import (no cap, by design) or Release → Stop releasing a year later →
  Revert stores such a pair, and a rename then answers 422 until the
  operator edits a box they never touched. *Reproduced.* Spec/author:
  `spec/lifecycle.md` §8.2.7 promises a Save is never refused over an
  unedited pair. Skip both-unedited, or cap at import.
- ~~**O1**~~ — **Done in #3228**: every bundle member name is made safe at the zip writers (`spec/extract_data.md` "Zip member names"; `tests/integration/test_zip_member_names.py`). **A session code becomes a zip member's path.** The code is
  free text and enters member names unchanged (`filename()`,
  `app/services/extracts/__init__.py:46`; the by-instrument, shape and
  metadata members): a co-owner's `../../evil` puts `../../evil_*.csv` in
  every operator's `bundle.zip` and `responses_bundle.zip`; `2026/Q1`
  makes a folder; `:` or `*` breaks Windows extraction. *Reproduced.*
  Code: sanitize the code once, as the slugs already are.
- ~~**S1**~~ — **Done in #3232**: the slot refuses with the count unless `acknowledge_response_loss` carries it (`spec/quick_setup_card_spec.md` "Result reporting"; `tests/integration/test_relationship_group_clear_asks_first.py`). **Ruled 2026-10-22: ask, as the Relationships Setup card does.** **Quick Setup's Relationships slot deletes saved group answers
  without asking.** `_save_slot` passes no `acknowledged_loss`
  (`app/web/routes_operator/_quick_setup.py:938`), so on a reverted
  session with responses a Relationships file plus the replace tick
  answers 303 and 4 responses become 1; the Setup card refuses the same
  file with a count. Reachable from a stale Home tab or a direct POST.
  *Reproduced.* Author/spec: `spec/quick_setup_card_spec.md` predates
  the 2026-10-17 "ask first" ruling. Refuse while responses exist, or ask.
- ~~**C1**~~ — **Done in #3233**: a reminder, and the Invitation card, build the link again from its token (`invitations.current_invite_url`; `spec/architecture.md`; `tests/integration/test_invitation_link_reuse.py`). **Ruled 2026-10-22: nothing was sent before the flip; add the guard anyway, rebuilding the link from the token.** **Reminders resend invitation links from before the
  `/reviewrobin` flip.** `send_reminder` reuses the URL in the last
  invitation email whenever its token still matches
  (`app/services/invitations.py:729` checks only the token segment), so
  a pre-21D `https://<host>/me/invite/T` goes out on every reminder and
  shows as the copyable invite link; the host answers it 404.
  *Reproduced.* Author (was anything sent before the flip?), then code:
  require the stored URL to equal `build_invite_url(token)`.

## 3. Low

- ~~**R3**~~ — **Done in #3234**: `spec/reviewer-surface.md` "Persistence semantics" says what a lone blank keeps and what it still asks for (`tests/integration/test_change_after_submit.py`). **Ruled 2026-10-22: narrow the spec: a blank that leaves nothing on its row needs no new Submit.** Blanking an assignment's only answer after Submit leaves the
  review reading Submitted: the blank rule unstamps the same assignment's
  other rows (`_core.py:432`) and there are none. *Reproduced.*
  Spec/author: narrow the "must Submit again" sentence, or add a
  session-level marker.
- ~~**L2**~~ — **Done in #3234**: `date_formatting` pads the year itself (`tests/unit/test_date_formatting.py`). A year below 1000 renders unpadded (`strftime("%Y")`,
  `app/services/date_formatting.py:250`, `:275`): End `0026-10-27`
  saves, re-renders as `26-10-27 12:00`, and every later Save is 422.
  *Reproduced.* Code: `f"{year:04d}"`, or refuse years below 1000.
- ~~**O2**~~ — **Done in #3235**: both writes answer 409 under the session lock and the page renders read-only (`spec/email_template_editor.md` §5; `tests/integration/test_email_template_editor.py`). **Ruled 2026-10-22: lock the email template editor on archived sessions.** The Archive page's Archived column and sort read `updated_at`
  (`app/web/views/_sessions_table.py:56`), which the email template
  editor (writable on archived sessions) moves. *Reproduced.*
  Spec/author: an archived timestamp, or lock the editor.
- ~~**O3**~~ — **Done in #3235** (`tests/integration/test_operator_settings.py`). **Ruled 2026-10-22: store the password as typed.** The SMTP password is `strip()`ped before it is stored
  (`app/services/operator_settings.py:316`); latent, since nothing
  sends. *By reading.* Author.
- ~~**S2**~~ — **Done in #3236**: a file is chosen when it has a filename (`spec/setup_pages.md`; `tests/integration/test_held_upload_setup_cards.py`). An empty file chosen on a Setup upload card sends the held
  file instead (`read_upload`, `app/web/routes_operator/_shared.py:236`),
  on all four cards. *Reproduced.* Code: a non-blank filename means
  chosen, as Quick Setup's `_attached` does.
- ~~**S3**~~ — **Done in #3236**: `_check_uploads` runs through `run_in_threadpool` (`tests/integration/test_import_config_route.py`). Quick Setup can take the session-row lock on the event loop:
  `_check_uploads` runs inside the async path and, on a malformed
  Settings row, reaches `lock_session` (`_quick_setup.py:633`, `:796`).
  Postgres only. *By reading.* Code: `run_in_threadpool`.
- ~~**P1**~~ — **Done in #3236**: an email claim counts only when non-empty after strip (`cordware/spec/identity.md`; `tests/integration/test_blank_email_claim.py`). A whitespace-only email claim counts as an email
  (`cordware/identity.py:156`): the user row stores `""`, the next
  sign-in answers 500 on the unique email, and a valid fallback claim is
  hidden. `spec/permissions.md` §2 says 401. *Reproduced.* Code, plus
  "non-empty after strip" in `cordware/spec/identity.md`.
- ~~**P2**~~ — **Done in #3236**: `refuse_oversized_ids` reads a declared form body and the `cursor` (`tests/integration/test_bad_input_refused.py`). Oversized ids in form bodies (`session_ids`, `user_ids` and
  the roster and assignment `*_ids` lists) and the audit-log `cursor`
  still answer 500 on SQLite; `app/web/oversized_ids.py` reads only path
  and query. *Reproduced* on nine routes. Code.
- ~~**E1**~~ — **Done in #3237**: the engine skips a disabled rule at any depth, the card hides one, and the import refuses a used rule set the card can't show (`spec/csv_contracts.md` §3.3; `tests/integration/test_rule_writes_checked.py`). The engine and the shape gates read a stored rule set
  differently: the engine ignores a Composite child's `enabled`, and the
  gates look only at `link1` / `link2`, so a hand-edited Settings CSV
  stores rules the card hides and its next Save drops. *Reproduced.*
  Code.
- ~~**E2**~~ — **Done in #3237**: `responses.is_catch_all_key`, read by Generate, the preview and the column (`spec/assignments.md`; `tests/integration/test_group_self_review_roster.py`). **Ruled 2026-10-22: the empty-key catch-all group never counts as the reviewer's own.** On a relationship-tag boundary a reviewer's whole "no
  relationship" group counts as a self-review: the (R, R) pair keys to
  `("",)`, like every unrelated reviewee. Only stored or imported
  boundaries reach it. *Reproduced.* Author.
- ~~**E3**~~ — **Done in #3237** (`tests/integration/test_prepare_counts_group_clears.py`). Prepare answers 500 instead of reporting a failure when the
  dry-run cannot load a rule set (`app/web/routes_operator/_workflow.py:145`,
  before the step's `try`). *By reading* past a reproduced
  `ValidationError`. Code.
- ~~**C2**~~ — **Done in #3235**: the sort script expires the `Path=/` copy on load and on sort (`spec/sessions_overview.md`; `tests/browser/test_sys_admin_sessions_table.py`). An old `Path=/` sort cookie beats the new `/reviewrobin/` one
  on the server (Starlette keeps the last value, the JS the first), so
  the lobby sorts by a stale order the operator cannot clear.
  *Reproduced.* Code: `_rrwWriteCookie` also expires `Path=/`.
- ~~**S4**~~ — **Done in #3238**: Create takes both owner locks through `run_in_threadpool` (`tests/integration/test_owner_add_lock.py`). *Found by the cold read of the S3 fix.* Create with Quick
  Setup files takes a user-row lock on the event loop: `create_session`
  is `async def` and calls `session_owners.lock_owner_eligible` (`FOR
  SHARE`), and `write_staged_owners` → `add_owner` locks each staged
  owner (`app/web/routes_operator/_quick_setup.py:253`, `:319`).
  Postgres only. *By reading.* Code: `run_in_threadpool`, as S3.
- ~~**P3**~~ — **Done in #3238**: a blank object id, claim or header, yields to the next (`cordware/tests/test_identity.py`). *Found by the cold read of the P1 fix.* A whitespace-only
  `objectidentifier` claim still counts as the principal id
  (`cordware/identity.py`, `_claim` with `blank_counts=True`), hiding a
  valid `oid`; `find_signed_in_user` never matches a blank one, so the
  object-id identity is lost. *By reading.* Code: as P1.
- ~~**E4**~~ — **Done in #3238**: the Assignments page names the instrument and Validate reports `instruments.rule_set_unloadable` (`tests/integration/test_prepare_counts_group_clears.py`). *Found by the cold read of the E3 fix.* A stored rule set
  that cannot load makes the Assignments and Validate pages answer 500
  however they are reached (`staleness_by_instrument` →
  `_session_rule_set_to_schema`, `app/web/views/_assignments.py:153`,
  `app/services/validation.py:879`). *Reproduced.* Code.

## 4. What the reads tried and found sound

One line per read; the reports themselves were working notes.

- **R:** ordinal parsing and digest refusals; the R1 group rules;
  regroup clears (shrink and split keep, a gain clears); `resolve_mode`;
  archived short-circuits; public IDs on every participant path.
- **L:** the L2–L8 fixes; 19X Item 6's box shapes; Item 9's counts;
  Duplicate's fresh `public_id` and `form_key`; scheduled events decided
  under the lock; purge and archive atomic.
- **O:** the sort cookie (#3208); Select all; `content_disposition` on
  every download; the observer CSV by instrument number; the O2–O10
  fixes; Accounts and Diagnostics.
- **S:** held uploads scoped to token, operator and session, swept, and
  cascaded; the S-row fixes; S4 and #3141; the pair-tag gates; every
  other group-clear ask.
- **P:** all 197 routes walked through their dependencies; 41
  cross-session child-id routes and 68 cross-session form bodies changed
  nothing; integer, negative and malformed public IDs 404; 13 hostile
  principal headers, none 500.
- **E:** the E-row fixes (133 tests); operators and the empty-value
  rule; self-review per instrument; group answers on Generate (projected
  equals deleted); the reconcile stamp's inputs.
- **C:** 122 POST routes under the mount, none leaking an unprefixed
  URL; `return_to` including `//evil`; static files; the lifespan runs
  once in order; the fake-auth guard fails closed.

**Not covered:** anything Postgres-only beyond reading (S3, P1's
`DataError`, the row-lock semantics), and every browser-only behavior.
