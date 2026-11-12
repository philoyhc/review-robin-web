# ApplyDesk — rulings and open work

Open work only, as RRW's `guide/todo_master.md`. The functional baseline
is `applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md`;
where a ruling below differs from it, the ruling wins.

## Rulings (author, 2026-11-12)

1. **No native assessment engine in the MVP.** Assessment runs in Review
   Robin: ApplyDesk pushes rosters to it and pulls results back, on the
   handoff that segments 23A and 23B proved (`spec/handoffs.md`). The
   spec's native assessor instruments, panels and assessor CSV import
   (§4.1, §7.6–§7.8) are not built for the MVP.
2. **Referees are native to ApplyDesk, but set aside** until the Blob
   storage questions are settled with IT (spec §5.3, G8).
3. **No uploads in MVP applications**: form answers only. Attachments
   come with Blob storage, alongside referees.
4. **ApplyDesk keeps the roster of recognized assessors and referees, and
   what each may view.** To Review Robin they are ordinary reviewers; it
   holds no ApplyDesk authorization.
5. **Reviewers read an application on ApplyDesk's application profile
   page**, linked as each reviewee's `ProfileLink` in the handoff.
   ApplyDesk decides each view itself, from the signed-in Cordware
   identity and its own roster. The page shows only the *Shown to
   reviewers* section.
6. **Blind review is possible**: in a blind exercise the profile page
   redacts the applicant's name and identifiers.
7. **Every exercise has a 10-character public ID**, in RRW's alphabet
   (`app/db/models/review_session.py`, `PUBLIC_ID_ALPHABET`).
8. **The URL map follows RRW's.** Operators work under
   `/applydesk/operator/exercises` and
   `/applydesk/operator/exercises/<id>/…`; participants under
   `/applydesk/me` and `/applydesk/me/exercises/<id>/…`.

## MVP roadmap

Segments in order; each gets a plan in this folder when it starts.

| Segment | Lands | Gates and dependencies |
|---|---|---|
| **AD1 — Skeleton** | Package, `/applydesk` mount, health, CI lane, the URL map as placeholder pages | `applydesk/guide/segment_AD1_skeleton.md` |
| AD2 — Database and identity | The `applydesk` database and Alembic history; people bound by Entra tenant and object ID; operator grants; audit | Cordware: the database and its runtime principal (private) |
| AD3 — Exercises | The exercise and its public ID, configuration, draft → published → closed → archived, Validate, the Application → Review stage boundary | G2 (published changes), G3 (stages) |
| AD4 — Applicant forms and portal | The applicant form with *Shown* / *Not shown to reviewers* sections, versioned; drafts, submit, withdraw; open or invitation-only exercises | G1 narrowed to applicant forms (shared package or fork); G4 (allowance) |
| AD5 — Assessor roster and profile page | The exercise's assessors and what each may view; the application profile page with its access check, audit and blind redaction | View scope: below |
| AD6 — Assessment in Review Robin | Rosters from submitted applications, `ProfileLink` to the profile page, results back into ApplyDesk | The open items below |
| AD7 — Timeline and outcomes | Milestones, announcements, outcome import, embargo on read, release, correction | G5 (sender), G7 (publication) |
| AD8 — Dashboard and export | Counts by state; the export bundle | — |
| Later | Blob storage, then uploads and referees | G8, with IT |

## Open decisions

- **View scope (AD5):** whether an assessor may open every application
  in the exercise, or only those ApplyDesk lists for them. Listing
  pairs means ApplyDesk also sends them to Review Robin as
  Relationships, for the instrument to filter on.
- **Blind identity in Review Robin (AD6):** RRW shows `RevieweeEmail`
  under each name, and the handoff puts the application ID there. A blind
  exercise may need an alias key minted per handoff, which only
  ApplyDesk can map back.
- **The 23A open items (AD6):** `reviewees.unreachable_for_results` on
  every application ID; two concurrent first posts of one transfer; the
  new-user race in `get_or_create_user` (`guide/interoperability.md` §4).
- **Unattended send (AD7):** Cordware's host sends as the signed-in
  user (`cordware/graph.py`, `/me/sendMail`); a send with no one signed
  in shares RRW segment 14G's open question for IT.
- **Raise early with IT:** Blob storage (spec §5.3) and the `applydesk`
  database, beside 14G's mailbox question.
