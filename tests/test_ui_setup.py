import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import streamlit as st
import agent


class UISetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        original=agent.Agent
        def isolated(*args,**kwargs):
            kwargs['db_path']=Path(self.temp.name)/'setup.sqlite'
            return original(*args,**kwargs)
        self.factory=patch('agent.Agent',side_effect=isolated);self.factory.start()
        self.environment=patch.dict(os.environ,{'APP_ENV':'local','APP_MODE':'Demo','SUPPORT_ACCESS_CODE':'support-test','ADMIN_ACCESS_CODE':'admin-test','ALLOW_MODE_SWITCH':'false'})
        self.environment.start()
        self.app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
    def tearDown(self):
        self.app.session_state['agent'].db.close()
        self.environment.stop();self.factory.stop();self.temp.cleanup()
    def interface(self,name):
        next(r for r in self.app.radio if r.label=='Interface').set_value(name).run()
        self.assertEqual(len(self.app.exception),0)
    def test_provider_switch_and_sound_preference(self):
        selector=next(r for r in self.app.radio if r.label=='Assistant')
        self.assertTrue({'OpenAI','Groq','Gemini','Demo'}.issubset(set(selector.options)))
        self.assertTrue(next(t for t in self.app.toggle if t.label=='Reply sound').value)
        selector.set_value('Groq').run()
        self.assertEqual(self.app.session_state['agent'].model.mode,'Groq')
        self.interface('Support');self.interface('Customer')
        self.assertEqual(self.app.session_state['agent'].model.mode,'Groq')
    def test_role_unlock_survives_navigation_and_lock_works(self):
        self.interface('Support')
        next(w for w in self.app.text_input if w.label=='Support access code').set_value('wrong').run()
        self.assertEqual(len(self.app.tabs),0)
        next(w for w in self.app.text_input if w.label=='Support access code').set_value('support-test').run()
        self.assertIn('Customer chats',[t.label for t in self.app.tabs])
        self.interface('Admin')
        self.assertTrue(any(w.label=='Admin access code' for w in self.app.text_input))
        next(w for w in self.app.text_input if w.label=='Admin access code').set_value('admin-test').run()
        self.assertIn('API usage',[t.label for t in self.app.tabs])
        self.interface('Support')
        self.assertFalse(any(w.label=='Support access code' for w in self.app.text_input))
        next(b for b in self.app.button if b.label=='Lock Support').click().run()
        self.assertTrue(any(w.label=='Support access code' for w in self.app.text_input))
    def test_message_and_thinking_render_before_agent_and_sound_once(self):
        instance=self.app.session_state['agent'];original_chat=instance.chat
        original_markdown=st.markdown;rendered=[]
        def record(body,*args,**kwargs):
            rendered.append(str(body));return original_markdown(body,*args,**kwargs)
        def reply(*args,**kwargs):
            self.assertTrue(any('Need help with an order' in value for value in rendered))
            self.assertTrue(any('Thinking…' in value for value in rendered))
            return original_chat(*args,**kwargs)
        with patch('streamlit.markdown',side_effect=record),patch.object(instance,'chat',side_effect=reply):
            self.app.chat_input[0].set_value('Need help with an order').run()
        self.assertEqual(len(self.app.exception),0)
        cid=self.app.session_state['conversation_id']
        messages=instance.messages(cid)
        self.assertEqual(sum(m['role']=='user' for m in messages),1)
        self.assertFalse(any('<div class="threadly-thinking"' in value.value for value in self.app.markdown))
        self.assertFalse(self.app.chat_input[0].disabled)
        self.assertNotIn('reply_sound_event',self.app.session_state)

    def test_use_case_automatically_loads_random_matching_customer(self):
        use_case='Delayed delivery'
        rows=[row for row in agent.load('showcase_scenarios') if row['Use_Case']==use_case]
        next(w for w in self.app.selectbox if w.label=='Support use case').set_value(use_case).run()
        self.assertEqual(len(self.app.exception),0)
        chosen=self.app.session_state['loaded_showcase']
        self.assertIn(chosen,rows)
        self.assertEqual(self.app.session_state['customer_key'][0],chosen['Customer_ID'])
        self.assertEqual(self.app.session_state['selected_order'],chosen['Order_ID'])
        self.assertEqual(self.app.session_state['simulation_date'].isoformat(),chosen['As_Of'])
        conversation=self.app.session_state['conversation_id']
        self.app.run()
        self.assertEqual(self.app.session_state['conversation_id'],conversation)
        next(b for b in self.app.button if b.label=='Try another customer').click().run()
        self.assertEqual(len(self.app.exception),0)
        other=self.app.session_state['loaded_showcase']
        self.assertIn(other,rows)
        self.assertNotEqual(self.app.session_state['conversation_id'],conversation)
        if len({r['Customer_ID'] for r in rows})>1:
            self.assertNotEqual(chosen['Customer_ID'],other['Customer_ID'])
        variants=next(w for w in self.app.selectbox if w.label=='Scenario variant')
        alternative=next((v for v in variants.options if v!=other['Scenario_Variant']),None)
        if alternative:
            variants.set_value(alternative).run()
            self.assertEqual(len(self.app.exception),0)
            self.assertEqual(self.app.session_state['loaded_showcase']['Scenario_Variant'],alternative)
