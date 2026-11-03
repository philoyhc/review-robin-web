# Findings — codebase assessment (2026-11-03)

**Found by:** the three reads run beside
`guide/codebase_assessment_03nov.md`: a spec-vs-code audit, a defect read
of the window's `app/`, `cordware/` and `alembic/` changes, and a read of
`cordware/`, `residentialapps/` and `utilityapps/` · **Read at:**
`cc364ed0` (#3566) · **Open:** every row below.

The checklist the fixes work through (standard practice since
2026-11-02). **Nothing was edited by the reads**, and their scratch tests
were not kept: a fix PR writes its own test. Strike a row when it is done,
with the PR that did it, or mark it declined with the reason. Retire the
file to `guide/archive/` when no row is open.

**Ids:** **M** and **L** are defects, medium and low, as the assessment's
§6 numbers them · **D** is spec drift, as its §3 does · **N** is a gap
noted, not a defect. Ids restart per assessment. **Decides:** *code*
means the code is wrong against a spec that is right; *author* means a
choice between fixing the code and changing the contract; *spec* means
the spec is wrong. Line numbers are at `cc364ed0`.

## 1. High

None.

## 2. Medium

- **M1. A directory recheck changes setup without sending a validated
  session back to draft.** `app/services/directory_recheck.py` `recheck`
  (lines 150–185), from `app/web/routes_operator/_directory.py`. Every
  other setup write calls `lifecycle.invalidate_if_validated`; the recheck
  binds `directory_object_id`, runs
  `assignments.recompute_self_review_classification` (which can flip
  `is_self_review` and switch `include` off) and, under symmetric review,
  `symmetric_review.sync_reviewees_from_reviewers`, and does not. A
  validated session whose reviewer `e0123456@…` and reviewee
  `jane.tan@…` are unbound: rechecking both binds them, the assignment
  becomes a self-review on an instrument with `self_reviews_active=False`,
  its `include` goes off, and the session stays `validated`. The same pass
  runs on activated sessions (allowed by 20I's ruling), where it switches
  off included assignments mid-review. *CONFIRMED by a scratch test.*
  Author: invalidate a validated session when a recheck binds; and rule
  whether an activated session's recheck may move includes (skip the
  recompute there, or refuse Reviewers and Reviewees past validated).

## 3. Low

- **L1. A Reviewers recheck under symmetric review can 500.**
  `directory_recheck.py:178` calls `sync_reviewees_from_reviewers(db,
  locked)` with no `acknowledged_loss`, and the route does not catch
  `GroupAnswersWouldClear`; `app/web/error_handlers.py` has no handler for
  it. A drifted mirror (`reviewees.mirror_drift`) whose sync would clear
  answered group responses gives a 500, not the ask other reviewer writes
  show. *PLAUSIBLE, traced.* Code: catch it and roll back with a banner, or
  limit the recheck's sync to the directory columns. Likely lands with M1.
- **L2. A blocked submit leaves the countdown's flag set.**
  `app/web/templates/operator/partials/_directory_countdown.html`,
  `submit()`: `counted = true` precedes `requestSubmit`; if the browser's
  validation blocks the submit, every later submit on the page (both
  forms share the flag) skips the count. The server still checks every
  address, so this costs speed only. *PLAUSIBLE, traced.* Code: one flag
  per form, reset when the submit does not navigate.
- **L3. The Email Address Checker's preview 500s on a huge column
  index.** `utilityapps/email_check/routes.py:117`: `int(chosen)` on a
  `column` of more than 4,300 digits raises (Python's digit limit); the
  spec (`utilityapps/spec/email_check.md`, "Preview") says a non-index
  column is ignored. Super-admin only. Lines 85 and 197 parse
  `Content-Length` the same way. *CONFIRMED.* Code: bound the length
  before `int()`.
- **L4. The Residential preview list drops `<address>.`**
  `residentialapps/web/pages.py:45` `_first_address` strips angle
  brackets before trailing punctuation, so `- <jane@example.edu>.` leaves
  `jane@example.edu>` and names nobody; the spec allows both. Fails
  closed. *CONFIRMED.* Code: `rstrip(".,;:")` before `strip("<>")`.
- **L5. Residential's web log lines are stamped `cordware`.**
  `residentialapps/web/pages.py:17` logs under `residentialapps.web`,
  which no registry prefix covers, so `ApplicationFilter` stamps its two
  lines (the preview list's unreadable warning and its count) with
  `application: "cordware"` — the mis-stamp
  `residentialapps/spec/applications.md:229` says Residential's own logger
  will prevent, and calls not built. *CONFIRMED by trace.* Author: log
  under an application prefix now, or say in the spec that these two lines
  are stamped `cordware` until the logger lands.
- **L6. A whitespace-only name header reads as a name.**
  `cordware/identity.py`, the simple-header branch: a blank
  `X-MS-CLIENT-PRINCIPAL-NAME` counts as present and becomes `name="   "`,
  unlike the stripped id and email. Easy Auth never sends it. *CONFIRMED.*
  Code: one `.strip()`.

## 4. Spec drift

DRIFT_ROWS

## 5. Noted, not defects

- **N1. The public repository names the institution in places.**
  `residentialapps/docs/residentialapps_email_identity_matching.md:98–105`
  (a firewall issue by institution, the private repository's paths, the
  deployment's managed-identity state) and
  `utilityapps/docs/email_address_checker_functional_spec_v0.1.md:114,
  122, 194, 201` ("NUS tenant", "NUS directory"). Other files name it too
  (`rrw_design_rationale.md`, parts of `guide/`, `applydesk/docs/`), so it
  may be accepted; it conflicts with `cordware/settings.py`'s note that the
  institution's name lives only in the private deployment. Author: rule
  whether naming the institution is acceptable, and if not, which files.
- **N2. The Graph transport follows redirects with its bearer header.**
  `cordware/graph.py` `urllib_transport` uses urllib's default redirect
  handler, which re-sends `Authorization` across hosts. Graph `/users`
  does not redirect, so nothing is exposed today. Code, optional: a
  no-redirect opener.
- **N3. The Checker's `/check` and `/preview` take cross-site form
  posts.** Unlike `/lookup` (JSON only). A cross-site post can make the
  super-admin's browser run Graph lookups of chosen addresses; the result
  shows only to them, so the cost is rate usage. Unspecified. Author.
- **N4. Support Logs' consultation check takes student emails in a GET
  query.** `/consultation/check` puts them in access logs and history.
  Sample data today; worth a POST when wired. Noted for the wiring.
