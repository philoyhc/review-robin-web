# Findings — Apply Desk in the corpus sweep (2026-11-20)

**Found by:** RRW's `guide/sweep_2026-11-20_corpus.md`, read S4, the first sweep to read the packages' prose (segment 23H) · **Read at:** RRW `6003c8084` (#4063) · **Open:** all rows.

Apply Desk's share of the sweep's findings, kept beside its own plans; RRW's are in RRW's `guide/findings_2026-11-20_corpus.md`. Nothing was edited by the sweep, and the fixes ship as Apply Desk's own work. A row is struck when done, with its PR, or marked declined with the reason. **Decides:** *spec* (the spec is wrong; an update fixes it), *author* (a choice for the author), *trim* (history to strip, keeping its reason); in `docs/` rows *doc* plays *spec*. Line numbers are at `6003c8084`.

## For the author

- **S1** (low) `applydesk/spec/applications.md:502-504`, `:544`, `:640-648` give a gate its own From and To (`Gate.when`, `stages.window`); rulings 26 and 28 say a gate has none. The code follows the spec, so either a later decision is unlogged or spec and code are ahead of the rulings.

## Per file

- **S2** `spec/applications.md:267-269`, `:336-337`, `:470-471`, `:491-492`, `:743`, `:767`, `:1244`: "nothing is saved until AD2" and "Save disabled" hold for the sample exercise only; a scratch exercise saves (ruling 59; `_form.html:47`). Spec.
- **S3** `spec/applications.md:807-808`: a Panels heading carries an *Opened* chip, not *Sent* (`:819-820`, `_panels.html:162`); already in `guide/todo_master.md` "Rulings to settle". Spec.
- **S4** `spec/applications.md`: rulings 33 (parts replace *Shown*/*Not shown*), 36 (a second gate type), 38 (release per audience) and 39 (every panel generic) are not yet folded. A note, not drift: they fold at the AD1 → AD2 juncture (RRW `rrw_sdd_in_practice.md` §6.1).
- **S5** `spec/applications.md:3-10`, `spec/architecture.md:3-5`: the "Built so far" headers stop at AD1K, and are history. Trim.
- **S6** `spec/architecture.md`: the layout table omits `handoff.py`, `process_save.py`, `scratch.py`, `scratch_panels.py`, `tones.py`. Spec.
- **S7** `docs/photo_field_design.md`: "Into the MVP?" is still open though ruling 12 settled it; "not scheduled"; the old *Not shown* wording. Doc.

The v0.6b baseline is described as the baseline wherever it is cited, and nothing in `spec/` treats it as the contract. `spec_registry.py` maps every routing module to a live spec.
