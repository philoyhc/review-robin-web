# Segment 21F — Roster addresses resolved through the directory

**Opened:** 2026-10-31 · **Theme:** a roster address is resolved through Graph at upload, so a person listed by sign-in name (UPN) or by mail is matched by their directory account, never by an address another account may share · **Related:** `cordware/spec/identity.md` ("Graph"), `spec/audience_and_identity_model.md`, `spec/participant_model.md`, `utilityapps/spec/email_check.md` (the lookup and classification this reuses), `residentialapps/docs/residentialapps_email_identity_matching.md`

## Opportunity

At the institution a person's sign-in name and mail address differ. Review Robin matches a signed-in person to a roster on the mail only: every gate compares `normalize_email(user.email)` with the row's address. A roster written with sign-in names, which is what many institutional exports hold, matches nobody. The person signs in and is told they have no access.

Graph from application code is proved (Cordware's first release, 2026-10-31). The Email Address Checker resolves staff and student addresses given by UPN or by mail. Its `USE_PRIMARY` result is exactly "the sign-in name was given; the mail is …".

## Decision

**Resolve each roster address through the directory at upload, store the account with the row, and match a signed-in person by account** (author, 2026-10-31).

- **At the upload preview,** each distinct address is looked up with the checker's query and classification, `mail eq … or userPrincipalName eq …`, on the uploading operator's delegated token. The preview counts each outcome:
  - resolved by mail;
  - resolved by UPN, with the mail shown;
  - not found;
  - ambiguous;
  - not checked.
- **On save,** a resolved row stores the account's object ID, mail and UPN beside the address as written. Any other row stores none of them.
- **At sign-in,** a row that carries an object ID matches only the person whose principal ID is that object ID. A row without one matches by mail, as today.
- **The lookup and classification move into `cordware/graph.py`,** so RRW and the checker share one implementation. RRW cannot import `utilityapps`.

**Rejected:**
- *Match an entry against the signed-in person's mail or UPN at sign-in* (this plan's first draft, `#3424`). Entra does not keep one account's mail distinct from another account's UPN. `cordware/graph.py`'s `FAKE_USERS` models exactly that, with `office@` as one person's mail and another's UPN. Under that rule, an entry meant for one account would admit the other (Codex, `#3424`). The directory sees the collision as `AMBIGUOUS`; a sign-in cannot.
- *Gate UPN matching behind a deployment setting.* Its safety would rest on a claim about the tenant that nothing checks.
- *Mail-only, with the checker as the fix.* It leaves every operator to clean every roster by hand.

## Semantics

- **Outcomes** follow the checker's (`utilityapps/spec/email_check.md` "Classification"). A row is bound to an account only for `OK`, `USE_PRIMARY` or `FOUND_NO_PRIMARY`.
  - `AMBIGUOUS`, `NOT_FOUND`, `ERROR` or *not checked* bind nothing, and the row keeps today's mail matching.
  - External reviewers, guests and anonymous reviewee identifiers are unaffected: they never resolve.
- **The token.**
  - No delegated token, or fake auth off on a local run, means nothing is checked. The preview says so and the import proceeds as today.
  - With fake auth on, the lookup uses `FakeDirectory`.
  - The lookup runs within the preview request under a time budget, as the checker's plain post does. Whatever is not finished is *not checked*.
- **Matching** applies to the reviewer, reviewee and observer gates, the reviewer dashboard, invitation acceptance and `participants.disclosable_roles`:
  - with an object ID: `row.directory_object_id` equals the **current request's authenticated principal ID** (`get_current_user().principal_id`, the Entra object ID Easy Auth supplies), compared case-insensitively;
  - without one: mail, as today.

  The comparison is never with the persisted `users.external_principal_id`. `users.find_signed_in_user` can return a row by email whose stored principal ID belongs to an earlier holder of that address, and a bound row must not follow the address to a new account (Codex, `#3424`). A request with no principal ID, or the fake user's, binds to nothing.

  Gates that receive only a `User` row also take the authenticated identity, so the principal ID reaches every comparison.
- **Unchanged:**
  - the address as written, which is what the Setup pages show;
  - the allowlists, which have no upload step: `OPERATOR_EMAILS`, `SYS_ADMIN_EMAILS` and `SUPER_ADMIN_EMAILS` stay mail-only;
  - Residential's matching, which has its own plan.
- **One person across rosters.** Wherever two roster rows are asked whether they are the same person, two rows bound to the same object ID are the same person. Otherwise the address decides, as today. Without this, Jane listed as a reviewer by UPN and as a reviewee by mail would review herself as a peer (Codex, `#3424`). One helper (`participants.same_person`) decides, and every such comparison uses it:
  - self-review: `assignments/_self_review.py` and `rules/engine.py._is_self_review`, including group membership;
  - the cross-table identity checks: `csv_imports._identity_holders` and `cross_table_identity_conflict`, and `validation._identity_holders_by_email`.
- **Copying a session** carries the stored account fields.
- **The single-row add forms** resolve their one address the same way.
- **An address edit rebinds.** `update_reviewer`, `update_reviewee` and `update_observer` resolve the new address the same way. Without a lookup (no token, or not found) the old binding is cleared, never kept: a row edited from Alice's address to Bob's must not stay bound to Alice (Codex, `#3424`). An edit that leaves the address unchanged, folded, keeps the binding.

## Judgment calls — decided

- **Columns on the three roster tables,** not a shared address table. Each row's binding belongs to that row, and a re-upload replaces it.
- **The object ID binds; mail and UPN are kept for display only.** A changed mail or UPN later does not unbind a row.

## Blast radius (measured)

Taken 2026-10-31 at `2bb3e01`.

| What | Count | Command |
|---|---|---|
| Mail-only matcher sites | 14 in 6 files | `grep -rn "normalize_email(user.email)\|normalize_email(current_user.email)\|disclosable_roles(db, user.email\|_email_in(cfg\.\|is_super_admin(user.email)\|is_super_admin(current_user.email)" app --include=*.py \| wc -l` |
| SQL roster filters on one address | 3 in `services/participants.py` | `grep -n "func.lower(func.trim(" app/services/participants.py` |
| Roster CSV parsers | 3 (`parse_reviewer_csv`, `parse_reviewee_csv`, `parse_observer_csv`) | `grep -n "^def parse_.*_csv" app/services/csv_imports.py` |
| Roster row constructors | 6 (3 single-add services, 3 in `session_clone.py`) | `grep -rn "Reviewer(\|Observer(\|Reviewee(" app/services --include=*.py` |
| Same-person comparisons across rosters | 5 functions in 4 files (`assignments/_self_review.py`, `rules/engine.py`, `csv_imports.py`, `validation.py`) | `grep -rn "def is_self_review\|def _is_self_review\|def cross_table_identity_conflict\|def _identity_holders" app --include=*.py` |
| Roster address edits | 3 (`update_reviewer`, `update_reviewee`, `update_observer`) | `grep -rn "def update_reviewer\|def update_reviewee\|def update_observer" app/services` |
| Held-upload routes | 4 setup modules | `grep -rln "HeldUpload\|held_upload" app/web/routes_operator --include=*.py` |
| Models touched | 3 (`reviewer`, `reviewee`, `observer`) | `ls app/db/models/{reviewer,reviewee,observer}.py` |

## Status

Open. Plan `#3424`, rung 2 `#3425`, rung 3 `#3427`.

Rung 4 split at build (2026-10-31): a roster import has no preview step; it saves on submit and redirects. So:
- **4a** resolves addresses at the import's save, the single add and the edit, with no UI. It stores the account, sends mail to the directory's mail, and records the counts in the import's audit event (`directory_*`).
- **4b** shows those counts on the Setup page, read from the latest import's event. The wording is settled on the page first.

Rung 5, decided at build (2026-10-31):
- **This request's principal reaches the matchers** as `users.signed_in_principal_id`, a plain attribute `get_or_create_user` stamps on the row each request. It is not a column, and never the stored `external_principal_id`. The fake user gets none.
- **One rule:** `participants.Viewer`. A bound row matches only that principal; an unbound row matches by mail. The rule covers the three gates, the chip strip, the dashboard, invitation acceptance and role disclosure.
- **Self-review** (assignments, including group membership, and the rules engine) treats two rows bound to one account as one person.
- **The cross-table name check stays address-based.** It guards two names on one address, and an import's rows aren't resolved until after it runs. A person entered by UPN and by mail under two names is not flagged; self-review and matching still treat them as one.

Rung 5's `diff-reviewer` read of the cumulative diff (`ddb61b2..HEAD`) found no authorization hole. It found 11 items, all handled in `#3430`:
- **Self-review by account, everywhere.** The instrument preview's group lookup and the Full Matrix count still keyed on the address. Both now read `email_identity.same_identity`, as do both self-review tests and `participants.same_person`, its row form.
- **Quick Setup and rehydrate resolve too.** Both saved rosters unbound, and a rehydrate dropped every binding. The plan named only the Setup pages; the ruling "at upload" covers every upload path.
- **Bindings are audited.** `*.created` snapshots `directory_object_id`, and an edit that moves it records it in `changes`.
- **`/me/debug` stamps the principal**, so its back link works for a bound row.
- **One account can hold two rows in one roster** (Jane by mail and by UPN). The gates now take the lowest id, so the choice holds across requests. Refusing such duplicates is an open question.
- Tests added: the reviewer gate, and an edit that moves access from one account to the other.
- Two items are recorded, not changed. The fake user binds nothing, so locally only the unbound path can be exercised; the bound path needs the real tenant. And `cordware/identity.py` reads the email from `preferred_username` when the email claim is absent, so the `office@` protection depends on the tenant issuing that claim.

## PR ladder

1. **This plan.** Prose only.
2. **The shared lookup.** Moves `classify`, `look_up_all` and the outcome shape from `utilityapps/email_check/check.py` into `cordware/graph.py`, and the checker imports them. Must not change the checker's behavior; its tests pass unchanged.
3. **The columns.** Adds `directory_object_id`, `directory_mail` and `directory_upn` on the three roster tables, with a migration portable both ways. They are carried through `session_clone`. No reader yet.
4. **Resolution at upload.**
   - Lands:
     - the lookup in the three preview paths;
     - the preview's outcome counts, with the wording settled on the page first (scaffold);
     - storing the account on save;
     - the single-add forms;
     - address edits rebinding, or clearing the binding.
   - Must not change any gate.
5. **Matching by account.** The 14 sites and 3 SQL filters prefer the object ID, then fall back to mail. The same-person comparisons move to `participants.same_person`. Tests include two negative cases: `FAKE_USERS`' `office@` collision, where the account whose UPN is the roster's mail is not admitted; and a persisted principal ID that differs from the token's, which binds nothing. Last build rung, so `diff-reviewer` reads 2–5.
6. **Close.** `spec-writer` on the doc-impact specs, then the author's browser check of a UPN roster on the real tenant.

## Definition of done

- A roster row given by UPN that resolves admits its account after sign-in. A row given by mail still does (tests).
- The `office@` collision admits neither the wrong account by UPN nor anyone by an `AMBIGUOUS` binding (test).
- A user row whose stored principal ID belongs to an earlier holder of its email does not admit a new account to rows bound to the earlier one (test).
- An unresolved, external or anonymous row matches exactly as before (tests).
- A reviewer row by UPN and a reviewee row by mail for one account are a self-review, both in assignments and in the rules engine, groups included. The cross-table identity checks treat them as one person (tests).
- Editing a bound row's address rebinds it, or clears the binding when the new address doesn't resolve. The old account loses access and the new one gains it, for all three roster types (tests).
- With no token, the upload proceeds unchecked and says so (test).
- The new columns survive `alembic downgrade base` and `upgrade head` on Postgres (CI).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Invitations for a row resolved by UPN~~ go to the directory's mail (author, 2026-10-31).
- ~~Offer to rewrite UPN cells at upload~~: no (author, 2026-10-31).
- Should an upload refuse, or Validate flag, two rows in one roster bound to the same account? The gates pick the lowest id until this is ruled. The author decides.

## Out of scope

- **Matching at sign-in on mail or UPN.** Rejected above.
- **Secondary aliases.** `User.ReadBasic.All` doesn't resolve them; widening it is a consent decision for the institution's IT.
- **Re-resolving existing rosters in bulk.** A re-upload does it.
- **Residential's matching**, in its own plan.

## Doc impact

- `cordware/spec/identity.md` — "Graph": the shared lookup and classification (rung 2). "Matching a person": a roster row bound to an account matches by object ID (rung 5).
- `utilityapps/spec/email_check.md` — the lookup's home moves to `cordware/graph.py` (rung 2).
- `spec/csv_contracts.md` — the preview's directory outcomes and the stored account fields (rung 4).
- `spec/audience_and_identity_model.md` — the identity-match rule: account first, then mail (rung 5).
- `spec/participant_model.md` — the reviewee and observer gates' match (rung 5).
- `spec/architecture.md` — "Identity is Cordware's": RRW's direct `cordware.graph` imports (`app/services/directory_accounts.py`, `app/web/routes_operator/_shared.py`) (rung 5).
- `guide/todo_master.md` — the queue entry, deleted at close.
