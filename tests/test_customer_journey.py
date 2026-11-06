"""Exercise the guided customer journey with an isolated database."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import agent


class CustomerJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        original=agent.Agent
        def isolated(*args,**kwargs):
            kwargs['db_path']=Path(self.temp.name)/'journey.sqlite'
            return original(*args,**kwargs)
        self.factory=patch('agent.Agent',side_effect=isolated);self.factory.start()
        self.app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
    def tearDown(self):
        self.app.session_state['agent'].db.close();self.factory.stop();self.temp.cleanup()
    def click(self,label):
        # AppTest may retain the form widget for one rerun after navigation.
        for field in self.app.text_area:
            if field.label=='Describe your issue' and self.app.session_state['chat_stage']=='chat':field.set_value('')
        next(b for b in self.app.button if b.label==label).click().run()
        self.assertEqual(len(self.app.exception),0)
    def test_order_topic_and_new_chat_clear_context(self):
        self.assertEqual(len(self.app.chat_input),0)
        self.click('Get help with this order')
        oid=self.app.session_state['selected_order']
        self.click('Delivery status')
        self.assertIn(oid,self.app.session_state['history'][-1]['content'])
        old=self.app.session_state['conversation_id']
        self.click('＋ New chat')
        self.assertNotEqual(old,self.app.session_state['conversation_id'])
        self.assertEqual(self.app.session_state['memory'],{})
        self.assertIsNone(self.app.session_state['selected_order'])
        self.assertEqual(self.app.session_state['chat_stage'],'order')
        self.assertEqual(len(self.app.chat_input),0)
    def test_other_unlisted_issue_offers_support_without_false_connection(self):
        self.click('Other');self.click('My issue is not listed here')
        self.app.text_area[0].set_value('I need a copy of my invoice for my records.')
        self.click('Let Tia take a look')
        self.assertEqual(self.app.session_state['last']['pending']['kind'],'escalation')
        self.assertEqual(self.app.session_state['agent'].actions(self.app.session_state['conversation_id']),[])
        self.click('Request a Support Expert')
        messages=self.app.session_state['history']
        self.assertIn('a live expert has not been contacted',messages[-1]['content'])
        self.assertEqual(len(self.app.session_state['agent'].actions(self.app.session_state['conversation_id'])),1)
    def test_unlisted_supported_issue_uses_policy_flow(self):
        self.click('Get help with this order')
        self.click('My issue is not listed here')
        self.app.text_area[0].set_value('Where is my order?')
        self.click('Let Tia take a look')
        result=self.app.session_state['last']
        self.assertEqual(result['intent'],'order_tracking')
        self.assertIsNone(result['pending'])
    def test_empty_description_is_not_submitted_and_back_navigation_works(self):
        self.click('Other');self.click('My issue is not listed here')
        self.click('Let Tia take a look')
        self.assertEqual(self.app.session_state['history'],[])
        self.assertEqual(len(self.app.warning),1)
        self.click('← Back to topics');self.click('← Choose a different order')
        self.assertEqual(self.app.session_state['chat_stage'],'order')
