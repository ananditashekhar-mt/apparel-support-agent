# Damage-recognition fix — 11 November 2026

## Problem and change

The earlier 600-case OpenAI condition-fix benchmark missed `CONV-RESERVE-0011`:
“A tear was visible before I tried the garment on. ORD-20556”. It entered the
normal-return condition-confirmation flow rather than the damage review flow.

The existing damage policy was correct. The classifier prompt and intent
descriptions lacked guidance for physical faults described without the word
“damaged”, especially before trying on. The change teaches the classifier to
recognize tears, holes, broken fastenings and open seams, including when the
customer requests a return, exchange or refund as the remedy. It excludes
negated damage, hypothetical questions, other people's items, garment prints
and packaging-only damage. Explicit quality-framed stitching complaints retain
the existing quality intent; standalone physical-fault reports use damage.

No model, policy window, approval permission, storage or UI changed. The change
applies to model-backed classification, including OpenAI. The Demo keyword
parser is unchanged. Desktop redesign remains deferred.

## Evidence

Real `gpt-4.1-mini` calls exercised understanding, policy resolution, response
composition and idempotent mock confirmation. Every case used a separate
temporary SQLite database; Neon and production conversations were untouched.
Expected labels were frozen before the first run and never sent to the model.

| Check | Before | Final candidate |
| --- | ---: | ---: |
| Same 75-case strict intent + outcome comparison | 74/75 (98.67%) | 75/75 (100%) |
| Historical damage cases within that comparison | 38/38 | 38/38 |
| Used-item return cases within that comparison | 17/17 | 17/17 |
| New developer-authored damage/control cases | 19/20 | 20/20 |
| Policy outcome on the same 75 cases | 75/75 | 75/75 |
| Supplemental existing quality cases | Not rerun before | 16/16 |

Both paired runs completed without API errors; their 67 eligible mock
confirmations passed. The supplemental quality run also had no API errors.
The original missed complaint passed in both current runs, so its earlier
failure is intermittent. The one baseline miss this time was standalone
stitching coming apart, classified as quality; its review outcome was correct.
Consequently this comparison shows better label agreement, not a measured
policy-outcome gain.

An intermediate prompt shifted two existing quality-framed stitching fixtures
to damage. Both still proposed the correct review, but their labels regressed.
Clarifying the quality boundary restored all 16 quality labels without changing
their expected answers. These cases have now informed development and count as
regression coverage, not independent validation.

Automated coverage adds checks on days 2, 7 and 8 after delivery: damage uses
POL-03, asks for photos within the reporting window, explains late reporting
outside it, and never automatically creates a return even if the condition
checkbox is true. Test commands and final result are recorded below.

Final local suite: **90 tests run, 88 passed, 2 skipped** in 32.637 seconds.
The two skipped tests require a separately configured live Postgres test
database. An earlier suite run had one Streamlit AppTest timeout at its
three-second limit while API work was running; that test passed alone and
the subsequent full suite passed.

## Reproduce and inspect

- `scripts/evaluate_damage_fix.py candidate` runs the frozen 75 cases.
- Add `--quality-only` for the separate 16 quality cases.
- `reports/damage_recognition/cases.json` and `quality_cases.json` contain inputs
  and expected labels; result files preserve responses, policy decisions,
  token usage and source hashes.
- `baseline_agent.py` and `baseline_taxonomy.json` preserve the pre-change
  classifier source. The baseline result is historical evidence: running the
  runner with the label `baseline` now would use the current classifier.
- `.venv/bin/python -m unittest discover -s tests` runs local regressions.

This is a focused regression result, not a claim of 100% real-world accuracy.
The full 600-case benchmark has not been rerun, and its historical 599/600
result remains unchanged. Independent evaluation and multi-model/JEV
comparisons remain separate pending work. This fix is local and has not been
deployed to Streamlit.
