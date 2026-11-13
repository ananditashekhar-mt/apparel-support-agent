from star_widget_testing import enable_star_testing, set_stars
"""Exercise the guided customer journey with an isolated database."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import agent


class CustomerJourneyTests(unittest.TestCase):
    def setUp(self):
        enable_star_testing(self)
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
        if label=='Finish chat':
            if not any(b.label=='No, end chat' for b in self.app.button):self.click('End chat')
            label='No, end chat'
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
        self.assertEqual(len(self.app.chat_input),1)
        self.assertFalse(self.app.chat_input[0].disabled)
        self.click('Select order')
        oid=self.app.session_state['selected_order']
        self.click('Delivery status')
        self.assertIn(oid,self.app.session_state['last']['response'])
        old=self.app.session_state['conversation_id']
        self.click('＋ New chat')
        self.assertNotEqual(old,self.app.session_state['conversation_id'])
        self.assertEqual(self.app.session_state['memory'],{})
        self.assertIsNone(self.app.session_state['selected_order'])
        self.assertEqual(self.app.session_state['chat_stage'],'order')
        self.assertEqual(len(self.app.chat_input),1)
        self.assertFalse(self.app.chat_input[0].disabled)
    def test_other_unlisted_issue_offers_support_without_false_connection(self):
        self.app.chat_input[0].set_value('I need a copy of my invoice for my records.').run()
        self.assertEqual(self.app.session_state['last']['pending']['kind'],'escalation')
        self.assertEqual(self.app.session_state['agent'].actions(self.app.session_state['conversation_id']),[])
        self.click('Request a Support Expert')
        messages=self.app.session_state['history']
        self.assertTrue(any('a live expert has not been contacted' in m['content'] for m in messages))
        self.assertEqual(len(self.app.session_state['agent'].actions(self.app.session_state['conversation_id'])),1)
    def test_unlisted_supported_issue_uses_policy_flow(self):
        self.click('Select order')
        self.click('My issue is not listed here')
        self.app.text_area[0].set_value('Where is my order?')
        self.click('Let Tia take a look')
        result=self.app.session_state['last']
        self.assertEqual(result['intent'],'order_tracking')
        self.assertIsNone(result['pending'])
    def test_empty_description_is_not_submitted_and_back_navigation_works(self):
        self.click('Select order');self.click('My issue is not listed here')
        self.click('Let Tia take a look')
        self.assertEqual(self.app.session_state['history'],[])
        self.assertEqual(len(self.app.warning),1)
        self.click('← Back to topics');self.click('← Choose a different order')
        self.assertEqual(self.app.session_state['chat_stage'],'order')

    def test_damage_flow_offers_photo_upload(self):
        self.click('Select order');self.click('Damaged or faulty item')
        self.assertEqual(len(self.app.get('file_uploader')),1)
        self.assertIn('Save photos',[b.label for b in self.app.button])
        self.assertTrue(next(b for b in self.app.button if b.label=='Save photos').disabled)

    def test_undelivered_damage_complaint_never_offers_upload(self):
        instance=self.app.session_state['agent']
        for status in ('In Transit','Shipped','Cancelled','Delayed'):
            order=next(o for o in instance.orders.values() if o['Order_Status']==status)
            with self.subTest(status=status):
                picker=next(w for w in self.app.selectbox if w.label=='Preview customer')
                label=next(label for label in picker.options if label.endswith('Customer '+order['Customer_ID'][-4:]))
                picker.set_value(label).run()
                self.click('＋ New chat')
                self.app.chat_input[0].set_value('My item is damaged '+order['Order_ID']).run()
                self.assertEqual(self.app.session_state['last']['status'],'blocked')
                self.assertEqual(len(self.app.get('file_uploader')),0)
                self.assertNotIn('Save photos',[b.label for b in self.app.button])

    def test_damage_photos_hidden_before_recorded_delivery(self):
        from datetime import date,timedelta
        order=next(o for o in self.app.session_state['agent'].orders.values()
                   if o['Order_Status']=='Delivered' and o['Shipped_Date'] and o['Delivered_Date'][:10]>o['Shipped_Date'][:10])
        day=date.fromisoformat(order['Delivered_Date'][:10])-timedelta(days=1)
        next(w for w in self.app.date_input if w.label=='Simulation date').set_value(day).run()
        picker=next(w for w in self.app.selectbox if w.label=='Preview customer')
        picker.set_value(next(label for label in picker.options if label.endswith('Customer '+order['Customer_ID'][-4:]))).run()
        self.app.chat_input[0].set_value('My item is damaged '+order['Order_ID']).run()
        self.assertEqual(self.app.session_state['last']['status'],'blocked')
        self.assertEqual(len(self.app.get('file_uploader')),0)

    def test_closed_chat_reopens_only_after_reason_and_description(self):
        self.click('Select order');self.click('Delivery status')
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
        self.click('Select order');self.click('Delivery status')
        conversation=self.app.session_state['conversation_id']
        self.click('Past chats')
        self.app.button(key='recent_'+conversation).click().run()
        self.assertEqual(self.app.session_state['chat_stage'],'review')
        self.assertIn('Reopen chat',[b.label for b in self.app.button])
        self.click('Start a new chat')
        self.assertNotEqual(conversation,self.app.session_state['conversation_id'])
        self.assertEqual(self.app.session_state['memory'],{})

    def test_end_chat_csat_requires_rating_and_saves_optional_comment(self):
        self.click('Select order');self.click('Delivery status');self.click('Finish chat')
        session=self.app.session_state['conversation_id'];instance=self.app.session_state['agent']
        self.click('Submit feedback')
        self.assertEqual(instance.csat_responses(session),[])
        self.assertTrue(self.app.chat_input[0].disabled)
        set_stars(self.app,5)
        next(t for t in self.app.text_area if 'optional' in t.label).set_value('Clear and helpful, thank you.')
        self.click('Submit feedback')
        self.assertEqual(instance.csat_responses(session)[0]['comment'],'Clear and helpful, thank you.')
        self.app.run()
        self.assertNotIn('Submit feedback',[b.label for b in self.app.button])
        self.assertEqual(len(instance.csat_responses(session)),1)
        self.assertIn('Reopen chat',[b.label for b in self.app.button])

    def test_csat_can_be_skipped_and_reopening_gets_fresh_survey(self):
        self.click('Select order');self.click('Delivery status');self.click('Finish chat')
        self.click('Skip feedback')
        # AppTest retains removed form controls for one rerun after Skip.
        for widget in self.app.get('button_group'):widget.set_value([])
        for field in self.app.text_area:
            if 'optional' in field.label:field.set_value('')
        self.click('Reopen chat')
        next(r for r in self.app.radio if r.label=='Why are you reopening this chat?').set_value('Something is still pending')
        next(t for t in self.app.text_area if t.label=='Tell us what still needs attention').set_value('I still need an update.')
        self.click('Reopen and continue');self.click('Finish chat')
        set_stars(self.app,3)
        self.click('Submit feedback')
        responses=self.app.session_state['agent'].csat_responses(self.app.session_state['conversation_id'])
        self.assertEqual([(r['rating'],r['comment']) for r in responses],[(3,'')])

    def test_direct_delivery_question_shows_orders_and_resumes_without_typing_id(self):
        self.app.chat_input[0].set_value('Where is my order?').run()
        self.assertEqual(self.app.session_state['chat_stage'],'pick_order')
        self.assertNotIn('Please share your order ID',self.app.session_state['history'][-1]['content'])
        self.assertEqual(self.app.session_state['agent'].actions(self.app.session_state['conversation_id']),[])
        self.click('Select order')
        self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertEqual(self.app.session_state['last']['intent'],'order_tracking')
        self.assertIn(self.app.session_state['selected_order'],self.app.session_state['last']['response'])

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
        self.click('Select order');self.click('My issue is not listed here');self.click('Back')
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
        self.app.chat_input[0].set_value('Where is my order?').run()
        self.click('Back')
        self.assertEqual(self.app.session_state['chat_stage'],'issue')
        self.click('Delivery status');self.click('Select order');self.click('Finish chat')
        self.click('Reopen chat');self.click('Back')
        self.assertEqual(self.app.session_state['chat_stage'],'review')

    def test_unavailable_typed_order_is_replaced_by_selected_customer_order(self):
        self.click('Select order');self.click('My issue is not listed here')
        self.app.text_area[0].set_value('Where is ORD-99999?')
        self.click('Let Tia take a look')
        self.assertEqual(self.app.session_state['chat_stage'],'pick_order')
        self.click('Select order')
        self.assertEqual(self.app.session_state['chat_stage'],'chat')
        self.assertEqual(self.app.session_state['last']['order_id'],self.app.session_state['selected_order'])
        self.assertNotIn('99999',self.app.session_state['last']['response'])

    def test_initial_composer_accepts_question_before_order_selection(self):
        self.app.chat_input[0].set_value('I would like to return my item.').run()
        self.assertEqual(len(self.app.exception),0)
        self.assertEqual(self.app.session_state['chat_stage'],'pick_order')
        self.assertIn('I would like to return my item.',[m['content'] for m in self.app.session_state['history']])
        self.click('Select order')
        self.assertEqual(self.app.session_state['last']['intent'],'return_request')
        self.assertEqual(self.app.session_state['chat_stage'],'chat')

    def test_end_chat_checkin_yes_keeps_chat_open_and_no_closes(self):
        self.click('Select order');self.click('Delivery status')
        self.assertEqual(self.app.session_state['history'][-1]['content'],'Is there anything else I can help you with?')
        self.click('Yes, I need more help')
        self.assertFalse(self.app.chat_input[0].disabled)
        self.assertIn('What else',self.app.session_state['history'][-1]['content'])
        self.click('End chat')
        self.assertFalse(self.app.chat_input[0].disabled)
        self.click('No, end chat')
        self.assertTrue(self.app.chat_input[0].disabled)
        self.assertEqual(len(self.app.get('button_group')),1)

    def test_typed_no_ends_only_when_checkin_is_pending(self):
        self.click('Select order');self.click('Delivery status')
        self.app.chat_input[0].set_value('No thanks').run()
        self.assertEqual(len(self.app.exception),0)
        self.assertTrue(self.app.chat_input[0].disabled)
        self.assertEqual(len(self.app.get('button_group')),1)

    def test_typed_negative_delivery_report_does_not_close_chat(self):
        self.click('Select order');self.click('Delivery status')
        self.app.chat_input[0].set_value('No, my order never arrived.').run()
        self.assertEqual(len(self.app.exception),0)
        self.assertFalse(self.app.chat_input[0].disabled)
        self.assertEqual(self.app.session_state['last']['pending']['kind'],'escalation')

    def test_demo_view_switch_embeds_mobile_and_preserves_desktop_chat(self):
        from urllib.parse import parse_qs,urlsplit
        self.click('Select order')
        conversation=self.app.session_state['conversation_id']
        selected=self.app.session_state['selected_order']
        next(r for r in self.app.radio if r.label=='Layout preview').set_value('Mobile').run()
        self.assertEqual(len(self.app.exception),0)
        frame=next(frame for frame in self.app.get('iframe') if frame.proto.src)
        params=parse_qs(urlsplit(frame.proto.src).query)
        self.assertEqual(params['phone_preview'],['1'])
        self.assertEqual(params['customer'],[self.app.session_state['customer_key'][0]])
        self.assertEqual(len(self.app.chat_input),0)
        next(r for r in self.app.radio if r.label=='Layout preview').set_value('Desktop').run()
        self.assertEqual(self.app.session_state['conversation_id'],conversation)
        self.assertEqual(self.app.session_state['selected_order'],selected)
        self.assertEqual(len(self.app.chat_input),1)

    def test_embedded_mobile_view_cannot_embed_itself_again(self):
        self.app.query_params['phone_preview']='1'
        self.app.query_params['as_of']='2026-12-15'
        self.app.query_params['customer']='CUST-2026-0003'
        self.app.run()
        self.assertEqual(len(self.app.exception),0)
        self.assertNotIn('Layout preview',[r.label for r in self.app.radio])
        self.assertEqual(sum(bool(frame.proto.src) for frame in self.app.get('iframe')),0)
        self.assertEqual(self.app.session_state['customer_key'][0],'CUST-2026-0003')
