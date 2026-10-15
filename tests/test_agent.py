import sys
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent import Agent,load,retrieve_policy

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.agent=Agent(Path(self.temp.name)/'test.sqlite')
        self.order=next(o for o in self.agent.orders.values() if o['Order_Status']=='Delivered')
        self.day=date.fromisoformat(self.order['Delivered_Date'][:10])
    def tearDown(self):self.agent.db.close();self.temp.cleanup()
    def ask(self,text,**kwargs):
        return self.agent.chat(text,today=kwargs.pop('today',self.day),session='test',**kwargs)
    def test_tracking_and_unknown_order(self):
        r=self.ask('Where is ORD-10003?');self.assertIn('Xpressbees',r['response'])
        self.assertIsNone(self.ask('Where is ORD-99999?')['pending'])
    def test_missing_order(self):self.assertIn('order ID',self.ask('I want to return this')['response'])
    def test_active_order_context_avoids_repeating_order_id(self):
        result=self.agent.chat('Where is my order?',memory={'order_id':'ORD-10003'})
        self.assertIn('ORD-10003',result['response'])
        self.assertEqual([m['role'] for m in self.agent.messages('demo')],['user','assistant'])
    def test_condition_confirmation_continues_return_flow(self):
        first=self.ask('Return '+self.order['Order_ID'])
        result=self.ask('Yes, condition confirmed',memory=first['memory'],condition_ok=True)
        self.assertEqual(result['pending']['kind'],'return');self.assertIn('Eligible for return',result['response'])
    def test_return_condition_and_window_boundaries(self):
        text='Return '+self.order['Order_ID']
        self.assertIsNone(self.ask(text)['pending'])
        r=self.ask(text,condition_ok=True,today=self.day+timedelta(days=30));self.assertEqual(r['pending']['kind'],'return')
        r=self.ask(text,condition_ok=True,today=self.day+timedelta(days=31));self.assertEqual(r['pending']['kind'],'escalation')
    def test_expired_return_feedback_and_single_introduction(self):
        first=self.ask('Return '+self.order['Order_ID'],today=self.day+timedelta(days=68))
        self.assertTrue(first['feedback_required'])
        self.assertTrue(first['response'].startswith('Hi,\nI’m Tia from Threadly support.\n\n'))
        self.assertIn('68 days',first['response'])
        self.assertIn('within 30 days of delivery',first['response'])
        self.assertNotIn('—',first['response'])
        self.assertNotIn('Please confirm',first['response'])
        self.assertNotIn('unwashed',first['response'])
        self.assertNotIn('human-review',first['response'])
        follow=self.ask('Yes, condition confirmed',memory=first['memory'],condition_ok=True,
            history=[{'role':'assistant','content':first['response']}],today=self.day+timedelta(days=68))
        self.assertTrue(follow['feedback_required'])
        self.assertNotIn('Hi, I’m Tia',follow['response'])
        self.assertNotIn('condition rules',follow['response'])

    def test_non_delivered_block(self):
        r=self.ask('Return ORD-10003',condition_ok=True);self.assertEqual(r['status'],'blocked')
    def test_future_delivery(self):
        r=self.ask('Return '+self.order['Order_ID'],condition_ok=True,today=self.day-timedelta(days=1));self.assertEqual(r['pending']['kind'],'escalation')
    def test_missing_carrier_data(self):
        r=self.ask('My order ORD-10003 is late');self.assertIn('unavailable',r['response']);self.assertEqual(r['pending']['kind'],'escalation')
    def test_refunds_and_price_never_execute_payments(self):
        for text in ['Process my refund','The price dropped']:
            self.assertEqual(self.ask(text)['pending']['kind'],'escalation')
    def test_used_item_exception(self):
        self.assertEqual(self.ask('Return my washed item '+self.order['Order_ID'])['pending']['kind'],'escalation')
    def test_cancel_shipped_and_already_cancelled(self):
        self.assertIsNone(self.ask('Cancel ORD-10003')['pending'])
        self.assertEqual(self.ask('Cancel ORD-10001')['status'],'answered')
    def test_confirmation_idempotence_and_session_isolation(self):
        r=self.ask('Return '+self.order['Order_ID'],condition_ok=True)
        a=self.agent.confirm(r,'test');self.assertEqual(a,self.agent.confirm(r,'test'))
        with self.assertRaises(ValueError):self.agent.confirm(r,'someone_else')
        self.assertEqual(len(self.agent.actions('test')),1)
    def test_tampered_proposal_not_trusted(self):
        r=self.ask('Process my refund');r['pending']={'kind':'refund'}
        self.agent.confirm(r,'test');self.assertEqual(self.agent.actions('test')[0]['kind'],'escalation')
    def test_exchange_memory_and_stock(self):
        for order in self.agent.orders.values():
            variants=[v for v in self.agent.catalog if v['SKU']==order['SKU'] and v['Colour']==order['Colour'] and v['Size']!=order['Size'] and v['Stock_Qty']>=order['Qty'] and v['Status']=='Active']
            if order['Order_Status']=='Delivered' and variants:break
        day=date.fromisoformat(order['Delivered_Date'][:10]);variant=variants[0]
        r=self.ask('Exchange '+order['Order_ID'],today=day,condition_ok=True)
        r=self.ask('Size '+variant['Size'],today=day,condition_ok=True,memory=r['memory'])
        self.assertEqual(r['pending']['kind'],'exchange')
        key=r['pending']['variant'];before=self.agent.db.execute('SELECT qty FROM stock WHERE variant=?',(key,)).fetchone()[0]
        self.agent.confirm(r,'test');self.agent.confirm(r,'test')
        after=self.agent.db.execute('SELECT qty FROM stock WHERE variant=?',(key,)).fetchone()[0]
        self.assertEqual(before-after,order['Qty'])
    def test_stock_rechecked_on_confirm(self):
        # A competing reservation consumes stock after the proposal is generated.
        self.test_exchange_memory_and_stock()
        for event in self.agent.db.execute('SELECT payload FROM events'):
            import json
            r=json.loads(event[0])
            if r.get('pending',{} ) and r['pending']['kind']=='exchange':break
        self.agent.db.execute('DELETE FROM actions');self.agent.db.execute('UPDATE stock SET qty=0');self.agent.db.commit()
        with self.assertRaises(ValueError):self.agent.confirm(r,'test')
    def test_relevant_policy(self):
        self.assertIn('POL-02',[p['Policy_ID'] for p in retrieve_policy('larger shirt','exchange_size')])
    def test_no_evaluation_answers_used(self):
        self.assertNotIn('expected_agent_response',vars(self.agent))
    def test_openai_adapter_with_mock_client(self):
        import json
        calls=[]
        def create(**kwargs):
            calls.append(kwargs)
            text=json.dumps({'intent':'return_request','order_id':self.order['Order_ID'],'size':None,'colour':None}) if 'text' in kwargs else 'Please confirm the item condition so I can check your return.'
            return SimpleNamespace(output_text=text,usage=SimpleNamespace(input_tokens=10,output_tokens=5))
        agent=Agent(Path(self.temp.name)/'api.sqlite',mode='OpenAI',model='test-model',client=SimpleNamespace(responses=SimpleNamespace(create=create)))
        r=agent.chat('Return this',today=self.day)
        self.assertEqual(r['usage']['input_tokens'],20);self.assertIn('retrieved_policies',calls[1]['input'])
        self.assertIsNone(r['pending']);self.assertFalse(calls[0]['store']);agent.db.close()
    def test_ollama_adapter_uses_same_guarded_workflow(self):
        import json
        calls=[]
        def create(**kwargs):
            calls.append(kwargs)
            text=json.dumps({'intent':'order_tracking','order_id':'ORD-10003','size':None,'colour':None}) if 'response_format' in kwargs else 'Your order status is available in the supplied record.'
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))],usage=SimpleNamespace(prompt_tokens=12,completion_tokens=4))
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        agent=Agent(Path(self.temp.name)/'ollama.sqlite',mode='Ollama',model='local-test-model',client=client)
        result=agent.chat('Where is ORD-10003?')
        self.assertEqual(result['intent'],'order_tracking')
        self.assertEqual(result['usage']['requests'],2)
        self.assertIn('authoritative_decision',calls[1]['messages'][1]['content'])
        self.assertEqual(calls[0]['temperature'],0)
        agent.db.close()
    def test_api_failure_creates_no_action(self):
        def fail(**kwargs):raise RuntimeError('API unavailable')
        agent=Agent(Path(self.temp.name)/'failure.sqlite',mode='OpenAI',model='test-model',client=SimpleNamespace(responses=SimpleNamespace(create=fail)))
        with self.assertRaises(RuntimeError):agent.chat('Return this')
        self.assertEqual(agent.actions('demo'),[])
        self.assertEqual(agent.error_rows()[0]['error_type'],'RuntimeError');agent.db.close()
    def test_customer_chat_history_is_separated(self):
        self.agent.chat('Where is ORD-10003?',session='chat-a',customer_id='CUST-A')
        self.agent.chat('Where is ORD-10003?',session='chat-b',customer_id='CUST-B')
        self.assertEqual(len(self.agent.messages('chat-a','CUST-A')),2)
        self.assertEqual(self.agent.messages('chat-a','CUST-B'),[])
        self.assertEqual(self.agent.customer_conversations('CUST-A')[0]['id'],'chat-a')
        self.agent.ensure_conversation('empty-chat','CUST-A');self.agent.db.commit()
        self.assertNotIn('empty-chat',[c['id'] for c in self.agent.customer_conversations('CUST-A')])
    def test_customer_cannot_read_another_profiles_order(self):
        result=self.agent.chat('Where is ORD-10003?',session='private',customer_id='CUST-A',allowed_order_ids=['ORD-10004'])
        self.assertIn('this customer profile',result['response'])
    def test_openai_usage_and_cost_are_persisted(self):
        import json
        def create(**kwargs):
            text=json.dumps({'intent':'order_tracking','order_id':'ORD-10003','size':None,'colour':None}) if 'text' in kwargs else 'Tracked.'
            return SimpleNamespace(output_text=text,usage=SimpleNamespace(input_tokens=100,output_tokens=25))
        agent=Agent(Path(self.temp.name)/'usage.sqlite',mode='OpenAI',model='priced-model',client=SimpleNamespace(responses=SimpleNamespace(create=create)))
        agent.chat('Where is ORD-10003?',session='priced-chat',customer_id='CUST-A',input_rate=2,output_rate=8,usd_inr=80)
        summary=agent.usage_summary('CUST-A')
        self.assertEqual((summary['requests'],summary['input_tokens'],summary['output_tokens']),(2,200,50))
        self.assertAlmostEqual(summary['cost_usd'],0.0008);self.assertAlmostEqual(summary['cost_inr'],0.064)
        agent.db.close()

if __name__=='__main__':unittest.main()
