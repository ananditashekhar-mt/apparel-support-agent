"""OpenAI regression + pre-authored fresh condition tests; checkpointed."""
import hashlib,json,os,sys,tempfile,time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from agent import Agent,load
from scripts.evaluate_openai_dataset import run_case,summary


def fresh_cases():
    source=json.loads((ROOT/'data/evaluation/condition_fresh_cases.json').read_text())
    groups=defaultdict(list);catalog=load('product_catalog')
    for o in load('orders'):
        if o['Order_Status']=='Delivered' and not o['Issue_Type']:groups[o['Customer_ID']].append(o)
    pairs=[]
    for orders in groups.values():
        for a in orders:
            alternatives=[v for v in catalog if v['SKU']==a['SKU'] and v['Colour']==a['Colour'] and v['Size']!=a['Size'] and v['Status']=='Active' and v['Stock_Qty']>=a['Qty']]
            if not alternatives:continue
            for b in orders:
                if a['Order_ID']==b['Order_ID']:continue
                da=date.fromisoformat(a['Delivered_Date'][:10]);db=date.fromisoformat(b['Delivered_Date'][:10])
                if abs((da-db).days)<=20 and max(da,db)+timedelta(days=5)<=date(2026,12,31):pairs.append((a,b,alternatives[0],max(da,db)+timedelta(days=5)))
    assert pairs,'Need real customer orders for independent condition checks'
    cases=[]
    for i,case in enumerate(source):
        a,b,target,day=pairs[i%len(pairs)]
        turns=[{'message':case['message']+' '+a['Order_ID'],'condition':case['kind'] in ('eligible_return','eligible_exchange')}]
        final_intent='used_item_return';status='escalation_proposed';pending='escalation'
        if case['kind'] in ('eligible_return','different_order'):final_intent='return_request';status='confirmation_required';pending='return'
        if case['kind']=='clarify':final_intent='return_request';status='needs_information';pending=None
        if case['kind'] in ('used_exchange','eligible_exchange'):
            final_intent='exchange_size';turns[0]['message']+=' Requested size '+target['Size']+'.'
            if case['kind']=='eligible_exchange':status='confirmation_required';pending='exchange'
        if case['kind']=='condition_followup':
            turns.append({'message':case['followup'],'condition':True})
            if case['id']=='M04':final_intent='exchange_size'
        if case['kind']=='different_order':turns.append({'message':case['followup']+' '+b['Order_ID'],'condition':True})
        cases.append(dict(case,order=a['Order_ID'],customer=a['Customer_ID'],allowed=[a['Order_ID'],b['Order_ID']],as_of=day.isoformat(),
            turns=turns,expected_intent=final_intent,expected_status=status,expected_pending=pending))
    return cases


def run_fresh(case,model,root):
    a=Agent(root/('fresh-'+case['id']+'.sqlite'),mode='OpenAI',model=model)
    result={'id':'FRESH-'+case['id'],'kind':case['kind'],'message':case['message'],'expected_intent':case['expected_intent'],
        'expected_status':case['expected_status'],'expected_pending':case['expected_pending'],'turns':[]}
    memory={'order_id':case['order']}
    try:
        for turn in case['turns']:
            r=a.chat(turn['message'],memory,history=a.messages(result['id'],case['customer']),today=date.fromisoformat(case['as_of']),
                condition_ok=turn['condition'],session=result['id'],customer_id=case['customer'],allowed_order_ids=case['allowed'])
            memory=r['memory'];result['turns'].append({'message':turn['message'],'intent':r['intent'],'status':r['status'],
                'pending':(r.get('pending') or {}).get('kind'),'memory':memory,'response':r['response'],'decision_response':r['decision_response']})
        result.update(actual_intent=r['intent'],actual_status=r['status'],actual_pending=(r.get('pending') or {}).get('kind'))
        result['intent_correct']=r['intent']==case['expected_intent']
        result['outcome_correct']=r['status']==case['expected_status'] and result['actual_pending']==case['expected_pending']
        result['success']=result['intent_correct'] and result['outcome_correct']
    except Exception as error:result.update(error=type(error).__name__,http_status=getattr(error,'status_code',None),success=False,intent_correct=False,outcome_correct=False)
    finally:a.db.close()
    return result


def main():
    load_dotenv(ROOT/'.env',override=True);os.environ['JEV_SHADOW_ENABLED']='false';model=os.environ['OPENAI_MODEL']
    folder=ROOT/'reports/openai_condition_fix';folder.mkdir(exist_ok=True)
    manifest={'model':model,'agent_sha256':hashlib.sha256((ROOT/'agent.py').read_bytes()).hexdigest(),
        'fresh_cases_sha256':hashlib.sha256((ROOT/'data/evaluation/condition_fresh_cases.json').read_bytes()).hexdigest(),
        'dataset_sha256':hashlib.sha256((ROOT/'data/support_conversations.json').read_bytes()).hexdigest()}
    path=folder/'manifest.json'
    if path.exists():
        previous=json.loads(path.read_text());assert all(previous[k]==v for k,v in manifest.items())
    else:path.write_text(json.dumps(dict(manifest,started_utc=datetime.now(timezone.utc).isoformat()),indent=2)+'\n')
    checkpoint=folder/'results.jsonl';results=[json.loads(l) for l in checkpoint.read_text().splitlines()] if checkpoint.exists() else []
    done={r['id'] for r in results}
    rows=[r for r in load('support_conversations') if r['Split'] in ('test','challenge','reserve')]
    fresh=fresh_cases()
    with tempfile.TemporaryDirectory() as t,ThreadPoolExecutor(max_workers=8) as pool,checkpoint.open('a') as output:
        root=Path(t);futures={}
        for row in rows:
            if row['Conversation_ID'] not in done:futures[pool.submit(run_case,row,model,root)]='regression'
        for case in fresh:
            if 'FRESH-'+case['id'] not in done:futures[pool.submit(run_fresh,case,model,root)]='fresh'
        for future in as_completed(futures):
            result=future.result();result['suite']=futures[future];results.append(result)
            output.write(json.dumps(result,ensure_ascii=False)+'\n');output.flush()
            if len(results)%20==0:print(json.dumps({'completed':len(results),'planned':660,'api_errors':sum(bool(r.get('error')) for r in results)}),flush=True)
    regression=[r for r in results if r['suite']=='regression'];new=[r for r in results if r['suite']=='fresh']
    def fresh_summary(cases):return {'count':len(cases),'passed':sum(r['success'] for r in cases),'percent':round(100*sum(r['success'] for r in cases)/len(cases),2),
        'outcome_passed':sum(r['outcome_correct'] for r in cases),'api_errors':sum(bool(r.get('error')) for r in cases)}
    report={'manifest':manifest,'regression':summary(regression),
        'regression_by_intent':{intent:summary([r for r in regression if r['expected_intent']==intent]) for intent in sorted({r['expected_intent'] for r in regression})},
        'fresh':fresh_summary(new),'fresh_by_kind':{kind:fresh_summary([r for r in new if r['kind']==kind]) for kind in sorted({r['kind'] for r in new})},
        'failures':[r for r in results if not r.get('strict_success',r.get('success'))]}
    (folder/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    assert hashlib.sha256((ROOT/'agent.py').read_bytes()).hexdigest()==manifest['agent_sha256']
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
