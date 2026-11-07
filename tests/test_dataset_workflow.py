import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import date
from agent import Agent, ROOT
from evaluation_checks import audit_references


class DatasetTests(unittest.TestCase):
    def test_generator_repeatable_and_consistent(self):
        spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_dataset.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as t:
            builder.DATA=Path(t)/'data';shutil.copytree(ROOT/'data',builder.DATA)
            builder.main()
            first={p.name:p.read_bytes() for p in builder.DATA.glob('*.json')}
            builder.main()
            self.assertEqual(first,{p.name:p.read_bytes() for p in builder.DATA.glob('*.json')})
            orders=json.loads(first['orders.json'])
            self.assertEqual(len(orders),600)
            for o in orders:
                dates=[e['Date'] for e in o['Shipment_Events']]
                self.assertEqual(dates,sorted(dates),o['Order_ID'])
                self.assertTrue(0<=o['Delivered_Qty']<=o['Qty'])
                if o['Order_Status']!='Delivered':self.assertEqual(o['Delivered_Qty'],0)
                self.assertIn(o['Customer_ID'],{c['Customer_ID'] for c in json.loads(first['customers.json'])})

    def test_reference_audit_flags_conflicts(self):
        row={'Conversation_ID':'x','Order_ID':'o','Intent':'exchange_size','Split':'test','Customer_Message':'size M'}
        self.assertEqual(len(audit_references([row],{'o':{'Order_Status':'Confirmed'}})['reference_cases_needing_review']),1)


class RequestWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'runtime.sqlite'
        self.agent=Agent(self.path,mode='Demo')
        self.order=next(o for o in self.agent.orders.values() if o['Order_Status']=='Confirmed')
        self.oid=self.order['Order_ID'];self.cid=self.order['Customer_ID']
    def tearDown(self):
        self.agent.db.close();self.temp.cleanup()
    def ask(self,text,session='customer',customer=None,**kwargs):
        return self.agent.chat(text,session=session,customer_id=customer or self.cid,today=kwargs.pop('today',date(2026,12,31)),**kwargs)
    def test_cancellation_support_update_survives_reopen_and_new_chat(self):
        proposal=self.ask('Cancel '+self.oid)
        aid=self.agent.confirm(proposal,'customer')
        self.assertEqual(self.agent.confirm(proposal,'customer'),aid)
        reply=self.ask('Where is '+self.oid,session='new-chat')['response']
        self.assertIn('pending',reply);self.assertIn(aid,reply)
        self.agent.update_request(aid,'in_progress','Deepti','Checking with warehouse')
        self.assertIn('Checking with warehouse',self.ask('Where is '+self.oid)['response'])
        self.agent.update_request(aid,'completed','Deepti','Cancellation completed in simulation')
        self.agent.db.close();self.agent=Agent(self.path,mode='Demo')
        self.assertIn('is cancelled',self.ask('Where is '+self.oid,session='reopened')['response'])
        self.assertTrue(any('Support update' in m['content'] for m in self.agent.messages('customer',self.cid)))
        self.assertEqual(self.agent.order_requests(self.oid,'another-customer'),[])
        self.assertEqual(self.agent.order_requests(self.oid,'anonymous','other-session'),[])
    def test_partial_delivery_and_damaged_case(self):
        partial=next(o for o in self.agent.orders.values() if o['Issue_Type']=='Partial Delivery')
        result=self.ask('An item is missing from '+partial['Order_ID'])
        self.assertIn('1 of 2',result['response']);self.assertEqual(result['pending']['kind'],'escalation')
        damaged=next(o for o in self.agent.orders.values() if o['Issue_Type']=='Damaged')
        result=self.agent.chat('My item arrived damaged '+damaged['Order_ID'],today=date.fromisoformat(damaged['Issue_Reported_Date'][:10]))
        self.assertIn('already noted',result['response']);self.assertEqual(result['pending']['kind'],'escalation')
    def test_undelivered_quantity_does_not_claim_items_are_missing(self):
        result=self.ask('An item is missing from '+self.oid)
        self.assertNotIn('remaining item is reported missing',result['response'])

    def test_invalid_update_rejected(self):
        with self.assertRaises(ValueError):self.agent.update_request('missing','completed')
        with self.assertRaises(ValueError):self.agent.update_request('missing','anything')

class SupportInterfaceTests(unittest.TestCase):
    def test_support_form_saves_customer_visible_update(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        import agent
        original=agent.Agent
        with tempfile.TemporaryDirectory() as t:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(t)/'ui.sqlite'
                return original(*args,**kwargs)
            with patch('agent.Agent',side_effect=isolated):
                app=AppTest.from_file(str(ROOT/'app.py')).run()
                instance=app.session_state['agent']
                order=next(o for o in instance.orders.values() if o['Order_Status']=='Confirmed')
                result=instance.chat('Cancel '+order['Order_ID'],session='ui-case',customer_id=order['Customer_ID'])
                aid=instance.confirm(result,'ui-case')
                next(r for r in app.radio if r.label=='Interface').set_value('Support').run()
                if any(w.label=='Support access code' for w in app.text_input):
                    import os
                    next(w for w in app.text_input if w.label=='Support access code').set_value(os.environ['SUPPORT_ACCESS_CODE']).run()
                self.assertEqual(len(app.exception),0)
                next(w for w in app.selectbox if w.label=='Status').set_value('in_progress')
                next(w for w in app.text_input if w.label=='Assigned to').set_value('Deepti')
                next(w for w in app.text_area if w.label=='Reply visible to the customer').set_value('Checking your cancellation')
                next(b for b in app.button if b.label=='Save update').click().run()
                self.assertEqual(len(app.exception),0)
                request=next(r for r in instance.support_actions() if r['id']==aid)
                self.assertEqual(request['status'],'in_progress')
                self.assertEqual(request['assignee'],'Deepti')
                self.assertIn('Checking your cancellation',instance.messages('ui-case',order['Customer_ID'])[-1]['content'])
                instance.db.close()
