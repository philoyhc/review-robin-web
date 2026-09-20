# Segment 19O — rosters and instruments

**Opened:** 2026-09-14 · **Theme:** operator-facing gaps on the roster and
instrument setup surfaces · **Related:** `spec/instruments.md`,
`spec/assignments.md`

**Items close independently**, so each carries its own `### Doc impact` and
`### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19O.1` reads Item 1's manifest.

---

## Item 7 — Loose ends, recorded 2026-09-18; sixteen entries, one open

### Opportunity

Twelve things found during 19O Item 6, 19P's close, 19Q Items 1–3 and
the 18sep assessment, each living only in a conversation, a closed
item's judgment calls or a dated record. None is in a live segment;
three were dropped from 19Q Item 2's plan by the `### Status`
compaction at its close, which is how a finding with no home
disappears. Recorded as a register, not planned.

**Audited, then worked, 2026-09-18.** The audit confirmed entries 1–7,
grew 8 and added 9–12; the pass that followed closed nine and the
`spec-writer` check on it added 13. The author ruled 3 and 13 on
2026-09-18 and both are swept; 19Q.3's close added 14, ruled and built
2026-09-19. **15 was added 2026-09-19** from the author's question about
the lobby's search box, and was ruled and built the same day; **16**
followed it on 2026-09-20 — 19Q.5's cold read found 15's rename had
left the old name in live spec prose — and is the first entry to leave
a gate behind rather than a sweep. **Two stay open:** 8, the dev-slot
verification only the author can do — to which 15 adds the two adjacent
`Clear` controls and the typeahead dropdown, and 19Q.5 the Guide page —
filed here because entry 8 *is* the dev-slot list, and a second one
would be the register's own failure mode; and, not a whole entry, the
`docs/status.md` compaction half of 12, a judgment call about what to
drop. The heading counts entries; this sentence counts open threads. One candidate was checked and **rejected** — `next_action_card.html`'s context comment reads "`None`
outside the `?validated=1` entry path **and outside `is_validated`**",
which is exactly `_workflow_card.py:121`'s `validated_just_ran or
is_validated`. Quoting only its first clause makes it look wrong.

### Decision

List only. Nothing here is scheduled, scoped or sized — an entry gets
its treatment when the author takes it up, as Item 6's did.

### The register

**Fifteen worked, one open, plus the dev-slot list.** The worked
entries compact to their outcome: each one's evidence is in its commit
and in `docs/status.md`, and what a later reader needs from here is what
was found, not how. Entry 8 keeps its detail because it is still live;
entry 12 keeps its measurements because the split it records is a
decision a later reader may want to re-apply or reverse; entry 15 keeps
the two claims it measured **false**, which is the part of it a later
reader cannot reconstruct from the diff.

1. **Done.** `spec/operations_pages.md` had the invitation gate wrong in
   both directions in one paragraph — all six routes gate on
   `validated`-or-`ready`; the strictness is a button convention.
2. **Done.** `docs/status.md` annotated five of those routes
   `ready`-only.
3. **Done — ruled, spec follows.** State 4Err renders Activate against
   its own body copy. Author's ruling, 2026-09-18: *the current
   behavior is fine; spec to follow.* `spec/workflow_card.md` recorded
   it as measured-and-unadjudicated and now records it as **intended** —
   the difference between a reader treating it as a finding and treating
   it as the contract.
4. **Done — filed, not changed.** `?validated=1` writes from a GET.
   Author's ruling: keep the backend; removing it fails 208 tests across
   ~30 files. Recorded in `guide/deferred_consolidated.md`.
5. **Done.** `precondition` was in the `context.step` enum, which no
   audit row can carry — it is a `super_step` value. Spec says which
   vocabulary owns it; the dead `step or "unknown"` fallback is gone.
6. **Done.** `spec/rrw_functional_spec.md` §9.8 carried a state machine
   six segments stale. Replaced by a pointer, not a corrected list.
7. **Done — it never did.** `session.workflow_run_failed` was flushed
   and never committed, so the row died with the connection. The control
   is the finding: `workflow_run_started` survived only because a later
   service happened to commit.
8. **Dev-slot verification owed on five merged changes**, none of which
   the suite can exercise: 19O.6's sort panel on Reviewees /
   Relationships / Assignments, 19Q.2 rung 1's Manage Invitations
   counter, 19Q.2 rung 3's six rewritten copy strings, 19Q.3 rung 1a's
   State 2 card copy, and 19Q.3 rung 2's four recaptured Guide
   screencaps with the prose around them. Grown 2026-09-19 by entry
   13's two missed strings: the Quick Setup lifecycle banner and the
   Danger Zone intro, both of which want a reading in place, and again
   by 19Q Item 6's three: the instrument card **title**, the **delete
   confirmation** beneath it, and **every card's tint**, which now runs
   1..6 by creation order rather than arbitrarily. That last one is the
   only entry here a screenshot answers better than prose. Grown again
   by entry 15: the Lobby and Archive filter cards, renamed and now
   carrying a typeahead — specifically **how the `<datalist>` reads
   while typing**, which headless Chromium proves is present and does
   not settle, and **the two adjacent `Clear` controls** on the lobby,
   the tag strip's chip and the filter box's button, which clear
   different things under the same word. The screencaps block the 19Q
   close by the author's ruling, 2026-09-18; the rest block nothing.
9. **Done.** The Workflow card's State 6 told the operator reviewers had
   been notified when no transport is wired — the sentence 19Q.3's cold
   read found copied into the Guide.
10. **Done.** `spec/workflow_card.md` pointed at `invitations_generate`,
    retired with the Create invites button.
11. **Done.** `tools/code_metrics.py --churn-only` reported a ratio
    pinned at `1.0x` by arithmetic on a shallow clone. It refuses now.
12. **Done — header, then the split.** `docs/status.md`'s header was six
    days stale and is fixed. The file, **1,260 lines / 642K characters**
    by 2026-09-19, was named a compaction target by
    `guide/codebase_assessment_18sep.md` §4 "in §3's sense: with a
    register to catch what falls out". Measured first: 217 dated rows
    were **76% of the characters**, and 118 of them name an archived plan
    that holds the real detail. **Author's call: split rather than
    summarise.** Rows dated 2026-09-11 and earlier moved verbatim to
    `docs/status_history.md`; `status.md` keeps its header, the live
    capability inventory, the architectural notes and the timeline from
    2026-09-12. **1,260 → 1,098 lines, 642K → 335K characters**, and
    §3's rule is satisfied by construction — nothing was summarised, so
    nothing could be lost, and the register is a file rather than a
    paragraph. Two pre-existing defects surfaced: one 2026-05-07 timeline
    row was inside the three-column **Segments shipped** table, where it
    renders malformed, and the table has never been strictly newest-first
    (six adjacent pairs, all April–May). The first is filed in date
    order; the second is left alone and recorded, reordering a dated log
    being churn that makes every later diff harder to read.
13. **Done — ruled and swept.** *Pause* and *Revert to draft* named one
    transition in two vocabularies. Author's ruling, 2026-09-18:
    **Revert to draft is the external-facing canonical name; Pause is
    the legacy and internal equivalent.** Operator copy says Revert to
    draft, internal identifiers keep Pause, four specs say which is
    which. `spec/domain_assumptions.md`'s *Closed/Paused* was left
    alone: that is **instrument** status, a different Pause.
    **Reopened and finished 2026-09-19: the sweep matched the label,
    not the word.** Two rendered strings said it in lower case, in
    running prose, and neither was pinned by a test. The Quick Setup
    lifecycle banner renamed its *second* sentence and kept "Setup
    edits are **paused**" in the first — two vocabularies inside one
    string literal, three lines under a docstring citing this ruling.
    The Danger Zone card read "Both are locked while the session is
    Activated — **pause it first**", above the two per-control notes
    the sweep did rename. Both now use the house pair the rest of the
    app uses (`_validate.py`: "Setup is locked. Revert to draft on
    Session Home to make changes."), and both are pinned, each
    assertion mutation-checked against the copy it replaced.
14. **Done — ruled and built.** `spec/workflow_card.md` tested
    `needs_acknowledge` before invitation state, so 4W was modelled as
    exclusive with 5 and 6 and its button column showed three. The
    template tests invitations **first** and appends the warning line
    independently, and `send_invites_visible` reads invitation state
    alone. Measured: validated, invitations generated, one fresh W8
    warning renders **State 5's body, the warning line and four button
    slots**. Author's ruling, 2026-09-19: **fix the spec — `W` is an
    overlay on States 4, 5 and 6**, so `5W` and `6W` exist. Swept
    across four documents and the template's own comments; the `4W`
    column is gone from the button table, which changes no totals
    because the overlay changes no button's visibility. **Nothing
    pinned any of it** — `needs_acknowledge` and `4W` appeared nowhere
    under `tests/` — so the overlay now has a test, mutation-checked
    four ways. Predates 19Q; surfaced by 19Q.3's `spec-writer` pass. It
    is also 19Q Item 4's reproduction case, and that plan is annotated
    with the name. **The slice's own defect was the gate, not the
    model**: an absolute `from tests.…` import that `python -m pytest`
    resolves and the `pytest` console script does not, so CI failed at
    collection where the sandbox was green.

15. **Done — ruled and built.** *"There's no search button for the
    search box?"* (author). There is not, because it is not a search
    box: the Session Lobby's control hides rows already rendered, live
    on every keystroke, and never queries or navigates. The Archive
    page carried a copy. **Author's ruling: it is a filter, name it
    one, fold the Archive in** — plus typeahead over name, code and
    tag. Three rungs, PRs #2488 → #2489 and this close.

    The ruling dissolved the opening question rather than answering it:
    a filter that applies live has nothing to submit, so the missing
    button was correct and the `Cancel` beside it was the odd control.
    It is `Clear` now, in a card headed `Filter`, on both pages.

    **The two copies became one.** The matching rule is
    `rrwSessionFilterMatches` in `base.html`, beside the sort primitive
    the same two pages already share. A first pass made the copies
    *identical* instead, which the cold read named as how the fourth
    drift starts — the entry's own argument for folding the Archive in
    was that two copies had already drifted three ways. The three
    drifts themselves stand: AND/OR pills on the lobby against
    hardcoded OR on the Archive, and two different empty-state
    mechanisms, each right for its page.

    **Two claims measured false, both mine, both recorded rather than
    dropped.**

    - *The cross-column false positive does not reproduce.* Driving the
      filter in Chromium and then mutating the matching back showed the
      check written to prove it passing against the old code too.
      `textContent` carries the markup's indentation, so the haystack
      read `"\n                Spring Review\n               2026-A"`
      and nothing typable bridged that gap. Per-column matching shipped
      on the reasons that survive: it is the documented rule, and it
      stops the behaviour depending on template whitespace.
    - *The session cap halved a session.* Names and codes were merged
      and sliced, so 150 sessions offered 150 names and 50 codes — the
      rest findable by one spelling of their identity and not the
      other, while the docstring claimed the opposite. It counts
      sessions now.

    The **tag** defect was real and is fixed: `team a` no longer drags
    in `team a2`, which is the collision whole-value matching exists to
    prevent and these two pages were the only surfaces to have.

    **The gap under all of it was that page JS had no test but
    `node --check`.** `tests/integration/test_session_filter_rule.py`
    executes the rule under the node CI already runs, and writing it
    immediately found a hidden precondition — the function assumed a
    pre-lowercased term.

    **Found while auditing, not fixed:** the Archived page's row
    expander ships a `Download` button `disabled` unconditionally, a
    placeholder for an export that does not exist, with nothing beside
    it saying so. Now at least audited (`spec/operator_button_audit.md`
    §2a #184), along with the rest of that page's buttons, which had no
    section at all.

    **Open for the author, on the dev slot:** the lobby now shows the
    tag strip's `Clear` chip and the filter box's `Clear` button side
    by side, clearing different things. `Clear` is the app-wide word
    for both, so the rename is right and the adjacency is what is new.

16. **Done — built 2026-09-20.** Entry 15's rename left the old value
    behind, and the entry's own count of it was wrong twice over. It
    said three files, four lines, taken from the cold read that found
    it rather than measured; the re-grep found **five** live lines
    across four files — `spec/operator_ui_concept.md`,
    `spec/visual_style_rrw.md`, two CSS comments in
    `app/web/templates/base.html`, and a comment in
    `app/web/templates/operator/sessions_list.html` that no one had
    listed at all. A sixth, in `docs/status_history.md`, my own grep
    hid: the line cites an archived plan and I had piped the search
    through `grep -v guide/archive/`.
    **Three stay**, all historical records: `guide/todo_master.md`'s
    account of a decision taken when the card *was* called Search,
    `guide/roster_expander_revamp_handoff.md` (shipped and superseded,
    and about a roster page, which still has a real search), and this
    entry, quoting the old name on purpose. `docs/status_history.md`
    takes the file-level escape, its whole premise being rows kept
    verbatim.
    **The durable half is a gate**, and it covers less than a first
    draft of this entry claimed: `Search card` joins the retired
    vocabulary in `tests/unit/test_doc_conventions.py`, whose
    `LIVE_DOCS` is `spec/` + `docs/`. That catches the spec and status
    prose — where a stale control name is a live contract — and **not**
    the template and test comments, which are most of what was fixed
    here. Widening `LIVE_DOCS` to `app/` and `tests/` is a bigger change
    than this entry, and is not made. Mutation-checked: put either spec
    line back and it fails.
    **Matched by pattern, not substring, after Codex (#2507) put the
    first draft's own failure to it**: the literal `Search card` passed
    over `spec/rehydrate.md`'s *"the search card's"* and
    `docs/status.md`'s *"search-card"*, so the gate reproduced, inside
    an hour, the miss it was written to prevent. It is
    `search[-\s]card`, case-insensitive, which found three more live
    lines plus two in `tests/` and one module docstring.
    **The pattern is knowingly ambiguous**: the roster and operations
    pages put their real search in a card, so "search card" is the
    correct name for *those*, and the day a spec says so this fires on a
    true line. The answer then is the line-level escape, not a narrower
    regex — no pattern can tell the lobby's card from a roster's. The term is the **card**, not
    the word — seven operator tables still carry a real `Search:` input
    and a `Search` submit button, and those are correct, which is why
    entry 15 was right to rename only the two lobby pages.
    `.claude/skills/segment-plan/SKILL.md`'s blast-radius recipe names
    the list, so its "(button vocabulary today)" aside is updated too.

### Doc impact

- `docs/status.md` — a row when entries are worked, and its own stale
  header (entry 12). Which specs change is not knowable until each is
  taken up; the register sizes nothing on purpose, so its manifest grows
  an entry at a time rather than committing up front to the specs the
  entries would touch. The bullets below are that growth, added
  2026-09-18 as nine entries were worked.
- `spec/operations_pages.md` — the invitation gate stated at both layers (entry 1).
- `spec/lifecycle.md` — `precondition` named as a `super_step` value rather than a `context.step` one (entry 5).
- `spec/rrw_functional_spec.md` — §9.8's parallel state machine replaced by a pointer; the Pause naming in §6.1 and §16.2 (entry 6); the state count and the right-column list (entry 14).
- `spec/workflow_card.md` — State 6's copy and the retired `invitations_generate` pointer (entries 9, 10); 4Err-renders-Activate recorded as intended (entry 3); the `W` overlay replacing the `4W` state in the cascade, both tables and the detour (entry 14).
- `guide/deferred_consolidated.md` — the `?validated=1` deferral, recorded where deferrals live (entry 4).
- `spec/session_home.md` — the two draft-returning transitions under one label (entry 13); the state list and the validated-row button note (entry 14).
- `spec/quick_setup_card_spec.md` — the lifecycle banner's copy (entry 13).
- `spec/settings_inventory.md` — the lifecycle-transition action names (entry 13).
- `spec/visual_style_rrw.md` — the Workflow card's transition list (entry 13).
- `spec/sessions_overview.md` — the card is a **Filter**, not a Search: its drawing, its control table and its prose all name a `Search` card carrying `Cancel`, where the shipped card is headed `Filter` and carries `Clear`. Also the matching rule, which is per column and whole-value on tags now, and the typeahead (entry 15).
- `spec/operator_button_audit.md` — Section 2 row 12's card name and the `Cancel` it lists; the Archived page has **no section at all**, so its filter card's `Clear` is unaudited along with the rest of its buttons (entry 15).
- `spec/setup_pages.md` — its "Search matching and suggestions" section states the per-column rules for seven surfaces; the Lobby and Archive are now an eighth and ninth that follow them by a different mechanism, and the one deliberate divergence (no `"Name (handle)"` label, because a per-column filter cannot match it) belongs beside that rule (entry 15).
- `spec/operator_ui_concept.md` — the lobby's create affordance is described as sitting in the `Search card` (entry 16).
- `spec/visual_style_rrw.md` — the same, in the Create Session affordance row (entry 16).
- `spec/rehydrate.md` — the Rehydrate entry point is described twice as the lobby's `search card` / `search-card` button row, and its "today" button list still reads `Cancel` · `Add new`, where the shipped row is `Clear` · `Add new session` (entry 16).

### Open questions

- Which entries are worth doing at all is the author's, one at a time.
  Entry 3 is the only one carrying a behavior question rather than a
  correction.

### Out of scope

- Planning, sizing or ordering any entry. That is the point of a
  register: Item 6 proved that a finding survives a close only if it is
  written down somewhere a close does not compact.

---

## Item 6 — Loose ends, recorded 2026-09-18, settled 2026-09-18

### Opportunity

Seven things found during 19P's close and 19Q Item 1 and left where
they were, each living only in a conversation. Recorded as a register
rather than a plan, then worked through in one pass on the author's
instruction.

### Decision

Settle all seven. One carried a behavior choice, one a scope choice,
both the author's: the lost *"no reviewer matched"* hint is **restored**
rather than specced as an accepted loss, and the per-page sort-workaround
migration **stays filed** rather than riding this pass. *(Annotated
2026-09-18: the author took the migration up after the other seven had
landed, so it rode a later slice of this item rather than a later item.
See `### Status`.)*

### Doc impact

- `spec/rrw_functional_spec.md` — **§9.6**'s session status card described against the shipped template: half-width, no bulk controls, and the two that went at 18R Item 3 went for different reasons (Item 6).
- `spec/lifecycle.md` — the `_REVERT_RETURN_TO` allowlist loses the dead `previews` slug (Item 6).
- `spec/preview_hub.md` — **Open reviewer surface** opens page 1, not `{page_n}` (Item 6).
- `spec/operations_pages.md` — the drill-in's email region sits below two cards or three, depending on the Review Progress card (Item 6).
- `app/web/spec_registry.py` — `_preview_surface`'s governing spec, which pointed only at the retirement note (Item 6).
- `README.md` — the `previews` route row is a redirect, not an Operations row (Item 6).
- `guide/new_ux_ideas.md` — entry 2 no longer proposes folding in a retired page (Item 6).
- `spec/reviewer-surface.md` — the redirect now carries the unmatched address, and the landing page re-checks it; **added at the close**, having been marked `cites:` on the registry half alone (Item 6).
- `spec/operations_pages.md` — the shared page shape gains a conditional fifth region between the Workflow card and the info card; **added at the close** (Item 6).
- `spec/workflow_card.md` — its copy of the return-to allowlist carried the dead `previews` slug too; **added at the close** (Item 6).
- `spec/instruments.md` — the page-layout and status-card sections, which §9.6 delegates to and which carried the same four errors; **added at the second close pass** (Item 6).
- `spec/visual_style_rrw.md` — the card cited as the worked example of legitimate full-width is half-width; **added at the second close pass** (Item 6).
- `spec/ui_elements.md` — the `.session-row-selected` row, whose per-page
  note listed which pages had migrated off 19P.1's handler; **added at the
  close**, the sort migration having been outside this item when the
  manifest was written (Item 6).
- `docs/status.md` — the 11F attribution on `GET .../preview`, the corrected status-card description, and the row when this lands (Item 6).

### Status

**Settled 2026-09-18 — all seven, then an eighth.** Two touched
behavior, five were prose, and the register's own missing line (the
sort migration) was taken up after them.

- **`app/web/spec_registry.py`** pointed `_preview_surface` at
  `spec/preview_hub.md` alone — a file that, since 19Q Item 1,
  explicitly hands the surface contract to `spec/reviewer-surface.md`.
  The registry named a document disclaiming the module it governed.
  Both modules now list `reviewer-surface` first.
- **The dead `previews` return-to slug** is out of
  `_REVERT_RETURN_TO`, its docstring example, and `spec/lifecycle.md`'s
  copy of the allowlist. It is an allowlist, so a stale member is a
  redirect target nothing can reach rather than a hazard — but an
  allowlist that lists the unreachable teaches a reader the wrong set.
- **The lost hint is restored.** `/preview-surface` now carries an
  unmatched address to Manage Invitations as `?no_match=`, which
  renders a `pill-empty` notice naming it. Only when the operator
  supplied one: a blank email resolves to `None` only on a session with
  no reviewers, and reporting *"no reviewer matched ''"* would name a
  mistake nobody made — the existing empty-roster test now pins that
  the hint is absent there.
- **The unordered `select` was one of two.** The register named
  `test_reviewers_page_mutate.py`; `test_observers_row_landing.py`
  carries the same `[210]` index against the same unordered query,
  copied from it along with the defect. `test_preview_pager.py`, which
  looked like a third, already ordered. Both fixed. *A register entry
  names the instance somebody noticed, not the class.*
- The documentary corrections, one bullet each in `Doc impact` above.
  Counted rather than summarised, because two records of this item
  disagreed on its size at the close and neither number was right.

**The cold read found five faults, and two of them were the entries
fixed badly rather than the entries themselves.**

- *The invariant was asserted in four places and was false.* "A blank
  email means an empty roster, so no hint" holds of the resolver, which
  strips; the redirect gate read the raw string, so `?reviewer_email=%20`
  on an empty roster produced "no reviewer has the email" followed by
  nothing. **Two gates on one value have to agree about what counts as
  blank.**
- *The hint stated a fact it never checked.* `no_match` came straight
  off the query string, so a hand-typed one had the page assert that a
  reviewer sitting in the table below did not exist. The route now
  re-checks it against the roster, folded through `normalize_email`.
- *The dead-slug fix was half done.* `spec/workflow_card.md` carries
  the same allowlist as `spec/lifecycle.md` and kept `previews` —
  leaving two live specs disagreeing, which is the defect the entry was
  filed for.
- *The §9.6 correction cited §9.1, and fixed one wrong clause inside a
  sentence wrong in four more.* The card is half-width, not full-width;
  has an accepting **count**, not a per-instrument pill row; has no
  visibility pill row at all; and holds two buttons, so "read-only" was
  the wrong word. And the two bulk controls went **differently** at 18R
  Item 3 — the accepting one was never wired, the *Show all when closed*
  toggle was on the page and was removed. Rewritten against the
  template.
- *The new card ignored the repo's notice idiom* — no `role="alert"`,
  no `banner-scroll-target`, and a `.pill-empty` used as a message
  label where every other surface uses it for a counter.

**One line the register should have had and did not.** Item 4's own
`Status` says the remaining sort-workaround migration is Item 6's, and
nobody wrote it down here — so the register was incomplete about its own
scope from the day it was filed. It is a line now, and it closed here:

- ~~**Migrate `session_reviewees`, `session_relationships` and
  `session_assignments`** off 19P.1's per-page capture-phase handler
  onto the shared `rrw:sorted` listener.~~ **Done 2026-09-18**, as its
  own slice after the author deferred it from the first pass. The port
  was three lines per page and identical on each, every `render()`
  already opening with the same panel cleanup. `MIGRATED_PAGES` is all
  six, and the guard that permitted *either* mechanism during the
  migration now **requires the listener and forbids the old handler
  beside it**: a page keeping both removes the panel twice and
  re-renders twice per sort.

  *The inverted assertion took three attempts, and the first two are
  the same mistake.* It first matched `setTimeout(render, 0)`, which
  every one of these pages also uses in its select-all handler, so it
  failed on `session_reviewers` — migrated days earlier and carrying no
  workaround at all. It then matched the historical handler's **exact
  byte-shape**, which a cold read ran against nine plausible
  re-introductions: **one caught, eight through**, including a guard
  that only calls `render()`, which is the double-render the test names
  in its own failure message.

  Both drafts were guessing how a future handler would be spelled. The
  guard asserts a **property** now — these pages touch `rrw-sort-btn`
  in markup only, there being no legitimate script-side reason to look
  at a sort button on a page that listens for `rrw:sorted`. The lobby
  is the one exception, and gets a whitelist rather than an exemption:
  the first thing called after its guard returns must be
  `expanderIsDirty`. *That test's own blacklist draft was defeated by
  `refreshExpander()` in the mutation run* — the third instance of the
  same lesson in one item. The page census is derived from the
  templates too, and pinned against a list a human last read, which
  caught the derivation pulling in `session_observers` (it names
  `data-rrw-sortable` in a comment saying it has none). Thirteen
  mutants: twelve caught, one a negative control that correctly
  survived — a bare `expander = null` with no call, which removes
  nothing and re-renders nothing.

### Open questions

- **Does 19O archive now that Item 6 closes?** **No** — author's
  ruling, 2026-09-18. Emptying the segment is not closing it: 19O is a
  standing home for operator-facing gaps on these surfaces, so the plan
  stays in `guide/` and the next gap becomes Item 7.

### Out of scope

- ~~The sort-workaround migration above, by the author's ruling.~~ Taken up 2026-09-18 once the rest had landed.
- `guide/new_ux_ideas.md:143`'s mention of Previews, which is a dated
  measurement (`453546c4`) and correct on its date.

---

## Item 5 — A roster delete destroys relationships and says nothing

### Opportunity

`relationships.reviewer_id` / `reviewee_id` are
`ForeignKey(..., ondelete="CASCADE")` (`relationship.py:52,57`) and
`session.py:20` sets `PRAGMA foreign_keys = ON`, so the cascade fires on
both dialects. **Four destructive paths on Reviewers and Reviewees wipe
the Relationships roster**, measured on a seeded session:

| Path | Relationships after |
|---|---|
| `delete-all`, either page | **0** |
| CSV replace via Upload, either page | **0** |
| Row-expander `bulk-delete` of one row | 2 — proportionate, correct |

**The cascade is right; the silence is not.** Twelve surfaces are wrong
about it: six confirmations that name assignments and responses but not
relationships, three guidance cards that stop at *"clears any
assignments already generated"*, the Guide's two-sentence Relationships
section, and the Relationships page afterwards — *"No relationships
yet"* over a roster that had rows a moment ago, with the reason its
`Add new` is inactive reachable only by hovering it.

Reported by the author, who hit that button and could not tell why.

### Decision

**Say what the delete costs before it happens, and record it once it
has.** `spec/setup_pages.md` already sets the rule this violates — *"The
confirmation names what goes"* — with a three-state label for
assignments and responses; this adds the fourth thing that goes.

The twelve surfaces are copy and need one query the templates lack. A
thirteenth is not: **the audit events undercount the loss**, carrying
`cascaded_assignments` and `cascaded_responses` and no relationships,
because the cascade runs in the database where the service never sees
it. Author's call (2026-09-17): it lands here, being the same omission
and sharing the same count — splitting it would leave the log
disagreeing with the confirmation that preceded it.

**Rejected: listing relationships unconditionally.** The three-state
rule exists because a label naming a loss that cannot happen is its own
defect — so a count of zero must read exactly as it does today.
**Rejected: blocking the delete, or a second acknowledgement.** The
cascade is correct and the operator is entitled to it; what they are
owed is the price before they pay it.

### Semantics

- **Zero relationships** → the label is byte-identical to today's.
  Nothing is appended for an empty roster.
- **`relationships_enabled` false** → the roster cannot have rows, so
  the count is zero and the clause never renders. No new gate.
- **Bulk-delete of selected rows** counts the relationships those rows
  carry, not the session's — the same distinction
  `acknowledge_response_loss` already draws, and for the same reason: a
  selection that touches no pair should not claim it does.
- **The Relationships empty state** distinguishes *never had any* from
  *cannot have any yet*: with either roster empty it names the
  dependency instead of inviting an upload the page will refuse.
- **No new acknowledgement field.** Relationships carry no responses, so
  the copy half is a naming change, not a second gate.
- **The audit count is taken before the delete**, in the service — a
  re-query afterwards always reads zero. It is the number the
  confirmation quoted, so the log and the label agree by construction.
  `observers.*` reaches nothing and keeps its present payload.

### Judgment calls — decided

- **The count is the roster's, not the cascade's** (2026-09-17). The
  confirmation asks "what will this cost", answered before the delete;
  a post-hoc cascade count is the audit log's job, which is out of scope
  below.
- **The disabled `Add new` keeps its tooltip** and the empty-state line
  carries the same fact in text. A tooltip is fine as a reminder and
  useless as the only copy.
- **The audit fix rides rung 1** (2026-09-17): a count computed twice
  is a count that can disagree with itself.

### Blast radius (measured)

Commands run 2026-09-17 on `origin/main` at `7b65fda`.

- The confirmations: `grep -c assignment_count` → **4** each in
  `session_reviewers.html` / `session_reviewees.html`, plus
  `delete_discards_*` → **3** each. Seven sites per page.
- Guidance: `session_{reviewers:156,reviewees:128,relationships:124}.html`;
  the Guide at `guide.html:337`.
- **No `relationship_count` exists.** Precedents:
  `existing_assignment_count` (`csv_imports.py:918`),
  `session_response_count` (`session_lifecycle.py:1023`); both render
  helpers pass them at `_setup_{reviewers,reviewees}.py:221-223,284-285`.
- Audit: `EVENT_SCHEMAS` already declares `{"counts"}` for both event
  types (`audit.py:577,635`), so the envelope likely admits the new
  field without a schema edit — **verify, do not assume**.
- Tests asserting the confirm copy: **2** files.

### Status

**Closed 2026-09-18.** Rungs 1–4 landed 2026-09-17; the close followed
as its own slice.

**Two manifest bullets outlived the code by a day** —
`spec/csv_contracts.md` and `spec/architecture.md` were named at
planning time and never written, so `close_check` failed C3 on both
while every rung had shipped. `csv_contracts` states the roster cascade
under *Wipe-and-replace* (Relationships' own replace is the leaf);
`architecture` documents the `counts` envelope's cascade slots.

**The architecture paragraph took three drafts**, and the shape of the
failure is the keeper: the fact is a matrix — which slot rides which
event — and both prose drafts got it wrong in opposite directions, once
implying every event carries all three slots and once implying the bulk
delete carries only `cascaded_responses`. It is a three-row table now.

- **The blast radius was wrong twice about one line.** No
  `relationship_count` existed, it said; the service helper did
  (`relationships.existing_count`) *and* a context key of that name
  already reached these templates via `views.session_status_pills`.
  Rung 1 needed no wiring.
- **`EVENT_SCHEMAS` needed no edit** — but verify, never assume: strict
  mode fails the *write*, so a suite not exercising the new key passes
  either way.
- **Rung 1 widened to the import path**, uncounted by the DoD's "four
  deleting events". A replace deletes and re-adds, destroying
  relationships as `delete-all` does; leaving it out would have rung 2
  quoting a number with no logged counterpart.
- **Rung 2's expander clause reads the ticked rows** where its three
  neighbours read the session — `Semantics` asks for it and the
  selection exists only in the browser. **Open for the author:** whether
  the four clauses should agree, in either direction.
- **Four copy defects, every one caught by reading and none by a
  mutation table** — prose can be pinned, not proved. The CSV replace
  inherited its sentence's opening verb and promised a roster that comes
  back; rung 3 explained the loss with *"a relationship names a pair, so
  it cannot outlive either side"*, which an identical re-upload
  falsifies (`_save` deletes and re-creates every row); the Guide sent
  operators to the `require_sys_admin` audit log; and the guidance
  rendered with `relationships_enabled` off, describing an impossible
  loss — the rule `Decision` states for labels, not carried across.
- **The re-upload advice was over-broad** (found on review of rung 3's
  PR): scoped to replacing a roster, since after a selected delete the
  surviving relationships would be destroyed by the upload it advised.
- **Rung 4 widened to the tooltip's text**, which `Judgment calls`
  settled only as "keeps its tooltip". Once the view helper knew *which*
  roster was empty, the old string was visibly wrong in two of its three
  cases — it told an operator with a full Reviewers roster to add a
  reviewer. Same source as the empty state, so they cannot drift.
- **The definition-of-done grep was adjudicated at rung 3**, not passed:
  line-based, so two targets satisfied it by *wrapping* while still
  saying the sentence, and the third should keep saying it.

### PR ladder

1. **The count helper, its context keys, and the audit field.**
   `relationship_count` in `app/services/relationships.py`, wired into
   both render helpers and both import handlers; the four deleting
   services count before they delete and pass
   `cascaded_relationships` into their `audit.counts(...)` payload,
   with `EVENT_SCHEMAS` unchanged (both event types already declare
   `{"counts"}`, so the envelope admits the field — verify, do not
   assume). **No copy changes** — the context keys render nowhere yet,
   so the visible surface is provably unmoved and rung 2 has something
   to read.
2. **The six confirmations.** `delete-all`, CSV replace and
   row-expander `bulk-delete`, on both pages. One three-state rule
   grows a fourth clause; the zero case is pinned byte-identical.
3. **The three guidance cards and the Guide.** Reviewers' and
   Reviewees' *"clears any assignments"* sentences, Relationships'
   card gaining the dependency, and `guide.html:337`.
4. **The Relationships empty state and the inactive `Add new`.** The
   two states the page cannot currently tell apart.

### Definition of done

- Deleting or replacing either roster names the relationship loss
  before it happens, asserted on all six confirmations.
- The four deleting events carry `cascaded_relationships`, asserted
  against a seeded roster and equal to the number the confirmation
  quoted; strict-mode audit tests pass.
- A session with zero relationships renders labels byte-identical to
  today's, asserted per confirmation.
- The Relationships empty state names the dependency when either roster
  is empty, and reads as today when both are populated.
- Every roster page's guidance names the relationship cost, pinned
  through `PAGE_CLAIMS` so `test_every_setup_page_states_its_own_
  invisible_fact` carries it.

  **Adjudicated at rung 3, and the check replaced.** The line was
  `grep -rn "clears any assignments already generated"
  app/web/templates/operator/` → 0, on the assumption that sentence
  would be rewritten everywhere. It should not be: an upload on any of
  the three pages *does* clear assignments, and on Relationships that
  is the whole story — there is no further cascade. Worse, the grep is
  line-based, so Reviewers and Reviewees satisfied it by **wrapping**
  while still saying it. A check two of its three targets pass
  vacuously and the third should fail is measuring nothing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**Does the audit-event undercount belong here or in its own
   item?**~~ **Answered 2026-09-17: here.** Author's call — same
   omission as the copy, and the two share a count.

### Out of scope

- **The cascade itself.** Correct as it stands; this item changes what
  the app says, not what it does.
- **Observers.** Nothing references `observers`, so no delete of one can
  cascade anywhere.

### Doc impact

- `spec/setup_pages.md` — § *Deleting the selected rows* describes the cascade as `Reviewer` / `Reviewee` → assignments → responses plus invitations, omitting relationships entirely; its three-state confirmation table gains a fourth state (Item 5).
- `spec/csv_contracts.md` — the replace contract for the two rosters states what a replace destroys (Item 5).
- `spec/architecture.md` — § *Audit-event detail schema*'s `counts` envelope gains `cascaded_relationships` alongside `cascaded_assignments` / `cascaded_responses` (Item 5).
- `spec/setup_pages.md` § *Shared body shape*'s guidance-fact table — the row each card's copy is held to; **added at rung 3**, not named at planning time, because rule 2 of the copy contract requires the row to exist for `test_every_setup_page_states_its_own_invisible_fact` to pin anything (Item 5).
- `spec/setup_pages.md` § *The table toolbar* — the Relationships-only
  prerequisite gate behind `Add new`, and the third empty-state branch
  that is its twin; **added at rung 4**, not named at planning time
  (Item 5).
- `docs/status.md` — row when the item lands (Item 5).

---

## Item 4 — A client-side sort strands the injected selection panel

### Opportunity

`_rrwApplySort` (`base.html:4363`) re-sorts **every child** of
`tbody.rrw-rows`:

```js
var rows = Array.prototype.slice.call(tbody.children);
```

An injected selection panel is one of those children. It carries a single
`colspan` cell and no `data-sort-value`, so `_rrwCellValue` returns `null` for
every sort column and the function's null-last rule parks it at the **bottom of
the table**, detached from the row it belongs to, until the selection changes.

A second effect is quieter and worse. The same pass stamps
`rrwOriginalIndex` once per row, which is what `state.length === 0` restores
when the operator clears the sort. A panel present at stamping time occupies an
index, so **every row after it is stamped one too high** and "unsorted" no
longer restores the server's order.

Found by `diff-reviewer` and by Codex independently on 19P.1 rung 1
(`#2397`). **Not introduced there** — it is a property of the two primitives
meeting, and the Session Lobby has had it since 19L.

### Decision

**Fix it once in `_rrwApplySort`**: drop `.session-expander` rows from the
tbody before the stamp-and-sort pass, then dispatch a `rrw:sorted` event so
whichever script owns the panel re-anchors it. The owners already know how to
place a panel — `refreshExpander()` on the lobby, `render()` on Reviewers — so
the fix is a removal plus a signal, not a second placement rule.

*Rejected: leave each page to defend itself.* 19P.1 already shipped that — a
capture-phase click handler on `.rrw-sort-btn` (`session_reviewers.html:850`)
that removes the panel before the inline sort handler runs. It works, and it is
deliberately local so the slice would not change lobby behavior. But 19P.2–3
bring Reviewees, Relationships and Observers, so the same workaround would be
copied **five** times against one function, and the lobby's copy of the bug
would still be live.

*Rejected: give the panel sort cells.* It has one `colspan` cell by
construction — the bracket depends on that cell being both first and last child
(`spec/ui_elements.md`, `.session-row-selected`).

### Semantics

- **Removal, not hiding.** A hidden row still occupies a `rrwOriginalIndex`.
- **The event fires on every sort pass**, including the clear-to-unsorted one,
  because that pass reorders rows too.
- **A page with no panel is unaffected** — the querySelectorAll finds nothing
  and the event has no listener. The seven sortable tables that never inject
  one keep their current behavior exactly.
- **The panel is rebuilt, not re-inserted.** Its content depends on the
  selection, not on row order; re-running the owner's existing render is
  simpler than moving a node and is what both owners already do.
- **`rrwOriginalIndex` is stamped after removal**, so the restore order is the
  server's again.

### Judgment calls — decided

- **2026-09-15.** Fixed in `base.html` rather than per page, because the defect
  is in the shared function and the per-page workaround does not scale to the
  five tables 19P will leave behind.
- **2026-09-15.** 19P.1's local workaround is **removed** by this item rather
  than left as belt-and-braces: two mechanisms for one bug is how one of them
  rots unnoticed.
- **2026-09-15.** Landed in 19O rather than inside a 19P rung — 19P re-houses
  controls and this fixes a bug older than it, and bundling them would put an
  unrelated fix in a feature PR (`CLAUDE.md`, Working approach).

### Blast radius (measured)

At `820d5d6`:

- `grep -n "tbody.children" app/web/templates/base.html` → **1** (`:4363`), the
  only place rows are collected for sorting.
- `grep -rln "data-rrw-sortable" app/web/templates` → **10** files; `grep -rln
  "session-expander" app/web/templates` → **4**. The intersection is **three**
  pages that both sort and inject: `sessions_list.html`,
  `sessions_archived.html`, `session_reviewers.html`. Each carries exactly one
  `rrw-rows` tbody. The other seven sortable tables inject nothing and are
  unaffected.
- `grep -c "rrw:sorted" sessions_list.html sessions_archived.html` → **0 / 0**:
  neither lobby page re-anchors after a sort today, which is the live bug.
- `grep -n 'closest(".rrw-sort-btn")' session_reviewers.html` → **1**
  (`:850`), the local workaround this item deletes.
- Tests: `grep -c "def test" tests/unit/test_lobby_row_selection.py` → **14**,
  `tests/integration/test_setup_tables_sort.py` → **13**. Neither exercises
  sort-with-a-selection — the combination is exactly what nothing covers.

### PR ladder

One slice. The fix is one function plus one listener per owner, and splitting
it would leave a dispatched event with nothing listening.

1. **`_rrwApplySort` drops and signals; the three owners re-anchor.** Removes
   19P.1's local workaround in the same slice, since it becomes a second
   mechanism for a fixed bug. Must not change the sort order itself, and must
   not touch the seven tables that inject nothing.

### Definition of done

- `_rrwApplySort` removes `.session-expander` children before stamping
  `rrwOriginalIndex`, asserted on the shipped source.
- A sort with rows selected leaves the panel anchored to the same row it was
  anchored to before, on the lobby **and** on Reviewers. *No JS runtime in the
  suite, so this is asserted as mechanism — the removal, the dispatch, the
  listeners — and confirmed in a browser against the rendered page, as 19P.1
  rung 1 did for its anchor rule.*
- Clearing a sort restores the server's row order with a panel open, which is
  the `rrwOriginalIndex` half.
- `grep -c 'closest(".rrw-sort-btn")' app/web/templates/operator/session_reviewers.html` → 0.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19O.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Does `sessions_archived.html` need the listener too?** **Yes**, and
   one line covered it: its script carries the same `refreshExpander()`
   entry point as `sessions_list.html`, so both pages take the identical
   listener.

### Status

**Closed 2026-09-18, one slice as planned.** `_rrwApplySort` drops every
`.session-expander` before it collects rows or stamps `rrwOriginalIndex`,
then dispatches `rrw:sorted` after the rows land; three of the seven
injecting pages re-anchor from it, and 19P.1's workaround on Reviewers —
the only page that had one — is gone in the same commit.

**Decisions confirmed at build.** Warn rather than preserve the node on
an unsaved lobby edit, and narrow the claims rather than migrate the
remaining three pages here (author, 2026-09-18). The rest of the
migration is 19O Item 6.

**Divergences from the plan, all measured:**

- The ladder said *three* injecting pages, measured at `820d5d6`. At
  build time it was **seven**, six of them sortable — 19P.2-3 and 19P.5
  had taken the expander further. *A measurement carries its commit for
  exactly this reason.*
- `spec/ui_elements.md` has no `[data-rrw-sortable]` entry to put the
  rule beside, and the `sessions_overview` waiver reasoned from the
  panel entry when the **Sortable columns** bullet was what needed the
  line. Waiver replaced with a bullet.
- Two files joined the manifest at the close: `spec/sort_by_reviewee.md`,
  which `spec/README.md` says owns sort UX, and `spec/sessions_overview.md`
  again for the confirm gate, which post-dated the manifest's revision.
- **The lobby's panel is the only editable expander in the app** — five
  `[data-expander-field]` inputs plus purge and confirm checkboxes — so
  the rebuild this item decided on discarded unsaved work. The gate runs
  on the capture phase ahead of the inline sort handler, and declining
  cancels the sort.

**What the item cost, and why it is worth a line.** Three readers found
three faults of one shape: a check that is silent about what its author
did not think to include. The guard indexed the panel's *selector*
rather than its removal, so a split-statement mutant passed. The dirty
check scanned an opt-in attribute list, so it missed the bulk tag box,
then the purge checkboxes. Each fix was aimed at the instance; the third
was aimed at the class, and now reads every control in the panel.
Verification pointers: `tests/unit/test_sort_drops_injected_panel.py`
and `guide/segment_19O_rosters_and_instruments.md` Item 4's Doc impact.

**Browser half unverified.** No JS runtime in the suite, so the shipped
source is asserted as mechanism; the confirm dialog, the sort badges
after a cancel, and the panel's visible position after an accepted sort
all need the dev slot.

### Out of scope

- **The seven sortable tables that inject no panel.** Unaffected by
  measurement; touching them would widen a bug fix into a sweep.
- **Server-side sorting.** A different design, and not what is broken.
- **19P's re-housing.** This fixes the primitive underneath it; the rungs
  proceed unchanged either way.

### Doc impact

- `spec/ui_elements.md` — the `.session-row-selected` entry describes the injected panel's placement ("**The panel closes the bracket**") without stating what a client-side sort does to it; add the rule that a sort drops and re-anchors it, beside the `[data-rrw-sortable]` entry that owns the sort primitive (Item 4).
- `spec/sort_by_reviewee.md` — § *Shared sort primitive* gains the panel removal and the `rrw:sorted` dispatch; **added at the close**, not named at planning time, and the file `spec/README.md` says owns sort UX (Item 4).
- `spec/sessions_overview.md` — the **Sortable columns** bullet also carries the *"Discard unsaved changes?"* gate, since the lobby's panel is editable and a sort can now be cancelled; **added after the gate was built**, which post-dated this manifest's first revision (Item 4).
- `docs/status.md` — row when the item lands (Item 4).

- `spec/sessions_overview.md` — the **Sortable columns** bullet gains the sort-drops-and-re-anchors line, pointing at `ui_elements` for the mechanism (Item 4). *The plan waived this file on the grounds that its **panel** description states no sort interaction. True of the panel entry, and beside the point: the lobby's own sortable-columns bullet is where a reader meets sorting, and it said nothing about a selection surviving one.*

---

## Item 3 — A sent invitation makes the roster un-replaceable

### Opportunity

Re-uploading a reviewer roster over one whose invitations have been **sent**
raises `sqlalchemy.exc.IntegrityError: FOREIGN KEY constraint failed` on
`DELETE FROM invitations`, reaching the operator as an unhandled 500.
Reported from use; reproduced on `main` at `9866b28`.

`email_outbox` carries FKs to `reviewers.id` and `invitations.id`
(`email_outbox.py:50`, `:53`), neither with `ON DELETE` nor cleared first. Deleting
a `Reviewer` cascades `Reviewer.invitations` (`delete-orphan`), emitting
`DELETE FROM invitations` while outbox rows still reference them.

Four paths, measured — every one that deletes a reviewer:

| path | no invites sent | invites sent |
|---|---|---|
| `POST /reviewers/import` (replace) | 303 | **IntegrityError** |
| `POST /quick-setup/reviewers` | 303 | **IntegrityError** |
| `POST /reviewers/delete-all` | 303 | **IntegrityError** |
| `POST /reviewers/bulk-delete` | 303 | **IntegrityError** |
| `POST /reviewees/import` (control) | 303 | 303 |

Reviewees are unaffected: `email_outbox` has no `reviewee_id`. **No data is
lost** — the transaction rolls back whole, roster and assignments intact.

*Why it reads as "only when assignments exist":* `generate_invitations` targets
only reviewers that have assignments (`invitations.py:63`), and outbox rows are
written when an invitation is **sent** (`:287`, `:540`). No assignments → no
invitations → no outbox → the upload works.

**Not a dialect gap** — `app/db/session.py` enables `PRAGMA foreign_keys` and the
test engine imports it, so SQLite and Postgres fail alike. The suite is green at
3,948 because no test builds an outbox row then deletes a reviewer.

### Decision

One helper in `app/services/invitations.py` — the only module that writes
`EmailOutbox` rows — nulling both FKs for the reviewers about to be deleted.
Called from all four delete paths **and** from `session_purge`, which already
does the same unlink inline (`session_purge.py:65-71`) with a comment naming
the hazard.

*That inline copy is why this bug exists*: the knowledge lived in one path and
did not travel. Switching it to the helper is in scope for that reason — one
place knows, so a fifth path cannot repeat it.

**Rejected: `ON DELETE SET NULL` on the two FK columns plus `passive_deletes`.**
More robust — a new call site could not forget it — but it needs an Alembic
migration altering two FK constraints, surviving `downgrade base + upgrade head`
on Postgres, and `CLAUDE.md` names index/FK name mismatches between upgrade and
downgrade as a trap that has already bitten this project. Wrong risk for a bug
fix. Recorded as the permanent answer if a fifth path appears.

### Semantics

- **Orphaned outbox rows survive.** The row is already self-contained: `to_email`,
  `subject`, `body`, `sent_at`, `backend_message_id` and `delivered_at` are
  denormalised onto it, so no sent email depends on the reviewer row.
- **`reviewer_id IS NULL` is the defunct marker**, with `sent_at IS NOT NULL`
  separating a real send from a queue entry that never went. No new column.
- **`status` is not overloaded.** It means delivery state, and its vocabulary is
  the closed `EMAIL_OUTBOX_STATUSES` pinned by
  `tests/integration/test_email_outbox_schema.py` — a fifth `"defunct"` member is
  a schema change with a test behind it, to say what two existing columns
  already say.
- **Queued rows are unlinked too, not deleted.** Nothing dispatches them —
  `email_send.py` says so in its own docstring and no worker selects
  `status == "queued"` — so an unlinked queue entry is inert. One rule, no
  sent-vs-queued branch.
- Both FK columns are already `nullable=True`, and both live consumers
  (`views/_invitations.py:91`, `views/_setup.py:204`) already filter
  `reviewer_id.is_not(None)`. The null state was designed for.

### Judgment calls — decided

- **2026-09-14.** `session_purge` switches to the helper rather than keeping its
  working inline copy — author's call. It is beyond the defect but it is the
  root cause of the defect's shape.
- **2026-09-14.** The three spec corrections ride this item rather than a
  follow-up — author's call. One of them is wrong today, independent of the fix.
- **2026-09-14.** Unlink uniformly rather than branching on `sent_at`. The
  branch would buy nothing while no dispatcher exists, and would be a second
  rule to keep in step.

### Blast radius (measured)

Commands run at `9866b28`:

- Reviewer-deleting call sites: `grep -rn "db.delete(row)" app/services/csv_imports.py` → **2** (`_save:851`, `_delete_all:979`); plus `reviewers_service.delete_selected`.
- FKs onto the roster tables: `grep -rn 'ForeignKey("reviewers.id")\|ForeignKey("reviewees.id")' app/db/models/` → **4** (`assignment.py` ×2, `invitation.py`, `email_outbox.py`).
- Existing unlink precedent: `grep -rn "invitation_id=None" app/services/` → **1** (`session_purge.py:69`).
- Specs describing what a roster delete reaches: `grep -rn -i "cascad" spec/*.md` → 3 that make a claim (below).
- Tests building an outbox row then deleting a reviewer: **0**. That is the whole explanation for a green suite.

### Status

**Closed 2026-09-14.** The ladder held — helper and call sites, then the
specs — but named two artefacts wrongly, left as written and corrected here:
the helper shipped as `detach_outbox`, and the bulk-delete call landed in
`roster_bulk.bulk_delete`, the shared implementation, not
`reviewers_service.delete_selected`.

**The plan's reason for not overloading `status` was false, and a later reader
will re-derive it.** The plan, the spec and the helper docstring all said a
`"defunct"` member would silently move the Setup page's invite summary. It would
not: `views/_setup.py` filters `reviewer_id.is_not(None)` alongside
`status == "sent"`, so the rows that would carry it are already excluded. The
plan contradicted itself — its own Semantics bullet noting both consumers filter
for NULL is the refutation. The decision survives on the closed
`EMAIL_OUTBOX_STATUSES` alone, which is the argument that should have led.

**The belief that caused the bug sat in three places, only one a spec** —
`roster_bulk.bulk_delete`'s docstring used the same "inherited rather than
reimplemented" words `spec/setup_pages.md` did. 19O.1/.2's Doc-impact finding
generalises past `spec/`.

**`session_purge` had no outbox coverage**, so the root-cause call site shipped
untested. Two tests; three mutations, each caught by one.

**Declined:** `spec/sessions_overview.md` specifies no purge modes, so the
unlink is unstated there — a gap predating this item, recorded in
`guide/deferred_consolidated.md` with its trigger.

**Readers.** `diff-reviewer` 5 findings, 4 upheld. `spec-writer` pre-push, fired
on the `spec/` trigger, 5 findings, 3 upheld. **Close pass: 0 new findings, 0
edits** — everything reached the close already caught. First item under the
19O.3 cadence.

### PR ladder

1. **The helper + the four call sites + regression tests.** `detach_outbox_for_reviewers` in `invitations.py`; called from `csv_imports._save`, `csv_imports._delete_all`, `reviewers_service.delete_selected`, and `session_purge` in place of its inline unlink. One regression test per broken path, each with a **sent** invitation in the fixture. Must not touch `spec/`.
2. **The three specs, on the way out.** Must not touch `app/`.

### Definition of done

- Each of the four paths returns 303 with a sent invitation present, asserted per path.
- The orphaned outbox rows survive the delete with `reviewer_id IS NULL` and their `sent_at` unchanged.
- `session_purge` has no inline `invitation_id=None`; `grep -rn "invitation_id=None" app/services/` returns the helper only.
- `spec/setup_pages.md` no longer says a roster delete is inherited from the ORM cascade and not reimplemented.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

None. Both were put to the author on 2026-09-14 and answered: `session_purge`
switches; the specs ride this item.

### Out of scope

- **The DB-level `ON DELETE SET NULL`.** Rejected above; recorded in
  `guide/deferred_consolidated.md` if a fifth path appears.
- **A visible "recipient removed" marker on any page.** Derivable from
  `reviewer_id IS NULL`; nothing asks for it yet.
- **`email_outbox.reviewee_id`.** Does not exist, and reviewees are unaffected.

### Doc impact

- `spec/setup_pages.md` — § *What a delete takes with it* stops presenting the ORM cascade as sufficient, and names the outbox unlink (Item 3).
- `spec/quick_setup_card_spec.md` — § *Cascading effects* adds invitations and outbox rows to what a reviewer replacement reaches (Item 3).
- `spec/email_infra_options.md` — the outbox column table stops giving "system emails" as the only reason `reviewer_id` is nullable, and states the defunct semantics (Item 3).
- `guide/deferred_consolidated.md` — records that `spec/sessions_overview.md` specifies no purge modes, so the outbox unlink is unstated on that surface (Item 3). <!-- cites: spec/sessions_overview.md -->

## Item 2 — The self-review control's heading and live copy

### Opportunity

Item 1's checkbox shipped and the author found two faults on the rendered
page (screenshot, 2026-09-14).

**The copy does not follow the pill.** The label reads *"Exclude if the
**individual** reviewed is the reviewer"* while the Link 3 pill above it
reads **GROUP USING TAGS**. The mode word is rendered server-side from
`_link3_grouped` — the *persisted* `group_kind` — but the pill cycles
client-side in `newModelToggleUnitMode`, which rewrites the pill label, the
builder's dimming and the hidden `link3_mode` input and knows nothing about
the checkbox. So between cycling the pill and saving the card, the control
describes the opposite of what the operator has just selected. Every other
thing the pill governs updates live; this one does not.

**The control has no heading.** It sits under a `.col-divider` with no name,
so what the divider separates is left to inference. Item 1 chose the divider
precisely to say *this is a second thing* — a heading is the other half of
that sentence, and it was not written.

### Decision

**Heading `Self reviews`**, matching the unbold weight of the three Link
labels — the card's bold is reserved for its own title
(`spec/instruments.md` § *Instrument assignment rule + Unit of review*).

**The mode word is rewritten by the pill handler**, from a `data-` attribute
on the label so the two spellings live in one place. Rejected: recomputing
the copy from `link3_mode` on submit (the operator would still read the
wrong sentence while deciding), and dropping the mode word for something
mode-neutral — the author's ruling is that the copy names what is dropped,
and a group and an individual are different things to drop.

**Group copy is the author's wording** (2026-09-14): *"Exclude if the
reviewer is in the group being reviewed"* — not a substitution into the
individual sentence. *The reviewer is in the group* is the actual test on a
grouped instrument, and the Item 1 phrasing (*"the group reviewed is the
reviewer"*) says something that cannot happen.

### Semantics

- **Two whole sentences, not one with a swapped noun.** They differ in
  structure, so the handler swaps the sentence.
- **The `not_set` pill state reads as individual.** `link3_mode` already
  submits `individual` for `not_set`, so the copy follows the value that
  would be saved rather than inventing a third wording.
- **No behavior change.** Copy and a heading; the flag, its storage and its
  effect are Item 1's and untouched.

### Judgment calls — decided

- **Rewritten by the existing Link 3 handler, not a new listener**
  (2026-09-14). That handler already owns every live consequence of the
  pill; a second listener on the same event is a second thing to keep in
  step.

### Blast radius (measured)

Measured 2026-09-14 at `8fc0c172`.

```
grep -c "exclude_self_reviews" app/web/templates/operator/instruments_index.html   # 2
grep -rln "Exclude if the" app/ spec/ tests/ --include=*.py --include=*.html --include=*.md  # 3
```

### Status

**Closed 2026-09-14.** One PR for the item, one for the author's follow-up.
Intended versus done:

- **Both faults were as diagnosed**, and the first had the cause the
  screenshot implied: the copy was server-rendered from the persisted
  `group_kind` while the pill cycles client-side.
- **The follow-up added two clearing rules** the item had not anticipated,
  on the author's ruling: the control hides *and* clears while any Link is
  `Not set`, and clears when Link 3 moves individual → group. Both enforced
  server-side on save with the client clearing at the same moment — the
  visible half and the durable half, neither alone.
- **The reverse transition needed no rule, and the author said why**: the
  pill cycles `not_set → individual → group → not_set`, so it cannot reach
  individual *from* group without passing through `not_set`, which clears on
  the way. I had filed this as an open question; the UI had already answered
  it. That makes the cycle's shape load-bearing, so it is pinned by a test
  rather than left to memory: **a cycle that ever allows the direct move
  needs a rule in `resolve_exclude_self_reviews`**, and the test says so.
- **The guarantee was partial until the close pass said so.** Session-config
  import writes the column straight from the CSV while the instrument rows
  carrying `band1_touched_links` arrive from a different part of the bundle,
  so an import could store a flag the UI then hides — invisible *and* in
  force. The first rule now runs at the end of the import apply too
  (`clear_unsettled_exclude_self_reviews`). A clone needs no guard: it
  copies an existing pair atomically.
- **Two spec drifts, one made here and one inherited.**
  `spec/assignments.md` still quoted the wording this item replaced, so the
  file contradicted the one it links to; `spec/settings_inventory.md` still
  called the column *vestigial* — untrue since Item 1 rung 1, and
  contradicting `spec/roundtrip_coverage.md`, which that item *did* fix.
  Both are the same miss: *Doc impact* enumerating the specs the behavior
  touches rather than every spec that describes the thing.
- **Verified on the dev slot** (author, 2026-09-14). The one gap every PR
  body in this item declared — no browser harness exists here, so the live
  copy swap and the hide-on-unset were argued from structure plus
  server-render assertions — is closed by having looked.

**The lesson this item kept teaching, at both rounds:** *scope first, assert
second.* A copy assertion passed vacuously by reading markup that carries
both sentences as attributes; narrowed to the text, it then failed for
reading the **first** instrument card rather than the one under test — the
same trap as Item 1 rung 2, in the same file. One `_instrument_card` helper
now, whose own end bound was itself wrong (it matched the card's
`instrument-delete-N` form) until the close pass caught it.

**Every rule here is mutation-checked — including, now, the import guard.**
The compaction had generalized two carefully-scoped claims ("both fixes",
"all three rules") into an unqualified "every rule", which overclaimed for
`clear_unsettled_exclude_self_reviews`: it was added *by* a close pass and
never mutated. Rather than narrow the sentence back, the check was run —
under-fire and over-fire, each caught by exactly the test that should.
*The compaction introduced the one claim in this block that was not true
when written*, which is the item's own defect pattern arriving in the
record of the item.

### PR ladder

One PR: heading, both sentences, the handler rewrite, and its tests.

### Definition of done

- The heading `Self reviews` renders above the checkbox.
- Cycling the pill to *Group using tags* rewrites the copy without a save,
  asserted against the handler's own contract.
- A grouped instrument renders the group sentence on load; an individual or
  unset one renders the individual sentence.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

None.

### Out of scope

- **The Link 3 pill's own three-state cycle.** Unchanged.
- **Whether the control belongs in Link 3 at all.** Settled in Item 1 by the
  author: it is there for space, and the divider plus this heading say so.

### Doc impact

- `spec/instruments.md` — § *Self-review exclusion* gains the heading and both label spellings (Item 2).
- `spec/assignments.md` — § *Suppressing self-reviews* stops quoting the replaced wording and points at the spelling's owner (Item 2).
- `spec/settings_inventory.md` — the `exclude_self_reviews` row stops calling the column vestigial and states the import-time clear (Item 2 follow-up).

## Item 1 — Exclude self-reviews from the Link 3 column

### Opportunity

`spec/assignments.md` § *Self-review policy* names two supported ways to
suppress self-reviews. The first — *"Add a Link 2 (or Link 1) rule like
`reviewee.email IS DIFFERENT FROM reviewer.email`"* — **no operator can
reach.** `views/_instruments.py::new_model_usable_tags` returns
`tag1`/`tag2`/`tag3` for `reviewer` / `reviewee` / `pair_context` and no
email slot; the general Rule Builder that once offered the full grammar is
retired, route and template. The engine accepts `reviewer.email` and
`reviewee.email` (`ALLOWED_PREDICATE_FIELDS`); nothing authors them.
Found by Codex on #2381.

**It was designed away on a premise that no longer holds.** The 13A picker
omitted email deliberately — *"operator-authored rules don't reach for
email comparisons (the engine's `excludeSelfReviews` desugar handles that
case implicitly)"* (`app/web/views/_rule_builder.py`). Both halves then
went a day apart, in opposite directions: the picker retired **2026-05-25**
(`5aa0c9ed`), `excludeSelfReviews` was pinned `False` **2026-05-26**
(`8f8d336d`) — the same commit that wrote the policy naming the
now-unreachable rule. The only surviving affordance is post-generation:
materialize every self-review row, then deactivate it.

**But one objection is live, not archaeological**, and is the real reason
to answer rather than the retired comment above. `_band1.py` enforces it on
every Band 1 save (`:146-167`, and the seed at `:426-440`): *"The
per-instrument Self review toggle on the Assignments page is the sole
include / exclude surface; baking exclusion in at the rule-set level would
silently disable that toggle."*

### Decision

**A per-instrument flag, honored at materialization** — at the point in
`assignments/_generate.py:337-351` that already decides `pair_include`.

Read that branch precisely: `pair_include` is **not a skip**. It is the
value written to `Assignment.include` (`:450`), so today a self-review pair
on a session with `self_reviews_active=False` still gets a row. Honoring
the flag means **omitting the pair from `new_pairs`** — one `continue` —
which is a different edit with a consequence the skip framing hides, and
that consequence is in *Semantics*.

Why this is buildable where the banned flag is not: `_generate.py`
**already computes whole-group `is_self`** before that branch —
`self_review_groups` (`:314-332`) marks each group whose reviewer is one of
its own reviewees, built from the engine's full `result.pairs`. **Group
correctness is free**; nothing new expresses it.

**Answering `_band1.py`.** It is right that silently disabling a working
toggle is a regression. The toggle is not disabled here so much as *made
inapplicable*, and the cell must say so — "Excluded by rule" is the
objection's remedy, not a nicety. **If rung 4 slips, rung 3 must not
land.**

Rejected:

- **Email fields in the picker plus a pair predicate.** Pair-level, so on a
  group-scoped instrument it drops `(R, R)` and leaves the rest — worse than
  one member short, since `classify_self_review` identifies a self-review
  group *by finding that row* (`_self_review.py:122-128`), so the remainder
  stops counting as self-review at all.
- **`RuleSetOptions.excludeSelfReviews`, or the still-live
  `override_exclude_self_reviews` channel** (`_generate.py:304` →
  `engine.py:150-154`, resolving ahead of the pinned option). Both are the
  *desugar* stage, which carries both recorded hazards: it drops pairs
  **before** group composition (under-counting by one) and it is invisible.
  Honoring the flag after the fan-out avoids the first; rung 4 the second.

### Semantics

- **It sits in the Link 3 column for space, not because it belongs to the
  unit of review** (author, 2026-09-14). A **horizontal rule** below the
  Link 3 controls separates them, so the checkbox reads as a second thing
  in the same column rather than a third unit-of-review state. The rule is
  a `base.html` class, not an inline style — the column's existing 1px
  vertical separator (`--border-default`) is the sibling to match.
- **Default off**, and **takes effect at Generate** — Regenerate is the only
  write site for `Assignment` rows, so ticking the box leaves existing rows
  alone until the next Generate. The card says so.
- **Group mode drops the whole group**, individual mode the pair, both from
  the existing `is_self`.
- **Ticking the box after responses exist deletes them.** A pair dropped
  from `new_pairs` lands in `to_delete`, and `_materialise_one_instrument`
  deletes each row's `Response` rows before the row (`:434-438`). This needs
  no new guard: the diff already counts `responses_deleted` (`:369-378`) and
  the Prepare confirm card already spells it out
  (`next_action_card.html:90-98`). Rung 3 asserts it rather than adding to
  it.
- **A non-email reviewee identifier is never a self-review**
  (`is_self_review` returns `False` with no `@`), so the flag cannot drop an
  anonymous reviewee's row — the copy says *reviewed is the reviewer*, which
  is identity matching, not name matching.
- **The excluded rows read as excluded.** On Assignments → per-instrument
  status the **Self review** cell renders **"Excluded by rule"** in place of
  the count pill (author, 2026-09-14). Today it is a pill of
  `self_review_total` plus the include checkbox, the latter gated on
  `> 0` (`session_assignments.html:84-86`) — so a flagged instrument would
  otherwise read as a bare `0`, indistinguishable from a roster with no
  self-pairs. The checkbox needs no separate suppression; its guard already
  hides it. *None exist* and *none kept* must not share a rendering.

### Judgment calls — decided

- **Per-instrument, not per-session** (2026-09-14). The rule set and Link 3
  are both per-instrument; a session flag reinstates what 15B retired.
- **Reuse `SessionRuleSet.exclude_self_reviews`; add no column**
  (2026-09-14, corrected after reading the code). The column already exists
  (`app/db/models/session_rule_set.py:63`, `default=True`), is per-instrument
  in practice — Band 1 auto-manages one rule set per new-model instrument
  (`_band1.py:426`) — and already round-trips through session config IO
  (`_serialize.py:544`, `_apply_rule_set.py:47`) and the by-instrument
  extract (`by_instrument_extract.py:332`). The work is **removing the
  normalization**, not adding storage.
- **The checkbox writes no predicate** (2026-09-14). It is not sugar over a
  rule the operator could have written, so composing one would misdescribe
  it in the readback.
- **Turning the flag ON materializes an empty rule set; turning it OFF with
  no rule set is a no-op** (2026-09-14, rung 2). Band 1 only creates a
  `SessionRuleSet` once a Link 1 / Link 2 rule exists, so an untouched
  instrument has nowhere to store the flag. An empty rule set is
  output-identical to the synthetic Full Matrix schema, so this costs no
  assignment row — verified: the `revision_seed` difference is read only
  inside the quota-rule loop, which an empty rule set never enters. Not
  creating a row for an OFF write keeps untouched instruments clean, since
  `False` is the default and records nothing.
- **The checkbox label follows the Link 3 mode** (2026-09-14, rung 2):
  "individual" or "group", so the copy names what would actually be
  dropped.

### Blast radius (measured)

Measured 2026-09-14 at `8669849a`, before the first slice.

```
grep -rn "is_self_review(" app/ --include=*.py | grep -v "def " | wc -l      # 9
grep -rn "self_reviews_active" app/ --include=*.py --include=*.html | wc -l  # 21
grep -rln "_link3_\|link3_mode" app/web/templates | wc -l                    # 1
grep -rln -i "self-review\|self_review" spec/ docs/ | wc -l                  # 18
grep -rln "self_review\|self-review" tests/ --include=*.py | wc -l          # 51
```

Of the 18 spec/docs hits, the three this item commits to are in *Doc
impact*. The **51** test files are the figure to respect: self-review
classification is the engine's most cross-cut invariant, guarded by
`verify_self_review_classification` as a continuous gate.


*Corrected 2026-09-14 (`spec-writer` on `bb75e366`): first written as 10
and 106. The test command omitted `--include=*.py` and counted 55
`__pycache__/*.pyc` alongside the 51 real files — a guardrail is the wrong
place to overstate by double.*

### Status

**Closed 2026-09-14**, four rungs, four PRs. Intended versus done:

- **The mechanism landed as designed** and its load-bearing claim held under
  verification: `_diff_one_instrument` already computes whole-group `is_self`
  from the engine's full `result.pairs` before the `pair_include` branch, so
  honoring the flag there gives whole-group correctness for free, and a pair
  omitted from `new_pairs` is not re-added downstream.
- **Rung 1 was one deletion, not the two the ladder named, and the second
  would have been a bug.** Storage already existed
  (`SessionRuleSet.exclude_self_reviews`) and was being force-normalized to
  `False` on every Band 1 save — a heal for pre-#1452 rows that migration
  `d2e4f6a8c1b3` had already completed, so the re-write only discarded
  operator intent. But the ladder also said to drop the
  `exclude_self_reviews=False` seed: the mapped column is `default=True`, so
  that would have inverted the default for every new instrument, silent until
  rung 3. The seed stays.
- **Rung 2 found a hole in the storage decision.** Band 1 creates a rule set
  only once a Link rule exists, so an untouched instrument had nowhere to put
  the flag — and is the likeliest to want it. Turning it on materializes an
  empty rule set, verified output-identical to the synthetic Full Matrix
  schema; turning it off with no row is a no-op. Also: `base.html` is a
  generated-tool source, so the new `.col-divider` class desynced
  `tools/theme_*.html`.
- **Rung 4's premise was slightly wrong and the fix is better for it.** The
  plan assumed the Self review count is always `0` when the flag is set.
  Between ticking the box and the next Generate it is not, so the cell reads
  "Excluded by rule" only once the count is actually `0`; a
  flagged-but-not-yet-regenerated instrument keeps its real count and its
  toggle, which are still true and still actionable.
- **`spec/ui_elements.md` added to *Doc impact* at build.** The plan named the
  specs the behavior touches and missed the one the *primitive* touches. At
  close, `spec/roundtrip_coverage.md` joined it for the same reason — the
  column was described there as "vestigial", true until rung 3 made it govern
  generation.
- **The Band 2 preview diverged, was reported, and the author closed it.**
  `find_sample_in_scope_reviewee` built its schema from the live Link 1 /
  Link 2 fields and never read the column, so an instrument with the checkbox
  set could still preview a sample in which the reviewer reviews themselves.
  Found by the close pass and raised rather than fixed, since rung 3's scope
  rule forbids touching that function and closing the gap means deciding what
  the preview is *for*. **Author's ruling 2026-09-14: "the preview should
  follow the rule too."** Implemented the same way the generator does it — by
  filtering the engine's *output*, whole group at a time, never by flipping
  `excludeSelfReviews`, which would drop pairs before group composition is
  known and reintroduce the exact hazard the three layers exist to prevent.
  A grouped instrument whose only group is the reviewer's own now previews
  empty rather than showing a row Generate would not produce. **The first
  implementation keyed the groups wrongly** and the close pass reproduced
  it: it reused this function's reviewee-only boundary list, which is
  correct for the member-id partition and wrong here, so a
  pair-context-only boundary dropped the test to pair level while the
  generator still grouped — the preview offering a teammate Generate was
  about to exclude, which is the same class of divergence the ruling was
  meant to end. Both now call `group_key_for_pair` over the full boundary.
  *Two keyings of one concept is one too many.*

- **Two real defects came from the review bot after the close pass, and
  both were in the mechanism rather than the prose.** *(a)* Self-review
  groups were detected over `result.pairs` — the survivors — so a Link rule
  that filtered the `(R, R)` pair out of the fan-out left the group with no
  self-review marker at all, and the reviewer went on reviewing their own
  group with the checkbox set. Membership is a fact about the **roster**;
  the rules decide only which rows survive. Fixed at the root, which also
  fixes the same blind spot in the pre-existing `self_reviews_active` path.
  *(b)* "Excluded by rule" was driven by configuration alone, so a roster
  with no self-review candidate read as an exclusion that never happened —
  the same ambiguity the cell exists to remove, one step over. It now
  requires evidence (`InstrumentReconcileState.self_reviews_excluded`).
  Also: the dry-run's *eligible* figure and the audit event's pair count
  were still taken from the pre-exclusion fan-out, advertising rows Generate
  would never create.

**The defect pattern, stated because it repeated at every rung:** every error
was in prose *about* the code, never in reading what the code does. A
`server_default` cited on the wrong table, read off a grep hit's neighborhood
instead of its enclosing function. A test-file count doubled by `__pycache__`.
A "lands inert" claim contradicted by this plan's own judgment call two
sections above it. A spec drift reported in the prior session that was not
real. A rule set that could be created with no `.created` audit event. Four
`spec-writer` passes caught them; each was verified at `file:line` before
being fixed. *A row-scoped fix is not a claim-scoped fix.*

### PR ladder

1. **Unpin the existing flag.** No migration: drop the
   `exclude_self_reviews` re-normalization at `_band1.py:146-167` and the
   `exclude_self_reviews=False` seed at `:441`, so the column the model
   already carries stops being forced. Lands inert — nothing writes it yet
   and the engine still ignores it (`_session_rule_set_to_schema` hardcodes
   `excludeSelfReviews=False`). The PR body says what the column now means.
2. **The control.** Horizontal rule below the Link 3 controls, then the
   checkbox beneath it, reading and writing the column. Still no engine
   change; the PR body says so.
3. **Honor it at materialization.** The `_generate.py:337-351` loop omits
   the pair from `new_pairs` instead of writing `include=False`. Tests:
   individual, group, non-email identifier, a regenerate flipping the flag
   both ways, and the `responses_deleted` count on a tick-after-responses.
4. **Make the exclusion visible** — the "Excluded by rule" cell, per
   *Semantics*.

Rung 3 must not touch `RuleSetOptions`, `_session_rule_set_to_schema` or
`find_sample_in_scope_reviewee`. The three layers stay.

### Definition of done

- `SessionRuleSet.exclude_self_reviews` is no longer force-normalized, and
  a Band 1 save round-trips a `True` through config export/import
  unchanged.
- With it set, `replace_assignments` writes **no** self-review row: the
  `(R, R)` pair on an individual-scoped instrument, every member row of the
  group on a group-scoped one.
- `verify_self_review_classification` reports no drift after a regenerate
  with the flag set.
- A reviewee whose identifier is not an email is unaffected, asserted.
- The per-instrument **Self review** cell reads **"Excluded by rule"** when
  the flag is set, and a bare `0` when the roster simply has no self-pairs —
  asserted on both.
- `spec/assignments.md` § *Self-review policy* lists the shortcut and no
  longer names an affordance no operator can reach; its "enforced in three
  layers" paragraph is reconciled with the flag now being honored.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**How the excluded rows are shown.**~~ **Answered by the author
   2026-09-14: "Excluded by rule", replacing the count pill.** See
   *Semantics*.
2. ~~**Whether Link 3 is the right home**~~ **Answered by the author
   2026-09-14: yes, purely for space.** It is not a unit-of-review setting
   and is not presented as one — a horizontal rule separates it from the
   Link 3 controls above. See *Semantics*.

### Out of scope

- **Adding email to the Link 1 / Link 2 picker vocabulary.** Rejected above
  as a mechanism; out of scope as a change in its own right.
- **Restoring the general Rule Builder.** Retired at Wave 5 Gap 7 with the
  library tier; nothing here argues it back.
- **Changing `RuleSetOptions.excludeSelfReviews`.** The policy stands.

### Doc impact

- `spec/assignments.md` — § *Self-review policy* gains the shortcut as a supported affordance, drops the unreachable Link-rule claim, and reconciles its "enforced in three layers" paragraph (Item 1).
- `spec/instruments.md` — the Link 3 / *Unit of review* material gains the control and its interaction with Generate (Item 1).
- `spec/ui_elements.md` — §10 gains the `.col-divider` primitive the control is separated by (Item 1).
- `spec/roundtrip_coverage.md` — the `exclude_self_reviews` row stops calling the column vestigial (Item 1).
- `guide/deferred_consolidated.md` — the Part A entry is lifted into this plan and deleted (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
