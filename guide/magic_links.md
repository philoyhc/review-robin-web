# Magic links — a deferred plan

> **Status: deferred, not scheduled** (author, 2026-11-02). Nothing here is
> queued in `guide/todo_master.md`. It gathers what `guide/deferred_consolidated.md`
> held about magic links, so the idea has one home; it becomes a segment
> plan only when a lift trigger below fires. Until then every participant
> signs in with Entra (`spec/audience_and_identity_model.md`).

## What a magic link is here

A participant without an institutional account (an external evaluator, a
cross-institution panel) opens their review from an emailed link. It
proves possession of the email account; it does not bypass identity
(`spec/audience_and_identity_model.md`: "tokenized link replaces auth" is
not the model). It is a fallback, never the primary sign-in.

## The approach assumed: a guest session inside the app

Chosen by the author, 2026-11-02. Opening the link starts a guest session
that RRW and Cordware issue and check themselves; the participant never
holds an Entra account.

- **Rejected: Entra B2B guests.** IT invites each external person as a
  guest account, who then signs in through Easy Auth like everyone else,
  with no change to the app. It costs IT effort per guest (or a
  self-service invite flow) and depends on IT allowing guests for the
  app. Still worth asking IT before this plan is taken up: if guests are
  allowed and few, they may make it unnecessary.
- **Still needed: a way past Easy Auth**, which today requires sign-in on
  every path but `/health`, so a guest never reaches the app. Undecided
  (open questions):
  - *exclude the magic-link paths* (e.g. `/reviewrobin/m/…`) from Easy
    Auth, as `/health` is: a setting the author can make in Cloud Shell.
    It must cover every page a guest may reach, not only the landing, and
    on those paths the app then checks sign-in itself;
  - *or allow anonymous* everywhere and have Cordware refuse a request
    with no identity except on guest-allowed paths: one rule tested in
    CI, but the app becomes the gate, and a bug in its check opens pages
    Easy Auth used to guard.

  Either opens part of the host to people outside the tenant, so either
  needs a security sign-off first.

## What has to be built

1. **Cordware: a guest identity.** A guest identity type in
   `cordware/identity.py`, read from the guest cookie and accepted only
   where a route says so; with *allow anonymous*, also the host-level gate
   that sends a request with no identity to sign-in, except on
   guest-allowed paths, with tests that every other route refuses it.
2. **RRW: the link.** A random token, stored hashed (as invitation tokens
   are), bound to one participant in one session, time-limited, revocable,
   audited on issue, use and revoke.
3. **RRW: the exchange.** Opening the link swaps the token for a signed,
   HttpOnly session cookie scoped to that participant and session. A
   signing key in Key Vault; expiry; sign out; CSRF protection on the
   cookie's form posts (Easy Auth's cookie carries none of this for us).
4. **RRW: where a guest may go.** The reviewer surface, and the reviewee
   `/results` and observer `/collation` pages; never an operator page, the
   lobby or `/me`'s cross-session dashboard.
5. **The participant types.** `invitations` is reviewer-keyed. Reviewees
   and observers need tokened landings too (W21), in one of three shapes:
   - a polymorphic row (`participant_type` and three nullable keys);
   - sibling tables (`reviewee_invitations`, `observer_invitations`);
   - a token-only row with no foreign key (flexible, loses integrity).

   Undecided; it also decides whether `email_outbox.invitation_id` stays a
   key to `invitations`.
6. **Sending the link.** It needs a send path: by hand (segment 14F) or on
   a clock (14G). Mail to addresses outside the tenant may meet tenant
   rules on external recipients: ask IT.
7. **Duplicate identities.** A landing that creates a participant row is a
   new write path on the roster tables, so the unique-index variant of
   deferred Slice D (`guide/deferred_consolidated.md`, the duplicate-identity
   entry) ships before it.
8. **Abuse.** Rate limits on the link route; one active link per
   participant; reissue revokes the old one.

## The risk that stays

Anyone holding the link acts as that participant. Short expiry, single
use, and an optional one-time code emailed at the exchange narrow it; none
removes it. Whether people outside the tenant may see review content at
all is the institution's decision.

## Lift triggers

- A pilot session with external reviewers who have no institutional
  account, and IT refuses B2B guests.
- An operator asking to notify reviewees or observers who cannot sign in
  (W20's notices, `guide/deferred_consolidated.md`).

## Open questions, for when it is taken up

- The way past Easy Auth: excluded paths or allow anonymous. Author, with
  a security sign-off.
- The participant-type shape (5).
- Link lifetime and single use, and whether a one-time code is required.
- Whether reviewees and observers get links at all, or reviewers only.
