# Segment 21F — A roster entry matches the mail or the sign-in name

**Opened:** 2026-10-31 · **Theme:** a roster row or an admin-list entry written as a person's sign-in name (UPN) matches them, as one written as their mail does · **Related:** `cordware/spec/identity.md` (the `Identity` fields), `spec/audience_and_identity_model.md`, `spec/participant_model.md`, `residentialapps/docs/residentialapps_email_identity_matching.md` (Residential's own plan for the same rule)

## Opportunity

At the institution a person's sign-in name and mail address differ. Production sign-ins carry both: `Identity.mail` (and `email`) is the mail, `Identity.upn` the sign-in name (`cordware/spec/identity.md`; Cordware's private records, 2026-10-30).

Review Robin matches on the mail only. Every check that asks "is this signed-in person on this list" compares `normalize_email(user.email)` with the list:
- session rosters: reviewers, reviewees, observers;
- the reviewer dashboard;
- invitation acceptance;
- the role disclosure behind the Guide and permissions;
- `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS` at first sign-in;
- `SUPER_ADMIN_EMAILS`.

A roster written with sign-in names, which is what many institutional exports hold, therefore matches nobody. The person signs in and is told they have no access.

The Email Address Checker can clean a roster before upload today: `USE_PRIMARY` is exactly "the sign-in name was given; the mail is …" (Cordware's first release, 2026-10-31). That is a workaround, not a fix.

## Decision

**Match a list entry if it equals the signed-in person's mail or their sign-in name**, after `normalize_email`, case-insensitive. Both come from the signed token at sign-in, so no Graph call is involved.

- **The sign-in name is kept on the user.** A new nullable `users.upn` is set at first sign-in and refreshed whenever a sign-in carries a different one. The matchers that receive a `User` row then have both addresses.
- **One helper decides.** `email_identity.addresses(user)` returns the user's mail and UPN, normalized, with blanks dropped. Every matcher compares against that set, so no site re-derives the rule.
- **The allowlists** `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS` match either address at first sign-in.
- **A pre-seeded user row** (an admin's invite) is found by either address when no principal id matches.

**Rejected:**
- *Canonicalize every roster at upload through Graph now* (resolve each address to object ID, mail and UPN). It is the stronger design, and it is stage two (Out of scope). It needs the uploading operator's delegated token, cannot resolve guests, external reviewers or anonymous identifiers, and can outlive the token's hour on a large upload. Matching at sign-in has none of those limits and serves today's case.
- *Rewrite UPNs to mail at upload, without Graph.* Nothing in an address says which form it is.

## Semantics

- **The match set** is `{normalize(mail), normalize(upn)}`, without empty values. A user with no UPN (fake auth, or a provider without one) matches on mail alone, as today.
- **Where it applies:**
  - `deps.require_*_in_session` (the reviewer, reviewee and observer gates);
  - the reviewer dashboard and `routes_reviewer/_shared.py`;
  - invitation acceptance (`_invite.py`);
  - `participants.disclosable_roles`, as used by `permissions` and the Guide;
  - the allowlist bootstrap and the pre-seeded-row lookup in `users.find_signed_in_user`.
- **What is unchanged:**
  - **What is stored on roster rows.** A UPN is stored as written.
  - **Who is identified.** A reviewee identifier that is not an address stays anonymous.
  - **What the invitation mail goes to.** It is the roster's address as written. A UPN that accepts no mail is a deliverability question; the Email Address Checker answers it before upload.
- **Two rows, one person.** A session may list a person twice, once by mail and once by UPN. Each gate already takes the first match in its own order. The Validate page gains no new warning here; the checker's duplicate groups catch it before upload.
- **Collision.** Entra keeps a UPN and the addresses on other accounts distinct within a tenant, so one address cannot name two people. An address from another tenant matches only a person signed in with that address.
- **Audit.** Changing `users.upn` writes nothing, because it is a cached claim, not a user's choice. The existing `workspace.user_email_changed` is untouched.

## Judgment calls — decided

- **A column, not `request.state`.** The matchers take `User` rows in places with no request (services), so the UPN lives with the row.
- **The migration is nullable with no backfill.** Each user's next sign-in fills it.

## Blast radius (measured)

Taken 2026-10-31 at `2bb3e01`.

| What | Count | Command |
|---|---|---|
| Mail-only matcher sites | 14 in 6 files (`deps.py`, `routes_reviewer/_shared.py`, `_dashboard.py`, `_invite.py`, `views/_guide.py`, `services/permissions.py`) | `grep -rn "normalize_email(user.email)\|normalize_email(current_user.email)\|disclosable_roles(db, user.email\|_email_in(cfg\.\|is_super_admin(user.email)\|is_super_admin(current_user.email)" app --include=*.py \| wc -l` |
| SQL roster filters on one address | 3 in `services/participants.py` | `grep -n "func.lower(func.trim(" app/services/participants.py` |
| `is_super_admin` users | 9 files | `grep -rln "is_super_admin" app cordware --include=*.py \| grep -v tests` |
| Models touched | 1 (`users`) | `ls app/db/models/user.py` |

## PR ladder

1. **This plan.** Prose only.
2. **`users.upn` and the helper.**
   - Lands:
     - the column and its migration, portable both ways;
     - its write at first sign-in and its refresh on later sign-ins;
     - `email_identity.addresses`.
   - Tests: the column is set, refreshed, and left alone when the sign-in carries no UPN.
   - Must not change any matcher.
3. **The matchers.**
   - The 14 sites and the 3 SQL filters move to the match set.
   - The allowlists, and the super-admin list (per open question 1), are included.
   - So is the pre-seeded-row lookup.
   - Tests: a roster row by UPN admits its person through every gate, the dashboard, invitation acceptance and the Guide. A row by mail still does. Someone else's UPN does not.
   - Last build rung, so `diff-reviewer` reads 2–3.
4. **Close.**
   - `spec-writer` on the doc-impact specs.
   - Stage two is recorded in `guide/deferred_consolidated.md`.

## Definition of done

- A reviewer, reviewee or observer listed by sign-in name reaches their surface after sign-in, and one listed by mail still does (tests).
- `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS` accept the sign-in name at first sign-in (tests).
- `users.upn` survives `alembic downgrade base` and `upgrade head` on Postgres (CI).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Does `SUPER_ADMIN_EMAILS` accept the sign-in name too?** For the author to decide.
   - *Recommended: yes.* Both addresses come from the same signed token for the same account, and one rule everywhere is simpler to state.
   - *Against:* the protected tier is clearest when its list names exactly one form. The current guidance says "mail address", and Cordware's records follow it.
   - Until ruled, rung 3 leaves the super-admin list mail-only.

## Out of scope

- **Stage two: canonicalize at upload.** This means resolving each roster address through `cordware/graph.py`, storing the object ID, mail and UPN with the row, flagging unresolved addresses in the preview, and matching on (tenant, object ID) after first sign-in. Its limits:
  - aliases don't resolve with `User.ReadBasic.All`;
  - addresses outside the tenant never resolve;
  - the uploading operator's token expires after an hour.

  It is recorded in `guide/deferred_consolidated.md` at the close.
- **Residential's matching:** that is in its own plan, `residentialapps/docs/residentialapps_email_identity_matching.md`.
- **Secondary aliases at sign-in:** they are not in the token, so they can't match.

## Doc impact

- `cordware/spec/identity.md` — "Matching a person": an entry matches the mail or the UPN; `users.upn` caches the claim (rung 3).
- `spec/audience_and_identity_model.md` — the identity-match rule for rosters and allowlists (rung 3).
- `spec/participant_model.md` — the reviewee and observer gates' match (rung 3).
- `spec/settings_inventory.md` — `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS` take either form, and `SUPER_ADMIN_EMAILS` per question 1 (rung 3).
- `guide/deferred_consolidated.md` — stage two, upload-time canonicalization (close).
- `guide/todo_master.md` — the queue entry, deleted at close.
