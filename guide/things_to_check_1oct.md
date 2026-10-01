# Things to check in a browser — 1 October

Browser checks owed on `guide/post_assessment_1oct.md` work that the test
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
