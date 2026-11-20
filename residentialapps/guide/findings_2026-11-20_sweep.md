# Findings — Residential Apps in the corpus sweep (2026-11-20)

**Found by:** RRW's `guide/sweep_2026-11-20_corpus.md`, read S4, the first sweep to read the packages' prose (segment 23H) · **Read at:** RRW `6003c8084` (#4063) · **Open:** all rows.

Residential Apps's share of the sweep's findings, kept beside its own plans; RRW's are in RRW's `guide/findings_2026-11-20_corpus.md`. Nothing was edited by the sweep, and the fixes ship as Residential Apps's own work. A row is struck when done, with its PR, or marked declined with the reason. **Decides:** *spec* (the spec is wrong; an update fixes it), *author* (a choice for the author), *trim* (history to strip, keeping its reason); in `docs/` rows *doc* plays *spec*. Line numbers are at `6003c8084`.

## For the author

- **S1** (low) `spec/supportlogs_ui.md:312-317` says a handover is agreed by two people; `docs/support_logs_confidentiality.md` and the served `who_can_see.html:31` say three.
- **S2** (medium-low) `docs/residentialapps_roster_structure.md` uses the vocabulary from before the 2026-10-27 units ruling (RF Zone, Tower), with no superseded banner; the spec and code use Unit-defined levels and slots (`sample_data.LEVEL_LABELS`, `MAX_LEVELS`).
- **S3** (low) `docs/residentialapps_identity.md`, `docs/residentialapps_email_identity_matching.md`: "Proposed repository location", and the latter's dated deployment-status §7 ("Update 30/31 October"), are history. Retire or move it.

## Per file

- **S4** `spec/applications.md`: the page map omits `/ra-leave/check-dates` (`routes_leave_ra.py:72`) and `/ra-leave/admin/policy/preview-appeals` (`routes_leave_admin.py:47`). Spec.
- **S5** the "Built so far" headers in all four `spec/` files narrate segments 1A–1D. Trim.
- **S6** `spec/applications.md:64` numbers sections from the frozen `docs/ra_leave_management_functional_spec_v0.4.md` as if live; no live spec carries RA Leave's functional contract beyond the page map. Spec.
- **S7** `spec_registry.py` maps the routes to the two `*_ui.md` files only; the path-and-grant contract is in `spec/applications.md` "Pages". Spec.
- **S8** (medium-low) `spec/residentialops_ui.md:105-108` takes its accent figures from the frozen `docs/support_logs_ui_spec_v0.1.md` §6; state them (`#a21caf`, `#e879f9`). Spec.
- **S9** (medium-low) `docs/graph_learnings.md` §4: "RRW sends no mail itself yet" is false; `cordware/graph.py` `GraphMailer` and RRW's `GraphEmailTransport` ship. Doc.
- **S10** `README.md:11-12`, `:19`: the frozen v0.4, v0.3 and v0.1 documents are listed with no baseline or superseded note. Doc.

`docs/residentialapps_roles.md` and `docs/support_logs_confidentiality.md` are current.
