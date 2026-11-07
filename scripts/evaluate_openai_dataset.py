"""Checkpointed evaluation of the 600 new-data test/challenge/reserve cases.

Runs the actual OpenAI understand -> policy -> compose path. Per-case temporary
DBs keep stock and conversations independent. Expected labels never enter the
agent input. No prompts, policies or fixtures are tuned during this run.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from agent import Agent,load


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def metric(rows,key):
    return {'passed':sum(bool(r.get(key)) for r in rows),'total':len(rows),
            'percent':round(100*sum(bool(r.get(key)) for r in rows)/len(rows),2) if rows else None}

def summary(rows):
    successful=[r for r in rows if not r.get('error')]
    return {'count':len(rows),'completed_without_api_error':len(successful),'api_failures':len(rows)-len(successful),
            'intent_accuracy':metric(rows,'intent_correct'),'outcome_accuracy':metric(rows,'outcome_correct'),
            'strict_success':metric(rows,'strict_success'),
            'escalation_agreement':metric(rows,'escalation_correct'),
            'tokens':{key:sum(r.get('usage',{}).get(key,0) for r in rows) for key in ['input_tokens','output_tokens','requests']},
            'mock_confirmations':{'attempted':sum(r.get('confirmation_ok') is not None for r in rows),
                                  'passed':sum(r.get('confirmation_ok') is True for r in rows)}}


def run_case(row,model,root):
    started=time.monotonic()
    result={'id':row['Conversation_ID'],'split':row['Split'],'use_case':row['Use_Case'],
        'variant':row['Scenario_Variant'],'test_kind':row.get('Test_Kind'),'message':row['Customer_Message'],
        'order_id':row['Order_ID'],'customer_id':row['Customer_ID'],'as_of':row['As_Of'],
        'expected_intent':row['Intent'],'expected_status':row['Expected_Status'],
        'expected_pending':row['Expected_Pending_Kind'],'usage':{},'turns':[],'confirmation_ok':None}
    a=None
    try:
        a=Agent(root/(row['Conversation_ID']+'.sqlite'),mode='OpenAI',model=model)
        memory={'order_id':row.get('Input_Order_ID',row['Order_ID'])}
        for text in [row['Customer_Message']]+row.get('Follow_Up_Messages',[]):
            reply=a.chat(text,memory,history=a.messages(row['Conversation_ID'],row['Customer_ID']),
                today=date.fromisoformat(row['As_Of']),condition_ok=row.get('Condition_OK',False),
                session=row['Conversation_ID'],customer_id=row['Customer_ID'],allowed_order_ids=row['Allowed_Order_IDs'])
            memory=reply['memory']
            for key,value in reply.get('usage',{}).items():result['usage'][key]=result['usage'].get(key,0)+value
            result['turns'].append({'message':text,'intent':reply['intent'],'status':reply['status'],
                'pending':(reply.get('pending') or {}).get('kind'),'response':reply['response'],
                'decision_response':reply.get('decision_response')})
        pending=(reply.get('pending') or {}).get('kind')
        result.update(actual_intent=reply['intent'],actual_status=reply['status'],actual_pending=pending,
            intent_correct=reply['intent']==row['Intent'],
            outcome_correct=reply['status']==row['Expected_Status'] and pending==row['Expected_Pending_Kind'],
            escalation_correct=(pending=='escalation')==(row['Escalate']=='Yes'))
        result['strict_success']=result['intent_correct'] and result['outcome_correct']
        if pending and result['outcome_correct']:
            try:
                request=a.confirm(reply,row['Conversation_ID'])
                result['confirmation_ok']=a.confirm(reply,row['Conversation_ID'])==request and bool(a.actions(row['Conversation_ID']))
            except Exception as error:
                result['confirmation_ok']=False;result['confirmation_error']=type(error).__name__
    except Exception as error:
        result.update(error=type(error).__name__,http_status=getattr(error,'status_code',None),
            error_code=getattr(error,'code',None),intent_correct=False,outcome_correct=False,strict_success=False,escalation_correct=False)
    finally:
        if a:a.db.close()
    result['elapsed_seconds']=round(time.monotonic()-started,2)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--limit',type=int,default=None)
    args=parser.parse_args()
    if not 1<=args.workers<=12:parser.error('--workers must be between 1 and 12')
    load_dotenv(ROOT/'.env',override=True)
    # This benchmark is authorised for OpenAI only, not optional third-party shadows.
    os.environ['JEV_SHADOW_ENABLED']='false'
    model=os.environ.get('OPENAI_MODEL','')
    if not model:raise ValueError('OPENAI_MODEL must be configured.')
    rows=[r for r in load('support_conversations') if r['Split'] in ('test','challenge','reserve')]
    if args.limit:rows=rows[:args.limit]
    folder=ROOT/'reports/openai_new_dataset';folder.mkdir(parents=True,exist_ok=True)
    metadata={'mode':'OpenAI','model':model,'agent_sha256':sha(ROOT/'agent.py'),
        'dataset_sha256':sha(ROOT/'data/support_conversations.json'),'orders_sha256':sha(ROOT/'data/orders.json'),
        'catalogue_sha256':sha(ROOT/'data/product_catalog.json'),'policy_sha256':sha(ROOT/'data/policies.json'),
        'taxonomy_sha256':sha(ROOT/'data/intent_taxonomy.json'),'date_projection_sha256':sha(ROOT/'dataset.py'),
        'runner_sha256':sha(Path(__file__)),'planned_cases':len(rows),'shadow_enabled':False}
    manifest=folder/'manifest.json';checkpoint=folder/'results.jsonl'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        for key in metadata:
            if old.get(key)!=metadata[key]:raise ValueError('Existing checkpoint differs: '+key+'; preserve it before starting a new run.')
        metadata=old
    else:
        metadata['started_utc']=datetime.now(timezone.utc).isoformat()
        manifest.write_text(json.dumps(metadata,indent=2)+'\n')
    results=[json.loads(line) for line in checkpoint.read_text().splitlines()] if checkpoint.exists() else []
    done={r['id'] for r in results};pending=[r for r in rows if r['Conversation_ID'] not in done]
    print(json.dumps({'model':model,'planned':len(rows),'already_completed':len(done),'workers':args.workers}),flush=True)
    with tempfile.TemporaryDirectory() as temp,ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,row,model,Path(temp)):row for row in pending}
        with checkpoint.open('a') as output:
            for future in as_completed(futures):
                result=future.result();results.append(result)
                output.write(json.dumps(result,ensure_ascii=False)+'\n');output.flush()
                if len(results)%10==0 or result.get('error'):
                    print(json.dumps({'completed':len(results),'planned':len(rows),'errors':sum(bool(r.get('error')) for r in results),
                        'intent_passed':sum(r['intent_correct'] for r in results),'outcome_passed':sum(r['outcome_correct'] for r in results)}),flush=True)
    report={'metadata':metadata,'finished_utc':datetime.now(timezone.utc).isoformat(),'overall':summary(results),
        'by_split':{split:summary([r for r in results if r['split']==split]) for split in sorted({r['split'] for r in results})},
        'by_intent':{intent:summary([r for r in results if r['expected_intent']==intent]) for intent in sorted({r['expected_intent'] for r in results})},
        'failures':[r for r in results if not r['strict_success']],
        'limits':'Expected intent/status/action agreement, plus local mock confirmation. Response tone and factual grounding require manual review. No live carrier, payment, refund or hosted-site integration is tested. API-error cases count as failures.'}
    (folder/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['overall'],indent=2),flush=True)
    if metadata['agent_sha256']!=sha(ROOT/'agent.py'):raise RuntimeError('Agent changed during evaluation; report requires review.')

if __name__=='__main__':main()
