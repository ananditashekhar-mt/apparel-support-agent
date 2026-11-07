"""Frozen pre-fix same-model comparison, checkpointed with eight workers."""
import hashlib,json,os,sys,tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from agent import load
from scripts.compare_datasets import definitions,make_agent,matched


def old_native(row,orders,root):
    a=make_agent(root/(row['Conversation_ID']+'.sqlite'),orders,'OpenAI')
    r={'id':row['Conversation_ID'],'expected_intent':row['Intent'],'split':row['Split'],'message':row['Customer_Message']}
    try:
        reply=a.chat(row['Customer_Message'],{'order_id':row['Order_ID']},today=date(2026,9,17),session=row['Conversation_ID'],
            customer_id=row['Customer_ID'],allowed_order_ids=[row['Order_ID']])
        r.update(intent_correct=reply['intent']==row['Intent'],actual_intent=reply['intent'],actual_status=reply['status'],
            actual_pending=(reply.get('pending') or {}).get('kind'),response=reply['response'],usage=reply.get('usage'))
    except Exception as error:r.update(intent_correct=False,error=type(error).__name__,http_status=getattr(error,'status_code',None))
    finally:a.db.close()
    return {'key':'native-'+row['Conversation_ID'],'kind':'native_old','result':r}


def matched_group(label,orders,key,root):
    return {'key':label+'-'+key,'kind':'matched','dataset':label,
        'result':matched(orders,label,root,'OpenAI',3,only={key})}


def main():
    load_dotenv(ROOT/'.env',override=True);os.environ['JEV_SHADOW_ENABLED']='false'
    folder=ROOT/'reports/openai_old_new_baseline';folder.mkdir(exist_ok=True)
    manifest={'model':os.environ['OPENAI_MODEL'],'agent_sha256':hashlib.sha256((ROOT/'agent.py').read_bytes()).hexdigest(),
        'dataset_sha256':hashlib.sha256((ROOT/'data/support_conversations.json').read_bytes()).hexdigest()}
    path=folder/'manifest.json'
    if path.exists():
        old=json.loads(path.read_text())
        for key,val in manifest.items():assert old[key]==val,key
    else:path.write_text(json.dumps(dict(manifest,started_utc=datetime.now(timezone.utc).isoformat()),indent=2)+'\n')
    cached=folder/'checkpoints.jsonl'
    results=[json.loads(l) for l in cached.read_text().splitlines()] if cached.exists() else []
    done={r['key'] for r in results}
    old_orders=json.loads((ROOT/'data/archive/original/orders.json').read_text());new_orders=load('orders')
    rows=[r for r in json.loads((ROOT/'data/archive/original/support_conversations.json').read_text()) if r['Split'] in ('test','validation')]
    with tempfile.TemporaryDirectory() as t,ThreadPoolExecutor(max_workers=8) as pool,cached.open('a') as output:
        root=Path(t);futures=[]
        for row in rows:
            if 'native-'+row['Conversation_ID'] not in done:futures.append(pool.submit(old_native,row,old_orders,root))
        for label,orders in [('old',old_orders),('new',new_orders)]:
            for spec in definitions():
                if label+'-'+spec['key'] not in done:futures.append(pool.submit(matched_group,label,orders,spec['key'],root))
        for future in as_completed(futures):
            r=future.result();results.append(r);output.write(json.dumps(r,ensure_ascii=False)+'\n');output.flush()
            if len(results)%10==0:print(json.dumps({'completed_groups':len(results),'planned_groups':len(rows)+2*len(definitions())}),flush=True)
    native=[r['result'] for r in results if r['kind']=='native_old'];probes={label:[case for r in results if r['kind']=='matched' and r['dataset']==label for case in r['result']['results']] for label in ['old','new']}
    new=json.loads((ROOT/'reports/openai_new_dataset/summary.json').read_text())
    assert new['metadata']['agent_sha256']==manifest['agent_sha256']
    summary={'manifest':manifest,'old_native':{'count':len(native),'intent_passed':sum(r['intent_correct'] for r in native),
        'intent_accuracy':round(100*sum(r['intent_correct'] for r in native)/len(native),2),'api_errors':sum(bool(r.get('error')) for r in native)},
        'new_native':new['overall'],'matched':{label:{'count':len(cases),'passed':sum(r['success'] for r in cases),
        'percent':round(100*sum(r['success'] for r in cases)/len(cases),2),'failures':[r for r in cases if not r['success']]} for label,cases in probes.items()}}
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    assert hashlib.sha256((ROOT/'agent.py').read_bytes()).hexdigest()==manifest['agent_sha256'],'Agent changed during baseline'
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
