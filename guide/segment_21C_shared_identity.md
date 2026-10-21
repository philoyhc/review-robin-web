# Segment 21C — Shared identity

**Opened:** 2026-10-21 · **Outline:** `guide/segment_21_domain_retrofit.md`
(sub-segment 21C) · **Strategy:** `docs/cordware_repository_strategy_v0.8.md`
§3 "Shared identity, application-specific permissions" and "Environment,
guard and local testing switches" · **Sequence:**
`docs/cordware_implementation_sequence.md` §5 C1–C4 · **Hold:** lifted for
21C by the author at 21B's close (2026-10-21).

v0.8 §3 settles what moves and who owns each switch. This plan settles
the one decision v0.8 §8 leaves open, **the trusted-identity
interface**, and cuts the rungs.

## Opportunity

RRW is still its own identity provider, which v0.8 §3 gives to Cordware:

- **It parses Easy Auth itself.** `app/auth/identity.py` (165 lines) is
  the only reader of `X-MS-CLIENT-PRINCIPAL*`. A second mounted
  application would need its own copy.
- **It owns the fake user and nothing guards it.** `ALLOW_FAKE_AUTH` and
  the `FAKE_AUTH_*` identity live in `app/config.py`. "Never enable fake
  auth when deployed" is a documented rule (`docs/security_posture.md`),
  not an enforced one.
- **It parses `SUPER_ADMIN_EMAILS`.** `app/auth/roles.py` folds the fake
  email in by reading RRW's settings. v0.8 makes super-admin a platform
  role that Cordware asserts and every application reads the same way.

## Decision

**Cordware owns identity in `cordware/identity.py`, and RRW reads it
through four names.** RRW keeps `app/auth/identity.py` as a re-export, so
its 78 importers (4 app, 73 tests, 1 tool) are untouched (sequence C4,
deferred).

The interface:

- **`Identity`** — a frozen dataclass: `principal_id`, `email`, `name`,
  `provider`, `is_fake`. `is_super_admin` and `super_admin_configured`
  are **properties**, computed from the host-level predicate rather than
  stored. So the flag, the predicate and `super_admin_configured` agree
  by construction, which v0.8 §3 requires. A test that builds an identity
  by hand gets the same answer a request would. RRW's `AuthenticatedUser`
  becomes this class under its old name, `display_label` included.
- **`get_identity(request)`** — Easy Auth headers when present, else the
  fake user when `ALLOW_FAKE_AUTH` is on, else a 401. This is today's
  `resolve_current_user`, moved whole, with its optional settings
  argument now Cordware's `IdentitySettings`. `tests/test_identity.py`
  and `tests/integration/test_setup_template_download.py` pass one.
  `get_current_user` re-exports it.
- **Host-level reads, valid outside a request:**
  - `fake_auth()` returns `enabled` and `email`;
  - `is_super_admin_email(email)` tests any email;
  - `super_admin_configured()` says whether the effective list is
    non-empty;
  - `app_env()` and `is_local()`.
- **Settings:** a `cordware/settings.py` `IdentitySettings`, read from
  the repository-root `.env`. It holds `APP_ENV`, `ALLOW_FAKE_AUTH`, the
  three `FAKE_AUTH_*` identity fields, `FAKE_AUTH_SUPER_ADMIN` and
  `SUPER_ADMIN_EMAILS`, each under its current name and default
  (v0.8 §3's ownership list).

**The guard** sits in `cordware.main.create_app`. It refuses to build the
host when `ALLOW_FAKE_AUTH` is on and `APP_ENV` is not `local`, before
any application is mounted, so the process fails (v0.8 §3).

**Rejected: an `Identity` with stored `is_super_admin`.** It would have
to be set by every caller that builds one. There are 73 test files that
build `AuthenticatedUser`, and one forgotten `True` would make the flag
and the predicate disagree. **Rejected: RRW keeping a parser for its own
tests.** v0.8 §3 says one parser, and the re-export already serves the
tests.

## Semantics

- **Email comparison** in Cordware is `strip()` then `str.lower()`, the
  rule `app/services/email_identity.py`'s `normalize_email` documents
  (lowercase, deliberately not casefold, 19N Item 2). Cordware cannot
  import `app`, so it keeps its own copy, and an RRW test pins the two
  equal on the cases that file's tests use.
- **The effective super-admin list** is `SUPER_ADMIN_EMAILS` plus the
  fake email, the latter only while `ALLOW_FAKE_AUTH` and
  `FAKE_AUTH_SUPER_ADMIN` are both on. `super_admin_configured()` is
  whether that list is non-empty. Local fake auth with an empty setting
  therefore keeps RRW's any-admin fallback off, as today.
- **Through C2, the fake super-admin is still RRW's**:
  `effective_super_admin_emails()` folds in `fake_auth().email`. From C3
  RRW reads only Cordware's three names. The fake user keeps every role
  at every rung (outline § Semantics).
- **RRW's fake roles** (`FAKE_AUTH_OPERATOR`, `FAKE_AUTH_SYS_ADMIN`) key
  off `identity.is_fake` alone from C2. Cordware sets it only on the
  fake user, which the guard confines to `APP_ENV=local`.
- **`APP_ENV`** is read through `app_env()` and `is_local()`, by
  `validate_critical_settings` and, until C3, by RRW's empty-list
  warning. Its default stays `local`.
- **Host logging** (v0.8 §3, events 1–3):
  - a warning on every start with fake auth on, and a record of the
    guard's refusal (C1);
  - a malformed Easy Auth header every time, and a missing one once per
    process with a running count, the fact only and never the contents
    (C1; Open question 1);
  - the empty-list warning in a deployed environment moves from
    `app/main.py` to Cordware (C3).
- **Every switch stays settable per run** (`$env:NAME=…` or
  `export NAME=…` over `.env`), and a test sets each one.

## Judgment calls — decided

- C2 stays its own rung, though small: it is the one rung that changes
  who gets RRW roles, and it reads best alone (sequence C2).
- `cordware/settings.py` rather than more fields on `cordware/main.py`'s
  `CordwareSettings`: identity is imported by applications, the host
  module is not (import-boundary test).
- Identity tests move to `cordware/tests/`. RRW's tests keep exercising
  the re-export, so both sides stay covered.
- `/auth/me` and `/auth/me/debug` keep their shape. They already show
  `is_fake`, and `is_super_admin` joins them as a property (C3).

## Blast radius (measured)

Taken 2026-10-21 at `fd60526e`.

| What | Count | Command |
|---|---|---|
| `app.auth.identity` importers | 4 app, 73 tests, 1 tool | `grep -rlE 'app\.auth\.identity' --include=*.py app tests tools` |
| `app.auth.roles` importers | 6 app (`user.py`, `main.py`, `account_listing.py`, `users.py`, `deps.py`, `_sys_admin.py`), 2 tests | `grep -rlE 'app\.auth\.roles' --include=*.py app tests` |
| Super-admin call sites | 11: `main.py:66`; `users.py:375, 377, 393`; `account_listing.py:81, 222, 295`; `_sys_admin.py:390`; `deps.py:96, 165`; `user.py:100` | `grep -rnE 'effective_super_admin_emails\(\|is_super_admin\(' app` |
| `is_fake` readers | `deps.py:156`, `users.py:123`, `routes_auth.py:39`, `me_debug.html:14` | `grep -rnE 'is_fake' app` |
| Settings moving | 7 fields in `app/config.py`: `app_env`, `allow_fake_auth`, `fake_auth_principal_id`, `_email`, `_name`, `fake_auth_super_admin`, `super_admin_emails` | `grep -nE 'app_env\|allow_fake_auth\|fake_auth_\|super_admin_emails' app/config.py` |
| `APP_ENV` readers | `app/main.py:66`, `app/config.py:134` | `grep -rnE '\bapp_env\b' app` |
| Tests patching a moving setting | 44 lines in 8 files; 15 files name an env-var spelling | `grep -rnE '"(allow_fake_auth\|super_admin_emails\|fake_auth_[a-z_]+\|app_env)"' tests`; `grep -rliE 'ALLOW_FAKE_AUTH\|SUPER_ADMIN_EMAILS\|FAKE_AUTH_\|APP_ENV' tests` |

## PR ladder

1. **C0, this plan**, prose only.
2. **C1, Cordware's identity.**
   - Lands `cordware/identity.py` (`Identity`, `get_identity`, `fake_auth`,
     `app_env`, `is_local`) and `cordware/settings.py`, with the identity
     settings moved and `SUPER_ADMIN_EMAILS` / `FAKE_AUTH_SUPER_ADMIN`
     still RRW's.
   - Adds the guard and log events 2 and 3.
   - `app/auth/identity.py` becomes the re-export.
     `effective_super_admin_emails()` and `validate_critical_settings`
     read Cordware.
   - The parser tests move to `cordware/tests/`, and RRW tests that patch
     a moved field patch Cordware's.
   - **Must not change** who holds which role, or any response at `/`.
3. **C2, fake roles from the marker.**
   - `deps.py`'s fake operator and admin grants read `is_fake` alone.
   - RRW keeps `FAKE_AUTH_OPERATOR` and `FAKE_AUTH_SYS_ADMIN`.
   - Tests: the fake user's roles with each switch off.
4. **C3, the platform super-admin.**
   - `SUPER_ADMIN_EMAILS` and `FAKE_AUTH_SUPER_ADMIN` move.
   - The identity gains `is_super_admin` and `super_admin_configured`,
     and the host gains `is_super_admin_email`.
   - `app/auth/roles.py` and its 11 call sites read those three, keeping
     the fallback on `super_admin_configured`.
   - RRW's copies of both settings, and its empty-list warning, retire.
   - `tests/unit/test_roles_super_admin.py`'s cases move onto the
     Cordware switch.
   - This is the item's last build rung, so the cumulative `diff-reviewer`
     read runs here, from C1's base.
5. **Close:** specs (§ Doc impact), `cordware/spec/identity.md`, v0.8 §8,
   Status compacted, archive.

Each rung leaves every response at `/` unchanged, and the full suite
passes at each.

## Definition of done

- `cordware/identity.py` is tested on its own in `cordware/tests/`:
  - the parser;
  - the fake user;
  - every switch set per run;
  - the guard refusing with `ALLOW_FAKE_AUTH` on and `APP_ENV` not
    `local`, and allowing it at `local` (C1).
- `app/` reads no moved setting: `grep -rnE 'settings\.(app_env|allow_fake_auth|fake_auth_(principal_id|email|name|super_admin)|super_admin_emails)' app`
  finds nothing (C3).
- The fake user is an operator, an admin and a super-admin at every rung.
  With each switch off, it loses only that role (C1–C3).
- The super-admin flag, the predicate and the fallback are tested with an
  empty and a non-empty list, and with fake auth on and off (C3).
- `app/main.py` logs no super-admin warning; Cordware logs it in a
  deployed environment (C3).
- On localhost, the author signs in with fake auth and finds every role
  as before, `/auth/me/debug` included (close).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~Log a missing Easy Auth header on every 401?~~ No: a malformed
   header is logged every time, a missing one once per process with a
   running count (author, 2026-10-21, on the recommendation).
2. ~~C4, repointing the 78 importers?~~ Not in 21C; the re-export stays
   (author, 2026-10-21, on the recommendation).

## Out of scope

- **C4**, repointing the importers (Open question 2).
- **The prefix flip, `/.auth/*` return paths, the landing page:** 21D.
- **The dev slot's `APP_ENV`:** set when the slot resumes
  (`docs/deployment_dev.md` "Resuming the dev slot", step 1).
- **Residential's identity mapping:** stage 3.

## Doc impact

- `spec/architecture.md` — identity from Cordware: the re-export, the four names RRW reads, the guard (close).
- `spec/settings_inventory.md` — the seven settings' owner becomes Cordware, names and defaults unchanged (close).
- `spec/permissions.md` — super-admin from Cordware's flag, predicate and `super_admin_configured`; the fake roles keyed off `is_fake` (close).
- `spec/audience_and_identity_model.md` — super-admin as Cordware's platform role; fake identity and its guard owned by Cordware (close).
- `docs/security_posture.md` — the fake-auth guard enforced; identity interpreted by the host (close).
- `docs/local_setup.md` — the identity switches are Cordware's, still in one `.env` (close).
- `docs/cordware_repository_strategy_v0.8.md` — §8: the trusted-identity interface settled (close).
- `CLAUDE.md` — "Identity and auth" and the local auth shortcut name Cordware (close). `AGENTS.md` twinned.
- `cordware/spec/identity.md` — new: the trusted-identity contract (close); checked by hand.
