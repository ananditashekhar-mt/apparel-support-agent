"""Item disclosures cannot be bypassed by classification or a later checkbox."""
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from agent import Agent


class ItemConditionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.agent=Agent(Path(self.temp.name)/'condition.sqlite')
        self.order=next(o for o in self.agent.orders.values() if o['Order_Status']=='Delivered')
        self.oid=self.order['Order_ID'];self.cid=self.order['Customer_ID']
        self.day=date.fromisoformat(self.order['Delivered_Date'][:10])+timedelta(days=5)
        self.other=dict(self.order,Order_ID='ORD-900001');self.agent.orders[self.other['Order_ID']]=self.other
    def tearDown(self):self.agent.db.close();self.temp.cleanup()
    def ask(self,text,intent='return_request',issues=None,memory=None,condition=True,order=None):
        parsed={'intent':intent,'order_id':order,'size':None,'colour':None,'condition_issues':issues or []}
        with patch.object(self.agent.model,'understand',return_value=(parsed,{})):
            return self.agent.chat(text,memory or {'order_id':self.oid},today=self.day,condition_ok=condition,
                session='case',customer_id=self.cid,allowed_order_ids=[self.oid,self.other['Order_ID']])
    def test_condition_fact_overrides_generic_or_expired_return_classification(self):
        for issue in ['worn','washed','tags_removed','altered','stained']:
            for intent in ['return_request','return_outside_window']:
                with self.subTest(issue=issue,intent=intent):
                    r=self.ask('Return please',intent,[issue])
                    self.assertEqual(r['intent'],'used_item_return')
                    self.assertEqual(r['pending']['kind'],'escalation')
    def test_later_confirmation_does_not_erase_known_use(self):
        first=self.ask('I wore it once',issues=['worn'],condition=False)
        later=self.ask('Yes, condition confirmed',memory=first['memory'],condition=True)
        self.assertEqual(later['pending']['kind'],'escalation')
        self.assertEqual(later['memory']['condition_issues'],['worn'])
    def test_known_tag_removal_blocks_exchange_even_if_checkbox_is_true(self):
        first=self.ask('Tags removed',issues=['tags_removed'])
        r=self.ask('Exchange size instead',intent='exchange_size',memory=first['memory'])
        self.assertEqual(r['intent'],'exchange_size')
        self.assertEqual(r['pending']['kind'],'escalation')
        self.assertIn('original tags',r['response'])
        self.assertNotIn('has been worn',r['response'])
    def test_selecting_other_order_does_not_transfer_condition(self):
        first=self.ask('I washed this item',issues=['washed'])
        r=self.ask('Return another order',memory=first['memory'],order=self.other['Order_ID'])
        self.assertFalse(r['memory']['condition_review_required'])
        self.assertEqual(r['memory']['condition_issues'],[])
        self.assertEqual(r['pending']['kind'],'return')
    def test_no_condition_disclosure_still_allows_eligible_return(self):
        r=self.ask('Never worn, original tags attached',issues=[])
        self.assertEqual(r['pending']['kind'],'return')
    def test_disclosure_does_not_block_tracking(self):
        first=self.ask('I wore this once',issues=['worn'])
        r=self.ask('Where is my order?',intent='order_tracking',memory=first['memory'])
        self.assertEqual(r['status'],'answered');self.assertIsNone(r['pending'])
