"""Run held-out conversations. Exports actual results, not claimed quality scores."""
import argparse
import json
import tempfile
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from agent import Agent, load

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['train','validation','test','all'],default='test')
    parser.add_argument('--mode',choices=['Demo','OpenAI','Ollama'],default='Demo')
    parser.add_argument('--date',default='2026-09-17')
    args=parser.parse_args();load_dotenv()
    rows=[r for r in load('support_conversations') if args.split=='all' or r['Split']==args.split]
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        agent=Agent(Path(temp)/'eval.sqlite',mode=args.mode)
        for row in rows:
            # Only message and explicitly mapped order context go into the agent.
            result=agent.chat(row['Customer_Message'],{'order_id':row['Order_ID']},today=date.fromisoformat(args.date),session=row['Conversation_ID'])
            results.append({'conversation_id':row['Conversation_ID'],'expected_intent':row['Intent'],
                'expected_action':row['Expected_Action'],'expected_escalation':row['Escalate'],
                'intent_correct':result['intent']==row['Intent'],'actual':result,
                'manual_rubric_scores':{r['Dimension']:None for r in load('evaluation_rubric')}})
        agent.db.close()
    summary={'mode':args.mode,'split':args.split,'count':len(results),
        'intent_accuracy':sum(r['intent_correct'] for r in results)/len(results) if results else None,
        'note':'Only intent accuracy is automated. Review grounding, policy, tools, escalation, tone and context manually. Synthetic expected responses may conflict with order status.'}
    out=Path(f'evaluation_{args.mode.lower()}_{args.split}.json');out.write_text(json.dumps({'summary':summary,'results':results},indent=2))
    print(json.dumps(summary,indent=2));print('Results:',out)
if __name__=='__main__':main()
