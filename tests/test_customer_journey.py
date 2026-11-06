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
        # AppTest can retain removed form controls for one extra rerun.
        for widget in self.app.radio:
            try:widget.value
            except KeyError:widget.set_value(None)
        for field in self.app.text_area:
            try:field.value
            except KeyError:field.set_value('')
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

    def test_damage_flow_offers_photo_upload(self):
        self.click('Get help with this order');self.click('Damaged or faulty item')
        self.assertEqual(len(self.app.get('file_uploader')),1)
        self.assertIn('Save photos',[b.label for b in self.app.button])
        self.assertTrue(next(b for b in self.app.button if b.label=='Save photos').disabled)

    def test_closed_chat_reopens_only_after_reason_and_description(self):
        self.click('Get help with this order');self.click('Delivery status')
        conversation=self.app.session_state['conversation_id']
        self.click('Finish chat');self.click('Reopen chat')
        self.click('Reopen and continue')
        self.assertEqual(self.app.session_state['chat_stage'],'reopen')
        next(r for r in self.app.radio if r.label=='Why are you reopening this chat?').set_value('Something is still pending')
        next(t for t in self.app.text_area if t.label=='Tell us what still needs attention').set_value('I am waiting for my delivery update.')
        self.click('Reopen and continue')
        self.assertEqual(self.app.session_state['conversation_id'],conversation)
        self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertFalse(self.app.chat_input[0].disabled)
        self.assertTrue(any('I am waiting' in m['content'] for m in self.app.session_state['history']))

    def test_previous_chat_read_then_reopen_or_start_new(self):
        self.click('Get help with this order');self.click('Delivery status')
        conversation=self.app.session_state['conversation_id']
        self.click('Past chats')
        self.app.button(key='recent_'+conversation).click().run()
        self.assertEqual(self.app.session_state['chat_stage'],'review')
        self.assertIn('Reopen chat',[b.label for b in self.app.button])
        self.click('Start a new chat')
        self.assertNotEqual(conversation,self.app.session_state['conversation_id'])
        self.assertEqual(self.app.session_state['memory'],{})

    def test_end_chat_csat_requires_rating_and_saves_optional_comment(self):
        self.click('Get help with this order');self.click('Delivery status');self.click('Finish chat')
        session=self.app.session_state['conversation_id'];instance=self.app.session_state['agent']
        self.click('Submit feedback')
        self.assertEqual(instance.csat_responses(session),[])
        self.assertTrue(self.app.chat_input[0].disabled)
        next(r for r in self.app.radio if r.label=='Rate your experience').set_value(5)
        next(t for t in self.app.text_area if 'optional' in t.label).set_value('Clear and helpful, thank you.')
        self.click('Submit feedback')
        self.assertEqual(instance.csat_responses(session)[0]['comment'],'Clear and helpful, thank you.')
        self.app.run()
        self.assertNotIn('Submit feedback',[b.label for b in self.app.button])
        self.assertEqual(len(instance.csat_responses(session)),1)
        self.assertIn('Reopen chat',[b.label for b in self.app.button])

    def test_csat_can_be_skipped_and_reopening_gets_fresh_survey(self):
        self.click('Get help with this order');self.click('Delivery status');self.click('Finish chat')
        self.click('Skip feedback')
        # AppTest retains removed form controls for one rerun after Skip.
        for widget in self.app.radio:
            if widget.label=='Rate your experience':widget.set_value(None)
        for field in self.app.text_area:
            if 'optional' in field.label:field.set_value('')
        self.click('Reopen chat')
        next(r for r in self.app.radio if r.label=='Why are you reopening this chat?').set_value('Something is still pending')
        next(t for t in self.app.text_area if t.label=='Tell us what still needs attention').set_value('I still need an update.')
        self.click('Reopen and continue');self.click('Finish chat')
        next(r for r in self.app.radio if r.label=='Rate your experience').set_value(3)
        self.click('Submit feedback')
        responses=self.app.session_state['agent'].csat_responses(self.app.session_state['conversation_id'])
        self.assertEqual([(r['rating'],r['comment']) for r in responses],[(3,'')])

    def test_direct_delivery_question_shows_orders_and_resumes_without_typing_id(self):
        self.click('Other');self.click('Delivery status')
        self.assertEqual(self.app.session_state['chat_stage'],'pick_order')
        self.assertNotIn('Please share your order ID',self.app.session_state['history'][-1]['content'])
        self.assertEqual(self.app.session_state['agent'].actions(self.app.session_state['conversation_id']),[])
        self.click('Get help with this order')
        self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertEqual(self.app.session_state['last']['intent'],'order_tracking')
        self.assertIn(self.app.session_state['selected_order'],self.app.session_state['history'][-1]['content'])

    def test_recent_orders_are_latest_three_and_view_all_is_available(self):
        from collections import Counter
        orders=list(self.app.session_state['agent'].orders.values())
        cid=Counter(o['Customer_ID'] for o in orders).most_common(1)[0][0]
        order=next(o for o in orders if o['Customer_ID']==cid)
        label=f"{order['Customer_Name_Synthetic']} · {order['City']} · Customer {cid[-4:]}"
        next(s for s in self.app.selectbox if s.label=='Preview customer').set_value(label).run()
        expected=sorted([o for o in orders if o['Customer_ID']==cid],key=lambda o:(o['Order_Date'],o['Order_ID']),reverse=True)
        visible=[b.key for b in self.app.button if b.key and b.key.startswith('choose_')]
        self.assertEqual(visible,['choose_'+o['Order_ID'] for o in expected[:3]])
        self.click('View all '+str(len(expected))+' orders')
        self.assertEqual(len([b for b in self.app.button if b.key and b.key.startswith('choose_')]),len(expected))

    def test_back_through_topics_description_chat_and_history_preserves_conversation(self):
        self.click('Get help with this order');self.click('My issue is not listed here');self.click('Back')
        self.assertEqual(self.app.session_state['chat_stage'],'issue')
        self.click('Delivery status');session=self.app.session_state['conversation_id']
        messages=list(self.app.session_state['history'])
        self.click('Past chats');self.app.button(key='recent_'+session).click().run()
        self.click('Back');self.assertEqual(self.app.session_state['chat_stage'],'recent')
        self.click('Back');self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertEqual(self.app.session_state['conversation_id'],session)
        self.assertEqual(self.app.session_state['history'],messages)
        self.click('Back');self.assertEqual(self.app.session_state['chat_stage'],'issue')
        self.click('Back');self.assertEqual(self.app.session_state['chat_stage'],'order')

    def test_order_picker_back_and_reopen_back(self):
        self.click('Other');self.click('Delivery status');self.click('Back')
        self.assertEqual(self.app.session_state['chat_stage'],'issue')
        self.click('Delivery status');self.click('Get help with this order');self.click('Finish chat')
        self.click('Reopen chat');self.click('Back')
        self.assertEqual(self.app.session_state['chat_stage'],'review')

    def test_unavailable_typed_order_is_replaced_by_selected_customer_order(self):
        self.click('Other');self.click('My issue is not listed here')
        self.app.text_area[0].set_value('Where is ORD-99999?')
        self.click('Let Tia take a look')
        self.assertEqual(self.app.session_state['chat_stage'],'pick_order')
        self.click('Get help with this order')
        self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertEqual(self.app.session_state['last']['order_id'],self.app.session_state['selected_order'])
        self.assertNotIn('99999',self.app.session_state['history'][-1]['content'])
