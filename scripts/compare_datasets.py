"""Reproducible Demo evaluation and identical policy probes on old/new data.

Does not tune the agent or generate expected outcomes from its answers. Native
old labels are reported as agreement only; matched probes have explicit expected
status/actions. Each matched probe uses an isolated DB and confirms successful
proposals to verify local request persistence. No external support is contacted.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import agent as runtime
from evaluation_checks import audit_references


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def percentage(values):return round(100*sum(values)/len(values),2) if values else None


def make_agent(path,orders,mode):
    instance=runtime.Agent(path,mode=mode)
    instance.orders={order['Order_ID']:order for order in orders}
    return instance


def native(orders,rows,label,root):
    a=make_agent(root/(label+'-native.sqlite'),orders,'Demo')
    results=[]
    for row in rows:
        day=date.fromisoformat(row.get('As_Of','2026-09-17'))
        memory={'order_id':row.get('Input_Order_ID',row['Order_ID'])}
        cid=row.get('Customer_ID','anonymous')
        allowed=row.get('Allowed_Order_IDs',[row['Order_ID']])
        try:
            r=a.chat(row['Customer_Message'],memory,today=day,condition_ok=row.get('Condition_OK',False),
                session=row['Conversation_ID'],customer_id=cid,allowed_order_ids=allowed)
            for text in row.get('Follow_Up_Messages',[]):
                r=a.chat(text,r['memory'],history=a.messages(row['Conversation_ID'],cid),today=day,
                    condition_ok=row.get('Condition_OK',False),session=row['Conversation_ID'],customer_id=cid,allowed_order_ids=allowed)
            pending=(r.get('pending') or {}).get('kind')
            intent_ok=r['intent']==row['Intent']
            has_outcome='Expected_Status' in row
            outcome_ok=r['status']==row.get('Expected_Status') and pending==row.get('Expected_Pending_Kind') if has_outcome else None
            escalate=row['Escalate'].lower()
            results.append({'id':row['Conversation_ID'],'split':row['Split'],'intent':row['Intent'],
                'test_kind':row.get('Test_Kind'),'message':row['Customer_Message'],
                'intent_correct':intent_ok,'outcome_correct':outcome_ok,
                'joint_success':intent_ok and outcome_ok if has_outcome else None,
                'escalation_label_agreement':(pending=='escalation')==(escalate=='yes') if escalate in ('yes','no') else None,
                'expected_status':row.get('Expected_Status'),'expected_pending':row.get('Expected_Pending_Kind'),
                'actual_intent':r['intent'],'actual_status':r['status'],'actual_pending':pending,'response':r['response']})
        except Exception as error:
            results.append({'id':row['Conversation_ID'],'split':row['Split'],'intent':row['Intent'],
                'intent_correct':False,'outcome_correct':False if 'Expected_Status' in row else None,
                'joint_success':False if 'Expected_Status' in row else None,'error':type(error).__name__})
    a.db.close()
    groups=defaultdict(list)
    for r in results:groups[r['split']].append(r)
    return {'overall':summarize(results),'by_split':{k:summarize(v) for k,v in groups.items()},
        'by_intent':{intent:summarize([r for r in results if r['intent']==intent]) for intent in sorted({r['intent'] for r in results})},
        'audit':audit_references(rows,{o['Order_ID']:o for o in orders}),'results':results}


def summarize(rows):
    output={'count':len(rows),'unique_messages':len({r.get('message','') for r in rows})}
    for key in ('intent_correct','outcome_correct','joint_success','escalation_label_agreement','success'):
        scored=[r[key] for r in rows if r.get(key) is not None]
        output[key]={'passed':sum(scored),'total':len(scored),'percent':percentage(scored)} if scored else None
    return output


# Same scenario definitions, messages, conditions and expected outcomes for BOTH datasets.
# Values are written before execution. No expected labels come from an agent run.
def definitions():
    specs=[]
    def add(key,intent,status,age,expected,pending,messages,**extra):
        specs.append(dict(key=key,intent=intent,order_status=status,age=age,expected_status=expected,
            expected_pending=pending,messages=messages,**extra))
    for status in ('Confirmed','In Transit','Out for Delivery','Delivered'):
        add('tracking-'+status,'order_tracking',status,2,'answered',None,
            ['Where is my order?','Could you track my parcel?','What is the shipping status?'])
    add('delay','delivery_delay','Delayed',None,'escalation_proposed','escalation',
        ['My parcel is late.','The promised date has passed.','Delivery is delayed; please investigate.'])
    add('delivery-disputed','delivered_not_received','Delivered',1,'escalation_proposed','escalation',
        ['Marked delivered but not received.','The courier says delivered; I never received it.','I have not received the package despite the delivery notification.'])
    for intent,issue in [('damaged_item','Damaged'),('wrong_item','Wrong Item'),('quality_issue','Quality Issue')]:
        for age in (7,8):
            messages={'damaged_item':['The item arrived damaged.','I found a torn garment in the package.','There is damage on the garment.'],
                'wrong_item':['The wrong item arrived.','I received an incorrect garment.','You sent the wrong product.'],
                'quality_issue':['I have a quality concern.','The fabric quality is poor.','The stitching has a quality issue.']}[intent]
            add(intent+f'-day{age}',intent,'Delivered',age,'escalation_proposed','escalation',messages,issue=issue)
    add('partial-delivery','missing_item','Delivered',2,'escalation_proposed','escalation',
        ['One item is missing.','The order is a partial delivery.','Only one item arrived out of two.'],issue='Partial Delivery')
    for age in (29,30,31,40):
        intent='return_request' if age<=30 else 'return_outside_window'
        add('return-day'+str(age),intent,'Delivered',age,'confirmation_required' if age<=30 else 'escalation_proposed','return' if age<=30 else 'escalation',
            ['I want to return this.','Please arrange a return.','Can you help me return my purchase?'] if age<=30 else
            ['Can I return after 30 days?','I need a return outside window.','Please review a return after 30 days.'],condition=True)
    add('condition-missing','return_request','Delivered',5,'needs_information',None,
        ['I want to return this.','Can I return this purchase?','Please start a return.'],condition=False)
    add('condition-followup','return_request','Delivered',5,'confirmation_required','return',
        ['I want to return this.','Can I return this purchase?','Please start a return.'],condition=False,follow_condition=True)
    add('washed-item','used_item_return','Delivered',6,'escalation_proposed','escalation',
        ['Can I return this washed item?','I removed tags and want to send it back.','I have worn it once; can I send it back?'])
    for kind in ('size','color'):
        for available in (True,False):
            add('exchange-'+kind+('-available' if available else '-unavailable'),'exchange_'+kind,'Delivered',5,
                'confirmation_required' if available else 'blocked','exchange' if available else None,
                ['I need a size exchange.','Please exchange this for another size.','Can you check a size exchange?'] if kind=='size' else
                ['I need a colour exchange.','Please exchange this for another colour.','Can you check a color exchange?'],condition=True,exchange=kind,available=available)
    add('size-followup','exchange_size','Delivered',5,'confirmation_required','exchange',
        ['I want a size exchange.','Could you exchange the size?','Please arrange a size exchange.'],condition=True,exchange='size',available=True,follow_size=True)
    add('fit','fit_issue','Delivered',4,'needs_information',None,
        ['The fit is too tight.','This garment is too loose.','It does not fit me.'],condition=True)
    for status in ('Confirmed','Shipped','Cancelled'):
        add('cancel-'+status,'cancel_order',status,None,'confirmation_required' if status=='Confirmed' else 'blocked' if status=='Shipped' else 'answered',
            'cancellation' if status=='Confirmed' else None,['Cancel this order.','Please cancel my purchase.','I need to cancel this.'])
    for intent in ('refund_status','price_adjustment'):
        add(intent,intent,'Delivered',12,'escalation_proposed','escalation',
            ['Where is my refund?','Please check my refund status.','I need a refund update.'] if intent=='refund_status' else
            ['The price dropped after purchase.','Can I request a price adjustment?','This product is cheaper now.'])
    add('unrelated','unknown','Delivered',2,'needs_information',None,
        ['Can you book a flight for me?','Tell me a recipe for dinner.','Who won the cricket match?'])
    for kind in ('unknown-id','foreign-order','no-order-context'):
        add(kind,'order_tracking','Delivered',2,'needs_information',None,
            ['Where is my order?','Could you track my parcel?','What is the shipping status?'],identity=kind)
    return specs


def exchange_target(order,catalog,kind,available):
    candidates=[v for v in catalog if v['SKU']==order['SKU'] and v['Status']=='Active' and v['Stock_Qty']>=order['Qty'] and
        ((v['Size']!=order['Size'] and v['Colour']==order['Colour']) if kind=='size' else (v['Colour']!=order['Colour'] and v['Size']==order['Size']))]
    if available:return candidates[0] if candidates else None
    values=sorted({v['Size' if kind=='size' else 'Colour'] for v in catalog})
    key='Size' if kind=='size' else 'Colour'
    for value in values:
        if value!=order[key] and not any(v[key]==value for v in candidates):
            return dict(order,**{key:value})
    return None


def matched(orders,label,root,mode,repeats,only=None):
    catalog=runtime.load('product_catalog');results=[]
    for spec in definitions():
        if only and spec['key'] not in only:continue
        candidates=[]
        for order in orders:
            if order['Order_Status']!=spec['order_status']:continue
            if spec.get('issue') and order.get('Issue_Type')!=spec['issue']:continue
            target=exchange_target(order,catalog,spec['exchange'],spec['available']) if spec.get('exchange') else None
            if spec.get('exchange') and not target:continue
            if order.get('Delivered_Date'):
                day=date.fromisoformat(order['Delivered_Date'][:10])+timedelta(days=spec['age'] or 0)
                if label=='new' and day>date(2026,12,31):continue
            else:day=date.fromisoformat(order.get('Snapshot_Date','2026-09-17'))
            candidates.append((order,target,day))
        if not candidates:raise ValueError('No candidates for '+label+' '+spec['key'])
        for index in range(repeats):
            order,target,day=candidates[index%len(candidates)]
            oid=order['Order_ID'];cid=order['Customer_ID'];identity=spec.get('identity')
            message=spec['messages'][index%len(spec['messages'])]
            memory={} if identity else {'order_id':oid}
            if identity=='unknown-id':message+=' ORD-999999'
            if identity=='foreign-order':message+=' '+next(o['Order_ID'] for o in orders if o['Customer_ID']!=cid)
            if target and not spec.get('follow_size'):
                message+=' Requested '+('size '+target['Size'] if spec['exchange']=='size' else 'colour '+target['Colour'])+'.'
            turns=[{'message':message,'condition':spec.get('condition',False)}]
            if spec.get('follow_condition'):turns.append({'message':'Yes, condition confirmed','condition':True})
            if spec.get('follow_size'):turns.append({'message':'Size '+target['Size'],'condition':True})
            session=f"{label}-{spec['key']}-{index}"
            a=make_agent(root/(session+'.sqlite'),orders,mode)
            row={'scenario':spec['key'],'intent':spec['intent'],'order_id':oid,'customer_id':cid,
                 'as_of':day.isoformat(),'message':message,'turns':turns,'expected_status':spec['expected_status'],
                 'expected_pending':spec['expected_pending'],'mode':mode,'model':a.model.model if mode!='Demo' else None}
            try:
                for turn in turns:
                    r=a.chat(turn['message'],memory,history=a.messages(session,cid),today=day,condition_ok=turn['condition'],session=session,
                        customer_id=cid,allowed_order_ids=[o['Order_ID'] for o in orders if o['Customer_ID']==cid])
                    memory=r['memory']
                pending=(r.get('pending') or {}).get('kind')
                row.update(actual_intent=r['intent'],actual_status=r['status'],actual_pending=pending,response=r['response'],
                    intent_correct=r['intent']==spec['intent'],outcome_correct=r['status']==spec['expected_status'] and pending==spec['expected_pending'])
                row['proposal_persisted']=None
                if row['outcome_correct'] and pending:
                    request=a.confirm(r,session)
                    row['proposal_persisted']=bool(a.actions(session)) and a.confirm(r,session)==request
                row['success']=row['intent_correct'] and row['outcome_correct'] and row['proposal_persisted'] is not False
            except Exception as error:
                row.update(success=False,intent_correct=False,outcome_correct=False,error=type(error).__name__,http_status=getattr(error,'status_code',None))
            finally:a.db.close()
            results.append(row)
            if mode!='Demo':print(json.dumps({'dataset':label,'scenario':spec['key'],'success':row['success'],'error':row.get('error')}),flush=True)
    by_intent={i:summarize([r for r in results if r['intent']==i]) for i in sorted({r['intent'] for r in results})}
    return {'overall':summarize(results),'by_intent':by_intent,'results':results}


def quality(orders,rows,customers):
    catalog={(r['SKU'],r['Size'],r['Colour']):r for r in runtime.load('product_catalog')}
    audit=audit_references(rows,{o['Order_ID']:o for o in orders})
    represented=[(o,catalog[(o['SKU'],o['Size'],o['Colour'])]) for o in orders if (o['SKU'],o['Size'],o['Colour']) in catalog]
    return {'customers':len(customers),'distinct_customer_names':len({c['Name'] for c in customers}),
        'orders':len(orders),'conversations':len(rows),
        'post_delivery_cases_linked_to_undelivered_orders':len(audit['reference_cases_needing_review']),
        'identical_messages_shared_between_train_and_test':len(audit['distinct_messages_shared_between_train_and_test']),
        'orders_without_current_catalogue_variant':len(orders)-len(represented),
        'represented_variant_orders':len(represented),
        'unexplained_unit_price_times_quantity_differences':sum(o['Order_Total_INR']!=p['Price_INR']*o['Qty'] for o,p in represented)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['Demo','OpenAI'],default='Demo')
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1:parser.error('--repeats must be positive')
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    archive=ROOT/'data/archive/original'
    old_orders=read(archive/'orders.json');new_orders=runtime.load('orders')
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'mode':args.mode,
        'agent_sha256':digest(ROOT/'agent.py'),'generator_sha256':digest(ROOT/'scripts/build_dataset.py'),
        'data_hashes':{'old_orders':digest(archive/'orders.json'),'new_orders':digest(ROOT/'data/orders.json'),
            'old_conversations':digest(archive/'support_conversations.json'),'new_conversations':digest(ROOT/'data/support_conversations.json')},
        'method':'Same current agent, catalogue, policy and input conditions on both datasets. Independent expected statuses/actions for identical matched probes. Isolated DB per probe, local proposal confirmation and idempotency check. No fixes after observing these evaluations.'}
    report['data_quality']={'old':quality(old_orders,read(archive/'support_conversations.json'),read(archive/'customers.json')),
        'new':quality(new_orders,runtime.load('support_conversations'),runtime.load('customers'))}
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        if args.mode=='Demo':
            old_rows=[r for r in read(archive/'support_conversations.json') if r['Split'] in ('test','validation')]
            new_rows=[r for r in runtime.load('support_conversations') if r['Split'] in ('test','challenge','reserve')]
            report['native']={'old':native(old_orders,old_rows,'old',root),'new':native(new_orders,new_rows,'new',root)}
        # Bounded live sample: one of each major path; Demo tests every definition.
        live_keys={'tracking-Delivered','return-day30','return-day31','exchange-size-available',
                   'exchange-color-unavailable','damaged_item-day7','partial-delivery','cancel-Confirmed',
                   'refund_status','foreign-order','condition-followup','size-followup'}
        report['matched']={label:matched(orders,label,root,args.mode,args.repeats,live_keys if args.mode!='Demo' else None)
            for label,orders in [('old',old_orders),('new',new_orders)]}
    folder=ROOT/'reports';folder.mkdir(exist_ok=True)
    out=folder/f'dataset_comparison_{args.mode.lower()}.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'native':{k:v['overall'] for k,v in report.get('native',{}).items()},
                     'matched':{k:v['overall'] for k,v in report['matched'].items()},'report':str(out)},indent=2))

if __name__=='__main__':main()
