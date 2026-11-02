# Magic links — a deferred plan

> **Status: deferred, not scheduled** (author, 2026-11-02). Nothing here is
> queued in `guide/todo_master.md`. It gathers what `guide/deferred_consolidated.md`
> held about magic links, so the idea has one home; it becomes a segment
> plan only when a lift trigger below fires. Until then every participant
> signs in with Entra (`spec/audience_and_identity_model.md`).

**Ask IT first.** Entra B2B guest accounts would let external people sign
in through Easy Auth like everyone else, with no change to the app. Build
what follows only if guests are refused, or per-person invites do not
scale.

## What a magic link is here

A participant without an institutional account (an external evaluator, a
cross-institution panel) opens their review from an emailed link. It
proves possession of the email account; it does not bypass identity
(`spec/audience_and_identity_model.md`: "tokenized link replaces auth" is
not the model). It is a fallback, never the primary sign-in.

## The approach assumed: Easy Auth allows anonymous; the app enforces sign-in

Chosen by the author, 2026-11-02 (the second of the two ways past Easy
Auth). Easy Auth's unauthenticated action becomes *allow*, still passing
identity headers when someone is signed in, and Cordware refuses any
request without an identity except on the paths that admit a guest.

- **Why not excluded paths** (the first way): each guest path would be an
  Easy Auth exception, set by hand per mount; one rule in Cordware covers
  every application and is tested in CI.
- **The cost:** the app becomes the gate. A bug in Cordware's check opens
  pages Easy Auth used to guard, so the check needs its own tests (every
  route refuses no-identity unless marked guest-allowed), and the host's
  troubleshooting gains a row for it.
- **Who changes it:** the Easy Auth setting is the author's (Cloud Shell),
  with a security sign-off first: review content becomes reachable by
  people outside the tenant.

## What has to be built

1. **Cordware: the gate.** A host-level dependency that answers 302 to
   sign-in for a request with no identity, except on guest-allowed paths;
   a guest identity type, accepted only where a route says so.
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

- The participant-type shape (5).
- Link lifetime and single use, and whether a one-time code is required.
- Whether reviewees and observers get links at all, or reviewers only.
