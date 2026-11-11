"""Paired damage-routing regression: frozen cases, isolated DBs, real OpenAI calls.

Run baseline before editing the classifier, then candidate. Never uses Neon.
These developer-authored cases are regression tests, not independent evaluation.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from agent import load
from scripts.evaluate_openai_dataset import run_case, summary


def cases():
    rows = [r for r in load('support_conversations')
            if r['Split'] in ('test', 'challenge', 'reserve')
            and r['Intent'] in ('damaged_item', 'used_item_return')]
    original = next(r for r in rows if r['Conversation_ID'] == 'CONV-RESERVE-0011')
    messages = [
        ('The sleeve has a rip straight out of the parcel.', 'damaged_item'),
        ('Opened it just now and there is a hole beside the pocket.', 'damaged_item'),
        ('The zipper arrived broken. Can I return this?', 'damaged_item'),
        ('Stitching has come apart at the shoulder before any use.', 'damaged_item'),
        ('One button is cracked on the shirt I received.', 'damaged_item'),
        ('There is a slit in the lining; I have not worn it.', 'damaged_item'),
        ('Unboxing video shows the seam already split.', 'damaged_item'),
        ('Kapda phata hua aaya hai, abhi packet khola.', 'damaged_item'),
        ('Please exchange it: the sleeve was ripped when it arrived.', 'damaged_item'),
        ('I want a refund because the garment arrived torn.', 'damaged_item'),
        ('Return please, it is unused and has no tears or holes.', 'return_request'),
        ('Nothing is damaged. I just changed my mind and want to return it.', 'return_request'),
        ('The box was torn but the shirt is fine. I want to return it.', 'return_request'),
        ('If an item tears, what happens? Mine is fine; return it please.', 'return_request'),
        ('My friend received a torn dress; mine is fine. Return mine please.', 'return_request'),
        ('The print says TEAR IT UP. No damage; I want to return it.', 'return_request'),
        ('I wore it all day and want to return it.', 'used_item_return'),
        ('I washed it yesterday and want to return it.', 'used_item_return'),
        ('Where is my order?', 'order_tracking'),
        ('The fit is fine but I would like to return it.', 'return_request'),
    ]
    for i, (message, intent) in enumerate(messages, 1):
        escalation = intent in ('damaged_item', 'used_item_return')
        status = 'escalation_proposed' if escalation else ('answered' if intent == 'order_tracking' else 'needs_information')
        rows.append(dict(original, Conversation_ID=f'DAMAGE-FRESH-{i:02}',
                         Customer_Message=message + ' ' + original['Order_ID'],
                         Follow_Up_Messages=[], Intent=intent, Condition_OK=False,
                         Expected_Status=status, Expected_Pending_Kind='escalation' if escalation else None,
                         Escalate='Yes' if escalation else 'No', Split='developer_regression'))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['baseline', 'candidate'])
    parser.add_argument('--quality-only', action='store_true', help='Separate quality-boundary regression')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    os.environ['JEV_SHADOW_ENABLED'] = 'false'
    model = os.environ['OPENAI_MODEL']
    folder = ROOT / 'reports/damage_recognition'
    folder.mkdir(exist_ok=True)
    rows = cases()
    if args.quality_only:
        rows = [r for r in load('support_conversations') if r['Split'] in ('test', 'challenge', 'reserve')
                and r['Intent'] == 'quality_issue']
    frozen = json.dumps(rows, ensure_ascii=False, indent=2) + '\n'
    path = folder / ('quality_cases.json' if args.quality_only else 'cases.json')
    if path.exists():
        assert path.read_text() == frozen, 'Cases must stay identical between runs'
    else:
        path.write_text(frozen)
    results = []
    with tempfile.TemporaryDirectory() as temp, ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_case, row, model, Path(temp)) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: r['id'])
    manifest = {'model': model, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                           for p in ['agent.py', 'data/intent_taxonomy.json', 'data/orders.json',
                                     'data/policies.json', 'scripts/evaluate_damage_fix.py',
                                     str(path.relative_to(ROOT))]}}
    report = {'manifest': manifest, 'overall': summary(results),
              'historical_damage': summary([r for r in results if r['expected_intent'] == 'damaged_item' and not r['id'].startswith('DAMAGE')]),
              'fresh': summary([r for r in results if r['id'].startswith('DAMAGE')]),
              'failures': [r for r in results if not r['strict_success']], 'results': results}
    name = args.phase + ('_quality' if args.quality_only else '') + '.json'
    (folder / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('results', 'manifest')}, indent=2))


if __name__ == '__main__':
    main()
