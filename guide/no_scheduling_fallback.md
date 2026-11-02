# While mail cannot go on a clock: the manual fallback

**Opened 2026-11-02, at the author's request; revised the same day**
(author: "just because you can't do scheduled emails, it doesn't follow
you can't do scheduled actions"). A clock and a way to send with nobody
signed in are **independent**:

- **The clock is RRW's to build.** The host is Always On with one process,
  so an in-app loop runs timed actions without IT: segment 14E.
- **Mail with nobody signed in needs IT**: offline sending as the operator,
  else a dedicated mailbox (two requests kept privately with the
  deployment). If granted, segment 14G.

So "everything manual" narrows to the steps that send mail. This note says
what changes while that is so; segment 14F builds it. It leaves when 14G
ships, or when 14F has absorbed it.

## Which timed steps hold

| Step | Field | With 14E's clock, no mail on a clock |
|---|---|---|
| Start (activation) | `scheduled_activate_at` | **On time**: a state change, no mail (14E) |
| End (deadline close) | `deadline` | **On time**: late saves are refused on arrival already; 14E also closes the instruments at End |
| Release-from / release-until | `responses_release_at` / `_until` | **Holds**: checked when a reviewee or observer loads the page |
| Auto-archive, auto-delete after archive | not built | Would run on 14E's clock when built |
| Auto-send invites | `invite_offsets` | **Manual**: needs a send path on a clock |
| Auto-send reminders | `reminder_offsets` | **Manual**, as invites |
| Responses-received confirmations | queued on submit | **Manual**: sent by an operator's action |

## What changes while mail is manual (14F)

1. **The two auto-send fields render disabled** behind
   `RRW_SCHEDULED_SEND=off`, with one line: "Scheduled sending isn't
   available on this deployment; send from Invitations when it's time".
   Their values are kept and the Settings CSV round-trips, so switching
   the setting on with 14G restores them. Every other date field stays
   live: none of them misleads once 14E ships.
2. **The Workflow card drops "System will dispatch automatically"**, which
   is also wrong today (checklist item 7).
3. **Due-action prompts replace the promise.** Session Home says what is
   due ("Reminders due: 12 reviewers have not submitted, 2 days before
   End") beside its button; the lobby marks sessions with an action due.
   They read the same offsets the operator set, so the plan still drives
   the nudges.
4. **Confirmations** wait for an operator's **Send queued confirmations**,
   under the backlog rule in checklist item 9.
5. **The Guide** gains "Running a session by hand": what is automatic
   (Start, End, the release window) and what is the operator's (send,
   remind, confirm, close, release).

## Open questions

- **When to switch the setting on:** with 14G only, or as soon as IT
  grants offline sending (request 6) and 14G's first rung lands. Author.
- **Do due-action prompts also go to the owner by email?** A manual send
  to oneself adds little; proposed no. Author.
- **Per deployment or per session?** Proposed per deployment: the
  limitation is the host's.
