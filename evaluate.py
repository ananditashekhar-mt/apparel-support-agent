"""Run held-out conversations. Exports actual results, not claimed quality scores."""
import argparse
import json
import tempfile
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from agent import Agent, load
from evaluation_checks import audit_references, score_reference

def evaluate_free_form(mode='Demo', as_of=None):
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        agent=Agent(Path(temp)/'free-form.sqlite',mode=mode)
        for row in load('free_form_conversations'):
            memory={};turns=[]
            for message in row['messages']:
                result=agent.chat(message,memory,history=agent.messages(row['id']),
                    session=row['id'],today=date.fromisoformat(as_of) if as_of else None)
                memory=result['memory'];turns.append(result)
            checks={
                'intent':result['intent']==row['intent'],
                'status':not row['status'] or result['status']==row['status'],
                'order_context':result['order_id']==row['order_id'],
                'response':all(t in result['response'] for t in row['response_contains']) and
                    all(t not in result['response'] for t in row['response_excludes'])}
            results.append({'id':row['id'],'checks':checks,'passed':all(checks.values()),'turns':turns})
        agent.db.close()
    summary={'mode':mode,'count':len(results),'passed':sum(r['passed'] for r in results),
             'note':'Synthetic regression checks for responses, routing and context; not a live quality benchmark.'}
    output=Path(f'evaluation_{mode.lower()}_free_form.json')
    output.write_text(json.dumps({'summary':summary,'results':results},indent=2))
    print(json.dumps(summary,indent=2));print('Results:',output)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['train','showcase','test','challenge','reserve','all','free_form'],default='test')
    parser.add_argument('--mode',choices=['Demo','OpenAI','Ollama'],default='Demo')
    parser.add_argument('--date',default=None,help='Override scenario dates; normally omit.')
    args=parser.parse_args();load_dotenv()
    if args.split=='free_form':
        evaluate_free_form(args.mode,args.date)
        return
    rows=[r for r in load('support_conversations') if args.split=='all' or r['Split']==args.split]
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        agent=Agent(Path(temp)/'eval.sqlite',mode=args.mode)
        for row in rows:
            # Only message and explicitly mapped order context go into the agent.
            result=agent.chat(row['Customer_Message'],{'order_id':row.get('Input_Order_ID',row['Order_ID'])},today=date.fromisoformat(args.date or row['As_Of']),condition_ok=row.get('Condition_OK',False),session=row['Conversation_ID'],customer_id=row['Customer_ID'],allowed_order_ids=row.get('Allowed_Order_IDs',[row['Order_ID']]))
            for follow_up in row.get('Follow_Up_Messages',[]):
                result=agent.chat(follow_up,result['memory'],history=agent.messages(row['Conversation_ID'],row['Customer_ID']),
                    today=date.fromisoformat(args.date or row['As_Of']),condition_ok=row.get('Condition_OK',False),
                    session=row['Conversation_ID'],customer_id=row['Customer_ID'],
                    allowed_order_ids=row.get('Allowed_Order_IDs',[row['Order_ID']]))
            results.append({'conversation_id':row['Conversation_ID'],'expected_intent':row['Intent'],
                'expected_action':row['Expected_Action'],'expected_escalation':row['Escalate'],
                'intent_correct':result['intent']==row['Intent'],
                'outcome_correct':result['status']==row.get('Expected_Status') and (result.get('pending') or {}).get('kind')==row.get('Expected_Pending_Kind'),'reference_label_checks':score_reference(row,result),'actual':result,
                'manual_rubric_scores':{r['Dimension']:None for r in load('evaluation_rubric')}})
        agent.db.close()
    summary={'mode':args.mode,'split':args.split,'count':len(results),
        'outcome_accuracy':sum(r['outcome_correct'] for r in results)/len(results) if results else None,
        'intent_accuracy':sum(r['intent_correct'] for r in results)/len(results) if results else None,
        'escalation_label_agreement':sum(r['reference_label_checks']['escalation_label_agreement'] for r in results if r['reference_label_checks']['escalation_label_agreement'] is not None)/max(1,sum(r['reference_label_checks']['escalation_label_agreement'] is not None for r in results)),
        'fixture_audit':audit_references(load('support_conversations'),agent.orders),
        'note':'Intent accuracy and escalation label agreement are automated. Reference labels need review; agreement is not verified policy correctness. Grounding, tools, tone and context require separate checks.'}
    out=Path(f'evaluation_{args.mode.lower()}_{args.split}.json');out.write_text(json.dumps({'summary':summary,'results':results},indent=2))
    print(json.dumps(summary,indent=2));print('Results:',out)
if __name__=='__main__':main()
