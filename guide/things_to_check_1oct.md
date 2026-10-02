# Things to check in a browser — 1 October

Browser checks owed on `guide/post_assessment_1oct.md` work, and on the
`guide/findings_2026-10-01_corpus.md` fixes that followed it, that the test
suite cannot settle. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked, and retire the file once every row is ticked.

E1, E2 and E4 were checked by the author when they merged.

## E5 — Assignments and Validate before the first Prepare (#2717)

- [ ] **Assignments loads fast.** Open Assignments on a session with
  about 1,000 × 1,000 rosters, no Prepare yet, and instruments not set
  up. The page should load in well under a second, not several seconds.
- [ ] **Validate loads fast.** Open Validate on the same session. It
  should also load in under a second.
- [ ] **The second load is no slower.** Reload either page; it should be
  as fast as the first.

## E6 — the sweep's six code defects (#2719)

- [ ] **Purge and archive is red.** On Extract data, the **Purge and
  archive** button should be solid red, like the lobby expander's,
  not amber.
- [ ] **A saved shape's buttons swap.** On Extract data, in the data
  shaper, a saved shape shows **Edit** and no **Save**. Click **Edit**:
  **Save** shows and **Edit** hides. Click **Cancel**: they swap back.
- [ ] **A new shape's buttons still work.** Click **+Shape**. The new
  card shows **Save**, not **Edit**. Name it, pick columns, and Save it.
- [ ] **Disabled link buttons match.** On the Reviewers page, switch
  the table into edit mode. The toolbar's **Add new**, a link, should be
  exactly as faint as any other disabled button (0.5, not 0.55).
- [ ] **The Quick Setup banner points the right way.** Upload a second
  reviewers CSV in Quick Setup without ticking the replace box. The
  banner should say the box is "just above Submit", and it is.
- [ ] **The Validate Fix link lands.** On a single-instrument session,
  run Prepare, then add a reviewer. On Validate, the
  reviewer-missing warning's **Fix on Assignments** should open
  Assignments at the top, with no dead `#reviewer-row-…` in the URL.

## Email dates in the session's zone (#2720)

- [ ] **The deadline reads in the session's zone.** On a session whose
  display zone is not UTC (Singapore, say) with a 17:00 deadline, preview
  the invitation email. `$deadline` should read 17:00, not 09:00.
- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  same zone.

## Per-instrument Open / Close removed (#2722)

- [ ] **No Open / Close on an instrument.** On the Instruments page of
  an activated session, no instrument card offers Open or Close.
- [ ] **Accepting is session-wide.** Activate a session: every
  instrument accepts. Close session: none does, and the reviewer
  surface goes read-only on every page.

## Closed surface and reading back your own answers (#2723)

- [ ] **Prev / Next survive the close.** Close a two-page session. The
  reviewer surface shows the read-only form with Prev / Next and no
  Save / Cancel / Submit.
- [ ] **Raw shows them.** Set "Who can see what you wrote" → You →
  Responses released to Raw and open a release window. The reviewer
  sees their own values on the surface and on the summary page.
- [ ] **Off hides them.** Set that cell off. The surface says the
  values are hidden; the summary says the responses are not shown and
  has no CSV link.
- [ ] **Archive hides everything.** Archive the session; the summary
  shows nothing.

## Blocked Submit and stale sort keys (#2724)

- [ ] **A blocked Submit stays on its page.** On a two-page session,
  leave a required field empty, go to page 2 and press Submit. The
  missing-fields card shows over page 2, and its Cancel stays on page 2.
- [ ] **A deleted sort field doesn't block the save.** On an instrument
  sorted by a display field, delete that field, then save the card. It
  saves, and the remaining sort keys renumber 1, 2…

## Observer tag retired (A19)

- [ ] **Migrate first.** Run `alembic upgrade head`; the app then
  starts and the Instruments page loads.
- [ ] **An old settings CSV still imports.** Import a settings CSV
  exported before this change (it has `…observer_tag` rows) through
  Quick Setup. It applies without an error, and a fresh export has no
  `observer_tag` rows.
- [ ] **Observers still see their cohort.** On the observer collation
  page, an observer with a cohort rule sees their counts; one with no
  rule sees the "no rule" message.

## Reviewer visibility is Raw or off (A18)

- [ ] **Migrate first.** Run `alembic upgrade head`.
- [ ] **The You cell cycles two ways.** On an instrument card, unlock
  "Who can see what you wrote" and click You → Responses released. It
  cycles — / Raw responses only; Anonymized summaries no longer appears.
- [ ] **A stored summary reads as off.** An instrument whose You cell
  was Anonymized summaries before migrating now shows —, and the
  reviewer's own card shows — in that cell too.

## Inactive people keep their pairs, excluded (B2, B4)

- [ ] **Deactivating excludes, not deletes.** On a prepared session
  with a saved response, set that reviewer's reviewee inactive and run
  Prepare. On Assignments the pair is still there, shown inactive; the
  Prepare card warns of no response loss.
- [ ] **Reactivating brings the answer back.** Set the reviewee active
  and Prepare again. The pair is included, and the reviewer sees their
  saved answer on the surface.
- [ ] **Validate names a reviewer left with nothing.** Make every
  reviewee of one active reviewer inactive. Validate warns that the
  reviewer "has no active assignments"; an inactive reviewer is never
  named.
- [ ] **A group member who comes back sees current answers.** On a
  group-scoped instrument, answer a group, deactivate one member and
  Prepare, change the group's answer, then reactivate the member and
  Prepare. The reviewer sees the changed answer, not the old one.

## Settings replace names its loss (C3)

- [ ] **The tick says what a settings file does.** On Session Home's
  Quick Setup card, the replacement tick ends "A settings file rebuilds
  every instrument and deletes its assignments."
- [ ] **A settings upload still needs the tick.** Unlock the card,
  choose a settings CSV and leave the tick off: Submit stays disabled.
  Tick it and submit: the settings apply.
