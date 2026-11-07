# Old versus new dataset evaluation — 7 November 2026

The new dataset is a better test fixture: it has coherent order/product links, broader customer histories, explicit policy boundaries and less repeated wording. It has **not made the agent more capable**. The current Demo classifier performs equally on matched cases and struggles with the new evaluation language. Live OpenAI quality remains unmeasured because authentication failed.

A later run with the updated API key successfully evaluated all 600 new-data cases using gpt-4.1-mini. See [OpenAI evaluation](openai-new-dataset-evaluation.md) for those results. The expired-key observation below records the earlier comparison attempt.

## Name realism

The 200 customers now share 71 names. Common names such as Karan Malhotra, Gurpreet Singh, Lakshmi Reddy and Pooja Verma repeat, alongside a smaller set of distinctive names and initials. Selection uses a separate seeded name generator so changing names does not change products, orders or test questions. Identity and ownership use independent customer IDs, never names.

## Method

Executed **934 Demo evaluation cases**: 124 archived evaluation cases, 600 new held-out cases and 105 matched probes per dataset. The 57 workflow/dataset/UI tests also pass.

Both datasets ran through the **same current agent, policies and 240-variant catalogue**. Old native cases used 17 September 2026; new native cases used their per-scenario dates. The old cases supplied order context without condition confirmation, matching their earlier runner; the new cases supplied their explicit context/condition metadata. Therefore native outcome rates are not a controlled old/new comparison. Native intent scores measure agreement with each dataset's labels; old labels include known reference conflicts.

The matched experiment is the controlled comparison: **35 identical scenario definitions × 3 samples**, with the same wording, condition-confirmation rules and prewritten expected outcomes on each dataset. Delivered-order ages and fulfilment states were matched to the scenario; customer/order IDs and dates were adapted to each dataset. Each probe had an isolated SQLite database. Success required the intended classification, expected status and proposed action; offered actions were confirmed and checked for local persistence and idempotency. These are mock requests, not real refunds, deliveries or support notifications.

Expected matched outcomes were authored before execution rather than copied from agent outputs. The agent was **not changed after observing these results**. Recorded code/data hashes are in the JSON report.

## Results

| Measurement | Old dataset | New dataset |
| --- | ---: | ---: |
| Matched workflow success, 105 probes each | **103/105 — 98.10%** | **103/105 — 98.10%** |
| Native intent-label accuracy | 93/124 — 75.00% | 399/600 — 66.50% |
| Native expected status + action | Not reliably comparable; no structured outcome labels | 432/600 — 72.00% |
| Native strict intent + status + action | Not reliably comparable | 399/600 — 66.50% |
| Escalation-label agreement | 56/86 scorable labels — 65.12% | 501/600 — 83.50% |

The archived test-only subset reproduces the previously recorded **47/62 — 75.81%** intent baseline. Its 62 validation cases score 46/62 — 74.19%. The 75.00% old overall figure combines both subsets.

| New evaluation partition | Samples | Intent accuracy | Status/action agreement | Strict success |
| --- | ---: | ---: | ---: | ---: |
| test | 300 | 66.67% | 73.33% | 66.67% |
| challenge | 200 | 77.00% | 80.00% | 77.00% |
| reserve | 100 | 45.00% | 52.00% | 45.00% |

The challenge split contains 60 relatively straightforward identity/context checks, so its higher score does not mean Hinglish or difficult cases are solved. The earlier 100/100 showcase result came from curated demonstration templates; it did not predict performance on the held-out questions.

## Use-case coverage and results

All 16 named project intents and the unknown fallback are represented. The matched suite includes tracking at four fulfilment stages; delayed/disputed/partial deliveries; damaged, wrong and quality reports on days 7/8; returns on days 29/30/31/40; missing and follow-up condition confirmation; available/unavailable size and colour exchanges; multi-turn size selection; fit problems; three cancellation stages; refund/price handoffs; unrelated requests; unknown IDs; another customer's order; and missing order context.

| Use case | New native intent accuracy | Matched old workflow success | Matched new workflow success |
| --- | ---: | ---: | ---: |
| cancel_order | 39/54 — 72.22% | 9/9 — 100.00% | 9/9 — 100.00% |
| damaged_item | 10/38 — 26.32% | 4/6 — 66.67% | 4/6 — 66.67% |
| delivered_not_received | 10/21 — 47.62% | 3/3 — 100.00% | 3/3 — 100.00% |
| delivery_delay | 16/44 — 36.36% | 3/3 — 100.00% | 3/3 — 100.00% |
| exchange_color | 32/32 — 100.00% | 6/6 — 100.00% | 6/6 — 100.00% |
| exchange_size | 37/37 — 100.00% | 9/9 — 100.00% | 9/9 — 100.00% |
| fit_issue | 15/15 — 100.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| missing_item | 12/16 — 75.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| order_tracking | 110/150 — 73.33% | 21/21 — 100.00% | 21/21 — 100.00% |
| price_adjustment | 16/16 — 100.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| quality_issue | 16/16 — 100.00% | 6/6 — 100.00% | 6/6 — 100.00% |
| refund_status | 16/16 — 100.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| return_outside_window | 9/36 — 25.00% | 6/6 — 100.00% | 6/6 — 100.00% |
| return_request | 18/38 — 47.37% | 12/12 — 100.00% | 12/12 — 100.00% |
| unknown | 17/17 — 100.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| used_item_return | 17/17 — 100.00% | 3/3 — 100.00% | 3/3 — 100.00% |
| wrong_item | 9/37 — 24.32% | 6/6 — 100.00% | 6/6 — 100.00% |

## Failure patterns

The same two matched failures occurred on both datasets: “There is damage on the garment.” was classified as unknown on days 7 and 8. Other damage wording passed. This points to vocabulary coverage rather than a dataset-dependent policy calculation.

Examples from the new native evaluation:

| Customer wording | Expected intent | Actual Demo intent | Effect |
| --- | --- | --- | --- |
| Delivery is overdue; what happens next? | delivery_delay | order_tracking | Returned tracking rather than the delay handoff |
| You sent something different from what I ordered. | wrong_item | unknown | Failed to recognise the complaint |
| There is damage on the item straight out of the packaging. | damaged_item | unknown | Failed to offer the damage-review route |
| Can I send this purchase back? | return_request | unknown | Failed to recognise a return |
| The 30-day return window has expired; can someone review? | return_outside_window | return_request | Intent label differed, but age-based handoff was still correct |
| Cancel kar do please, bought the wrong thing. | cancel_order | wrong_item | Keyword precedence selected the wrong complaint |

The next improvement should target language understanding and mixed-request clarification, then run a fresh, independently worded benchmark. This report deliberately preserves the measured baseline rather than repairing failures and reusing the same test questions to claim an unbiased improvement.

## Data consistency

Checks below cover all operational orders and conversation fixtures, not just the evaluated subsets.

| Check | Old | New |
| --- | ---: | ---: |
| Post-delivery cases linked to undelivered orders | 112 | 0 |
| Identical messages shared between train and standard test | 28 | 0 |
| Orders with no exact variant in the current catalogue | 210 | 0 |
| Unexplained unit price × quantity differences among represented variants | 15 | 0 |

The catalogue comparison covers 262 old orders and 600 new orders. Only 52 old order variants are represented exactly in the current catalogue, versus all 600 new ones. Price/quantity checks apply to those 52 and 600 represented orders respectively. Historical catalogue removals or discounts could explain discrepancies in a real system; neither supporting history nor discount fields exist in this prototype. These are consistency flags, not proof of fraudulent or impossible historical transactions. Zero flags under these checks is not proof of complete correctness.

## Live model limitation and benchmark status

A live smoke test using the configured OpenAI model failed with **HTTP 401 / expired_secret_key**. No successful model inference was obtained, so there is **no OpenAI or hosted-site success rate** in this report. All reported evaluation percentages are for the local Demo rule classifier and policy engine.

The three new evaluation partitions have now been evaluated. They can serve as recorded regression sets, but the reserve is no longer an untouched benchmark. The old native set contains 37 unique messages across 124 cases, while the new native set contains 538 across 600. Templates, repeated scenarios and correlated samples limit generalisation; the percentages are descriptive, not independent production reliability estimates. Tone, subtle grounding errors and real fulfilment outcomes are not automatically scored.

## Reproduce

```bash
.venv/bin/python scripts/compare_datasets.py
.venv/bin/python -m unittest discover -s tests
```

The full machine-readable results, per-scenario actual replies, failed cases and hashes are in [dataset_comparison_demo.json](../reports/dataset_comparison_demo.json). Live authentication status is recorded in [openai_evaluation_status.json](../reports/openai_evaluation_status.json).
