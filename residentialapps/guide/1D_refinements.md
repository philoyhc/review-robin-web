# Segment 1D, item 1: refinements from the browser check

**Opened 2026-11-06** (author), from the browser check of Support Logs'
screens signed in as Daniel Koh (RF). Rungs 11–12 of item 1's iteration
("7+", `residentialapps/guide/segment_1D_support_logs.md`). Placeholder
screens and sample data only (`residentialapps/supportlogs/`): nothing is
wired. Read against RRW `3018287a6`.

## The roles the screens serve (author, 2026-11-06)

| In practice | Grants | Sample viewer |
|---|---|---|
| **RFs and RSLMs**: the frontline | Frontline; an RSLM may also be a Safety-flag recipient | Daniel Koh (RF); Priya Raman (RSLM, also recipient) |
| **Office staff**: coordinate consultation checks | Consultation check | Hui Min Goh (Exec) |
| **The Master**: overall coordination, workload oversight | Senior identifiable, Other Staff view: aggregate, Safety-flag recipient | Sam Lee (Master) |
| Administration | Sys admin; the platform's super-admin | Rachel Yeo (Admin); the platform super-admin |

The grants do not change: Access still lists each one, Other Staff view
included. Only the sample viewers change.

## Rung 11 — The sample viewers

- **Removed from the viewer switcher** (`VIEWERS`): Kenneth Lau, Siti
  Rahman, Marcus Tan, Nadia Hassan and Wei Jie Ong. They stay on the Staff
  roster copy, which Residential Operations shares, so Access still lists
  them. A grant a removed viewer held moves to `_OTHER_GRANTS`, so Access
  and Who holds access keep a holder where one is needed.
- **Hui Min Goh** becomes the office staff viewer (author, 2026-11-06):
  Consultation check in place of Safety-flag recipient. She is on the
  roster copy already as Residential Executive, so the roster and
  Residential Operations are untouched. Her Home redirects to the
  Consultation check, her only page.
- **Sam Lee** gains Other Staff view: aggregate (author, 2026-11-06).
- **Views no longer offered by the switcher** stay covered by tests on
  the grants themselves: the 403 page (a rostered person with no grant),
  aggregate-only Overview, and a Home listing two destinations.
- `guide/fake_ids.md` and `guide/1D_browser_checks.md` lose the removed
  viewers' commands and steps.

## Rung 12 — Home and Log encounter

- **Home:** the full-width **Log encounter** button goes; **Log** in the
  tabs reaches the same page.
- **Favorites:** on **Students**, each row of *My students* and *Shared
  with me* gets a favorite toggle, a star in the Toggle role
  (`aria-pressed`). **Log**'s quick picks become the viewer's favorites,
  in the order favorited, instead of the first six of the working set,
  with a hint under them: "Mark favorites on Students to pick them here."
  "Or find a student" stays for everyone else. Favorites are per staff
  member and private; marking one is not a read and writes no audit
  event. On sample data the toggle is inert and the favorites are seeded:
  two per frontline viewer (author, 2026-11-06), Daniel Koh's being one of
  his own students and S-08, which Priya Raman shared with him.
- **The shared student** (author, 2026-11-06: the existing share is kept):
  Priya Raman's records for S-08, shared with Daniel Koh on 2026-10-20.
  As one of Daniel's favorites, S-08 is reachable from Log too. Logging an
  encounter with S-08 records Daniel's own encounter; Priya's records stay
  read-only to him.
- **Durations:** 15 min, 30 min and 60+ min. Sample encounters with a
  dropped duration take the nearest kept one (5 and 10 min → 15 min;
  45 min → 30 min; 60 min → 60+ min).
- **Types:** "Student-initiated conversation" and "Staff-initiated
  conversation" go, leaving Check-in, Welfare follow-up, Practical support
  and Other. `SAYS_WHO`, which hid *Who started it?* for those two, goes
  with them, so the question shows for every type. Sample encounters of
  the two types become Check-in.
- Configuration's Durations and Types cards follow, reading the same lists.

## Checks

Each rung is one RRW PR on the `residential` CI lane, with
`residentialapps/spec/supportlogs_ui.md` and `guide/1D_browser_checks.md`
updated in it, and its own read. Done when the author's browser check
passes: the switcher's six viewers; Daniel Koh's Home without the button;
Log's two favorites, S-08 among them, and the hint; the three durations
and four types.

## Status

- **Rung 11:** as planned, except that the combinations no role in
  practice holds are not moved into `_OTHER_GRANTS`: they stay drawn for
  `?as=` but off the card (`UNLISTED_VIEWERS`), so the tests still reach
  the pages they open and Access still lists their grants. They are Wei
  Jie Ong (no grant), Kenneth Lau (aggregate), Siti Rahman (identifiable),
  Marcus Tan (Consultation check), Nadia Hassan (Consultation check with
  identifiable view) and, new, Farah Aziz, an RF on the roster copy, as a
  recipient with nothing else (Hui Min Goh's old combination); Access and
  Who holds access now list her as a recipient. Hui Min Goh gains a past
  check; flag F-04, which she had acknowledged and closed, is Sam Lee's.
  The Viewing as chip reads an off-card viewer's line from their grants.
  One read: the empty past checks, F-04, three tests looping over the card
  only, a stale count, this note and the chip, all fixed.
- **Rung 12:** as planned, but for the star's role. Daniel Koh's
  favorites are Clara Tan (S-03, his plan) and Hana Rahim (S-08, shared by
  Priya Raman); Priya Raman's are S-08 and S-10. The star is the column
  chip's pressed style, not a Toggle `.btn` (no Toggle role in
  `residentialops_ui.md` §4), disabled until wired and 44 px under a
  finger: the author's call to confirm. After saving for a shared student,
  the confirmation offers to open them, as for one's own. **Open for
  wiring:** a frontline viewer with no favorite has no student to pick
  until "Or find a student" works; the sample seeds every frontline
  viewer. One read: the Open link for a shared student, the star's touch
  target, the informal follow-up path's browser test, three weak tests
  and a dead variable, all fixed. Remapped sample encounters move the frontline's support
  time and workload minutes (Daniel Koh: 105 → 120 in 14 days, 145 → 165
  in the term).
