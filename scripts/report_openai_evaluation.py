"""Render the recorded new-dataset OpenAI run without making API calls."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'reports/openai_new_dataset'
report=json.loads((FOLDER/'summary.json').read_text())
demo=json.loads((FOLDER/'demo_control.json').read_text())
rows=[json.loads(line) for line in (FOLDER/'results.jsonl').read_text().splitlines()]
overall=report['overall'];meta=report['metadata']
assert len(rows)==meta['planned_cases']==600
assert meta['agent_sha256']==demo['agent_sha256']

def display(m):return f"{m['passed']}/{m['total']} — {m['percent']:.2f}%"

text=f'''# OpenAI evaluation on the new dataset — 7 November 2026

Completed the actual OpenAI classification → policy engine → response composition path for **600 cases**, using **{meta['model']}**. The updated API key works. This is a local agent evaluation against synthetic records, not a test of the deployed Streamlit endpoint or external commerce services.

## Overall results

| Measurement | Demo, same 600 cases and current code | OpenAI |
| --- | ---: | ---: |
| Intent-label accuracy | {display(demo['overall']['intent_correct'])} | {display(overall['intent_accuracy'])} |
| Expected policy status + proposed action | {display(demo['overall']['outcome_correct'])} | {display(overall['outcome_accuracy'])} |
| Strict intent + policy status + action | {display(demo['overall']['joint_success'])} | {display(overall['strict_success'])} |
| Escalation-label agreement | {display(demo['overall']['escalation_label_agreement'])} | {display(overall['escalation_agreement'])} |

OpenAI intent accuracy differs from Demo by **{overall['intent_accuracy']['percent']-demo['overall']['intent_correct']['percent']:+.2f} percentage points** on the identical question set. Policy-outcome agreement differs by **{overall['outcome_accuracy']['percent']-demo['overall']['outcome_correct']['percent']:+.2f} percentage points**.

API failures: **{overall['api_failures']}**. Successful model calls: **{overall['tokens']['requests']}**, excluding the initial two-call connectivity probe. Recorded token usage: **{overall['tokens']['input_tokens']:,} input**, **{overall['tokens']['output_tokens']:,} output**. No monetary cost is inferred without configured pricing.

Mock request persistence/idempotency: **{overall['mock_confirmations']['passed']}/{overall['mock_confirmations']['attempted']}** passed. These are local return/exchange/cancellation/escalation requests, not actual fulfilment or refunds. Only correctly proposed actions were confirmed; this conditional rate does not count missed proposals as successful workflows.

## Evaluation partitions

| Partition | Cases | Intent accuracy | Status/action agreement | Strict success | API failures |
| --- | ---: | ---: | ---: | ---: | ---: |
'''
for split,s in report['by_split'].items():
 text+=f"| {split} | {s['count']} | {display(s['intent_accuracy'])} | {display(s['outcome_accuracy'])} | {display(s['strict_success'])} | {s['api_failures']} |\n"
text+='''
## Use-case results

| Intent | Cases | Intent accuracy | Status/action agreement | Strict success |
| --- | ---: | ---: | ---: | ---: |
'''
for intent,s in report['by_intent'].items():
 text+=f"| {intent} | {s['count']} | {display(s['intent_accuracy'])} | {display(s['outcome_accuracy'])} | {display(s['strict_success'])} |\n"
text+='''
## Failures preserved for review

No prompts, agent rules, policy files or expected labels were changed to improve this run's results. Failure counts below are descriptive and include repeated wording across different orders.

| Expected intent | Actual intent | Actual status | Cases |
| --- | --- | --- | ---: |
'''
for pattern,n in Counter((r['expected_intent'],r.get('actual_intent',r.get('error')),r.get('actual_status','API error')) for r in rows if not r['strict_success']).most_common():
 text+='| '+' | '.join(str(x) for x in pattern)+f' | {n} |\n'
text+='''
Representative failed messages and actual replies:

'''
seen=set()
for r in rows:
 if r['strict_success']:continue
 key=(r['message'].rsplit(' ORD-',1)[0],r.get('actual_intent'),r.get('actual_status'))
 if key in seen:continue
 seen.add(key)
 text+=f"- **{r['id']}**: {r['message']}\n\n  Expected `{r['expected_intent']}` / `{r['expected_status']}` / `{r['expected_pending']}`; got `{r.get('actual_intent')}` / `{r.get('actual_status')}` / `{r.get('actual_pending')}`.\n\n"
 if r['turns']:text+='  Actual reply: '+r['turns'][-1]['response'].replace('\n',' ')+'\n\n'
 if len(seen)>=10:break
text+='''## Method and limits

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
'''
(ROOT/'docs/openai-new-dataset-evaluation.md').write_text(text)
status=ROOT/'reports/openai_evaluation_status.json'
old=json.loads(status.read_text()) if status.exists() else None
status.write_text(json.dumps({'date':'2026-11-07','configured_model':meta['model'],'status':'completed',
    'successful_live_samples':overall['completed_without_api_error'],'api_failures':overall['api_failures'],
    'summary_path':'reports/openai_new_dataset/summary.json',
    'previous_probe_failure':{'http_status':401,'error_code':'expired_secret_key'},
    'note':'Updated key verified. Full 600-case OpenAI evaluation completed; prior expired-key result was historical.'},indent=2)+'\n')
print(ROOT/'docs/openai-new-dataset-evaluation.md')
