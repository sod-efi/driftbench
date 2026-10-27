# Standing decisions (one line each)

- 2026-10-26: Headline held-out numbers use the paper's prompt (v1) only; the calibration loop touches the development split and never the held-out set.
- 2026-10-26: Every published number carries a 95% interval and there is no single-number ranking; vendors get a right of reply before publication.
- 2026-10-26: Vendor code under vendor/ is never edited; the StepShield commit is recorded in every results.json.
- 2026-10-26: Judge runs refuse to start above the stated budget and stop at 150% of their estimate; keys live only in .env or host variables.
- 2026-10-27: A judge row is read only after its step log shows no failed parses (`parse_status`); the 200-token cap of the paper's recipe is replaced by 600 and recorded as a deviation. Refusals are a verdict of their own, scored both as no alert and as an alert, never dropped.
- 2026-10-27: StepShield is cited as an arXiv preprint (2601.22136), never as a NeurIPS paper; a style file is not a venue.
- 2026-10-27: The repo is public (owner, Oct 27); step logs are committed, only .env and vendor/ stay out.
