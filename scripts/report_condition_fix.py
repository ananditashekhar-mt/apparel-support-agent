"""Render the frozen comparison and condition-fix results without API calls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
baseline=json.loads((ROOT/'reports/openai_old_new_baseline/summary.json').read_text())
before=json.loads((ROOT/'reports/openai_new_dataset/summary.json').read_text())
after=json.loads((ROOT/'reports/openai_condition_fix/summary.json').read_text())
r=after['regression'];fresh=after['fresh']

def metric(x):return f"{x['passed']}/{x['total']} — {x['percent']:.2f}%"

text=f'''# Same-model comparison and item-condition fix — 7 November 2026

## Same-model old/new comparison before the fix

Both datasets used **{baseline['manifest']['model']}**, the same frozen agent code, policies and catalogue. The new 600-case run was reused with a matching code hash; the 124 archived evaluation cases and 210 matched probes were run before changing the agent.

| Measurement | Old dataset | New dataset |
| --- | ---: | ---: |
| Native evaluation intent accuracy | {baseline['old_native']['intent_passed']}/{baseline['old_native']['count']} — {baseline['old_native']['intent_accuracy']:.2f}% | {metric(baseline['new_native']['intent_accuracy'])} |
| Matched workflow success, 35 scenarios × 3 samples each | {baseline['matched']['old']['passed']}/105 — {baseline['matched']['old']['percent']:.2f}% | {baseline['matched']['new']['passed']}/105 — {baseline['matched']['new']['percent']:.2f}% |

The native question sets differ in wording, size and class mix, and old labels have known inconsistencies. Their native accuracy difference cannot establish that changing the data improved the model. The matched results are close, with one more failed case on the new data. This does **not** demonstrate an accuracy benefit from the dataset change; the new dataset's demonstrated benefits are coherent records, broader scenarios, more natural identities and a stronger test fixture.

Both matched sets misclassified “The order is a partial delivery.” as delivery_delay instead of missing_item, while still reaching the expected escalation. The new matched set additionally missed a tag-removal return, which motivated the fix below. This is a single model pass with correlated templates, not an estimate of statistical superiority.

## Root cause and implementation

The previous classifier emitted only an intent and order/size/colour fields. The policy engine therefore depended on the model choosing used_item_return to know the item had been worn or its tags removed. When the model chose return_request, that condition information was lost and the code asked the customer to confirm eligibility.

The fix makes condition a separate structured fact:

- The model extracts explicitly disclosed worn, washed, tags_removed, altered and stained conditions, alongside the intent. It receives the intent taxonomy and instructions distinguishing actual disclosures from negations, hypothetical questions, indoor try-ons and shipping packaging.
- The policy engine combines those disclosures with the selected order's conversation memory. Return requests with known condition issues take the used-item review route. Exchanges and fit requests retain their intent but also go to condition review.
- A later generic confirmation cannot erase the earlier disclosure. Selecting a different order clears that order's condition memory. Memory persists with the saved conversation; this does not implement a new account-wide condition database across unrelated chats.
- Customer replies explain the disclosed condition, including missing original tags, and offer a Support Expert review. They do not automatically approve a standard return or exchange.
- The Streamlit agent cache version was changed so a rerun creates an agent with the new logic. No hosted deployment was performed.

Policies and the 600 regression case labels were not rewritten to raise scores. Optional third-party shadows were disabled for these OpenAI-only runs.

## Before/after on the same 600 cases

| Measurement | Before fix | After fix |
| --- | ---: | ---: |
| Exact intent accuracy | {metric(before['overall']['intent_accuracy'])} | {metric(r['intent_accuracy'])} |
| Expected policy status/action | {metric(before['overall']['outcome_accuracy'])} | {metric(r['outcome_accuracy'])} |
| Strict intent + policy outcome | {metric(before['overall']['strict_success'])} | {metric(r['strict_success'])} |
| Used/tagless return strict success | {metric(before['by_intent']['used_item_return']['strict_success'])} | {metric(after['regression_by_intent']['used_item_return']['strict_success'])} |

API failures after the fix: **{r['api_failures']}**. Conditional mock proposal confirmation/idempotency: **{r['mock_confirmations']['passed']}/{r['mock_confirmations']['attempted']}** passed. These are local requests, not real refunds, shipments or external support notifications.

The richer classification prompt increases usage: the 600-case run recorded **{before['overall']['tokens']['input_tokens']:,} input tokens before** and **{r['tokens']['input_tokens']:,} after**. These counts exclude the additional fresh tests. No monetary cost is inferred without current configured pricing.

## Fresh condition checks

The 60 case definitions were authored and saved **before implementing the fix**. They cover actual disclosures, eligible negatives, exchanges, ambiguous policy questions, follow-up confirmations and switching orders. They were authored by the implementer and are a focused test suite, not an external blind benchmark. Multiple cases share order records to test language/condition handling rather than population diversity.

Strict intent + policy success: **{fresh['passed']}/{fresh['count']} — {fresh['percent']:.2f}%**. Expected policy outcomes: **{fresh['outcome_passed']}/{fresh['count']}**. API failures: **{fresh['api_errors']}**.

| Fresh category | Cases | Strict success | Correct policy outcomes |
| --- | ---: | ---: | ---: |
'''
for kind,v in after['fresh_by_kind'].items():text+=f"| {kind} | {v['count']} | {v['passed']}/{v['count']} — {v['percent']:.2f}% | {v['outcome_passed']}/{v['count']} |\n"
text+='''
## Remaining failures

'''
if not after['failures']:text+='No scored failures in this run. This does not guarantee flawless natural-language behaviour.\n\n'
else:
 for f in after['failures']:
  text+=f"- **{f['id']}**: {f['message']} Expected `{f['expected_intent']}` / `{f['expected_status']}` / `{f['expected_pending']}`; got `{f.get('actual_intent')}` / `{f.get('actual_status')}` / `{f.get('actual_pending')}`.\n\n"
text+='''## Verification and limits

The local suite passes **70 tests**, including wrong classifier intent plus explicit condition facts, confirmation bypass attempts, exchange eligibility, tracking after a condition disclosure and isolation when changing orders.

The 600 known cases are regression tests after this targeted fix. The 60 fresh examples provide additional evidence, but neither set establishes production reliability. A single model pass can vary across runs. Automated scores check intent/status/action fields; they do not fully score every generated sentence, tone, factual omission or actual issue resolution. Condition extraction still depends on understanding the customer's disclosure. Undisclosed use cannot be detected without evidence or inspection. Saved condition flags are scoped to the order within a conversation, not a global customer history across new chats.

The pre-fix same-model comparison and post-fix regression are kept separate, with code hashes, to avoid crediting a code change to a dataset change. Do not combine these runs into one success rate.

## Evidence

- [Pre-fix old/new OpenAI comparison](../reports/openai_old_new_baseline/summary.json)
- [Pre-fix comparison checkpoints and actual replies](../reports/openai_old_new_baseline/checkpoints.jsonl)
- [Post-fix regression/fresh summary and failures](../reports/openai_condition_fix/summary.json)
- [All post-fix actual replies](../reports/openai_condition_fix/results.jsonl)
- [Fresh case definitions](../data/evaluation/condition_fresh_cases.json)

Reproduction scripts are `scripts/benchmark_openai_comparison.py`, `scripts/evaluate_condition_fix.py` and `scripts/report_condition_fix.py`. The API runners resume only when their manifests match, and refuse to mix different code versions into the same report. The baseline must therefore be rerun from its saved code version if starting a new run after the fix. Existing reports remain the frozen evidence.
'''
(ROOT/'docs/openai-comparison-and-condition-fix.md').write_text(text)
print(ROOT/'docs/openai-comparison-and-condition-fix.md')
