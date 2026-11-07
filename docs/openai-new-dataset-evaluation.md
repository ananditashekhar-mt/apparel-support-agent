# OpenAI evaluation on the new dataset — 7 November 2026

Completed the actual OpenAI classification → policy engine → response composition path for **600 cases**, using **gpt-4.1-mini**. The updated API key works. This is a local agent evaluation against synthetic records, not a test of the deployed Streamlit endpoint or external commerce services.

This is the frozen **pre-fix** result. A later item-condition fix and same-model old/new comparison are documented in [comparison and condition fix](openai-comparison-and-condition-fix.md).

## Overall results

| Measurement | Demo, same 600 cases and current code | OpenAI |
| --- | ---: | ---: |
| Intent-label accuracy | 399/600 — 66.50% | 585/600 — 97.50% |
| Expected policy status + proposed action | 432/600 — 72.00% | 587/600 — 97.83% |
| Strict intent + policy status + action | 399/600 — 66.50% | 585/600 — 97.50% |
| Escalation-label agreement | 501/600 — 83.50% | 587/600 — 97.83% |

OpenAI intent accuracy differs from Demo by **+31.00 percentage points** on the identical question set. Policy-outcome agreement differs by **+25.83 percentage points**.

API failures: **0**. Successful model calls: **1218**, excluding the initial two-call connectivity probe. Recorded token usage: **384,770 input**, **48,977 output**. No monetary cost is inferred without configured pricing.

Mock request persistence/idempotency: **334/334** passed. These are local return/exchange/cancellation/escalation requests, not actual fulfilment or refunds. Only correctly proposed actions were confirmed; this conditional rate does not count missed proposals as successful workflows.

## Evaluation partitions

| Partition | Cases | Intent accuracy | Status/action agreement | Strict success | API failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| challenge | 200 | 196/200 — 98.00% | 196/200 — 98.00% | 196/200 — 98.00% | 0 |
| reserve | 100 | 98/100 — 98.00% | 100/100 — 100.00% | 98/100 — 98.00% | 0 |
| test | 300 | 291/300 — 97.00% | 291/300 — 97.00% | 291/300 — 97.00% | 0 |

## Use-case results

| Intent | Cases | Intent accuracy | Status/action agreement | Strict success |
| --- | ---: | ---: | ---: | ---: |
| cancel_order | 54 | 54/54 — 100.00% | 54/54 — 100.00% | 54/54 — 100.00% |
| damaged_item | 38 | 36/38 — 94.74% | 38/38 — 100.00% | 36/38 — 94.74% |
| delivered_not_received | 21 | 21/21 — 100.00% | 21/21 — 100.00% | 21/21 — 100.00% |
| delivery_delay | 44 | 44/44 — 100.00% | 44/44 — 100.00% | 44/44 — 100.00% |
| exchange_color | 32 | 32/32 — 100.00% | 32/32 — 100.00% | 32/32 — 100.00% |
| exchange_size | 37 | 37/37 — 100.00% | 37/37 — 100.00% | 37/37 — 100.00% |
| fit_issue | 15 | 15/15 — 100.00% | 15/15 — 100.00% | 15/15 — 100.00% |
| missing_item | 16 | 16/16 — 100.00% | 16/16 — 100.00% | 16/16 — 100.00% |
| order_tracking | 150 | 150/150 — 100.00% | 150/150 — 100.00% | 150/150 — 100.00% |
| price_adjustment | 16 | 16/16 — 100.00% | 16/16 — 100.00% | 16/16 — 100.00% |
| quality_issue | 16 | 16/16 — 100.00% | 16/16 — 100.00% | 16/16 — 100.00% |
| refund_status | 16 | 16/16 — 100.00% | 16/16 — 100.00% | 16/16 — 100.00% |
| return_outside_window | 36 | 36/36 — 100.00% | 36/36 — 100.00% | 36/36 — 100.00% |
| return_request | 38 | 38/38 — 100.00% | 38/38 — 100.00% | 38/38 — 100.00% |
| unknown | 17 | 17/17 — 100.00% | 17/17 — 100.00% | 17/17 — 100.00% |
| used_item_return | 17 | 4/17 — 23.53% | 4/17 — 23.53% | 4/17 — 23.53% |
| wrong_item | 37 | 37/37 — 100.00% | 37/37 — 100.00% | 37/37 — 100.00% |

## Failures preserved for review

No prompts, agent rules, policy files or expected labels were changed to improve this run's results. Failure counts below are descriptive and include repeated wording across different orders.

| Expected intent | Actual intent | Actual status | Cases |
| --- | --- | --- | ---: |
| used_item_return | return_request | needs_information | 11 |
| used_item_return | return_outside_window | needs_information | 2 |
| damaged_item | quality_issue | escalation_proposed | 2 |

Representative failed messages and actual replies:

- **CONV-TEST-0047**: I have worn it once and want to send it back. ORD-20407

  Expected `used_item_return` / `escalation_proposed` / `escalation`; got `return_request` / `needs_information` / `None`.

  Actual reply: Hi, I’m Tia from Threadly support.  Thanks for reaching out about returning your item. To proceed with your return, please confirm that the item is unworn, unwashed, unaltered, unstained, and still has its original tags attached. This information will help us move forward with your request.

- **CONV-TEST-0138**: I have worn it once and want to send it back. I am contacting you about my recent purchase. ORD-20378

  Expected `used_item_return` / `escalation_proposed` / `escalation`; got `return_request` / `needs_information` / `None`.

  Actual reply: Hi, I’m Tia from Threadly support.  Thanks for reaching out about your return. Could you please confirm that the item is unworn, unwashed, unaltered, unstained, and still has its original tags? This will help us move forward with your request.

- **CONV-TEST-0258**: I have worn it once and want to send it back. Please explain the next step. ORD-20378

  Expected `used_item_return` / `escalation_proposed` / `escalation`; got `return_request` / `needs_information` / `None`.

  Actual reply: Hi, I’m Tia from Threadly support.  Thanks for reaching out. Before we can proceed, please confirm that the item is unworn, unwashed, unaltered, unstained, and still has its original tags attached. That will help us guide you on the next steps.

- **CONV-CHALLENGE-0018**: Removed tags already, can I still return? ORD-20498

  Expected `used_item_return` / `escalation_proposed` / `escalation`; got `return_outside_window` / `needs_information` / `None`.

  Actual reply: Hi, I’m Tia from Threadly support.  Thanks for reaching out about your return. To proceed, could you please confirm that your item is unworn, unwashed, unaltered, and unstained? Also, since the original tags are required for returns, please let us know if you still have them or if they've been removed. Once I have that information, I can help guide you on the next steps.

- **CONV-CHALLENGE-0148**: Removed tags already, can I still return? Please explain the next step. ORD-20498

  Expected `used_item_return` / `escalation_proposed` / `escalation`; got `return_request` / `needs_information` / `None`.

  Actual reply: Hi, I’m Tia from Threadly support.  Since the original tags have been removed, please confirm whether the item is still unworn, unwashed, unaltered, and unstained. This will help determine the next step for your return.

- **CONV-RESERVE-0039**: A tear was visible before I tried the garment on. ORD-20584

  Expected `damaged_item` / `escalation_proposed` / `escalation`; got `quality_issue` / `escalation_proposed` / `escalation`.

  Actual reply: Hi, I’m Tia from Threadly support.  I'm sorry to hear the garment arrived with a tear. Please add a clear photo of the damage and one of the full item using the photo upload below. If you can't upload a photo right now, you can still request help. While I can't approve a replacement here, I can help you request a review by a Support Expert. Just select "Request a Support Expert" below, and I will save your concern for their review.

- **CONV-RESERVE-0094**: A tear was visible before I tried the garment on. I am contacting you about my recent purchase. ORD-20584

  Expected `damaged_item` / `escalation_proposed` / `escalation`; got `quality_issue` / `escalation_proposed` / `escalation`.

  Actual reply: Hi, I’m Tia from Threadly support.  I’m sorry your item arrived with a tear. Please upload a clear photo of the damage and one of the full item using the photo upload below. If you can’t upload a photo now, you can still ask for help. You can select “Request a Support Expert” below, and they will take a closer look at your concern.

## Method and limits

- The 300 standard test, 200 challenge and 100 reserve cases were all evaluated. Training and curated showcase cases were excluded. All 16 named intents plus unknown requests are covered.
- Cases use their scenario date, explicitly supplied item-condition confirmation, initial order context and customer-owned order allowlist. Follow-ups run sequentially with actual conversation history.
- Every case has its own temporary database; no production customer history or stock was changed. Optional third-party Jev shadows were disabled for this OpenAI-only benchmark.
- Expected labels are used only by the scorer, never passed to the classifier or response writer. Generated replies receive the policy engine's authoritative decision and retrieved policies, as in the project.
- API errors count as failed cases; they are not silently excluded. Each completed case is checkpointed. Hashes record the agent, data, catalogue, policies, taxonomy, date projection and runner.
- The Demo control was rerun against the same current agent code and exactly the same 600 cases. This is a model-mode comparison. It is **not** an old-dataset OpenAI versus new-dataset OpenAI comparison.
- Exact intent labels can overlap semantically. Expected status/action agreement is reported separately. Synthetic templates and repeated phrases mean the samples are correlated; the percentages are not independent production-reliability estimates.
- Automated success does not establish that every generated sentence is grounded or that the user's real issue was resolved. Response tone, omitted details, unsupported assurances and real external fulfilment require additional review.
- The reserve was already evaluated during the earlier Demo comparison and is no longer untouched. These results are a fixed baseline; future tuning needs fresh independent language for a new generalisation claim.

The current local workflow suite also passed **64 tests**. No deployment changes were made by this evaluation.

## Evidence and reproduction

- [Machine-readable summary and failures](../reports/openai_new_dataset/summary.json)
- [All 600 cases and actual replies](../reports/openai_new_dataset/results.jsonl)
- [Model, code and data hashes](../reports/openai_new_dataset/manifest.json)
- [Same-code Demo control](../reports/openai_new_dataset/demo_control.json)

```bash
# Runs billed API calls. Resumes only a matching recorded run.
.venv/bin/python scripts/evaluate_openai_dataset.py
# Renders this report without API calls.
.venv/bin/python scripts/report_openai_evaluation.py
```
