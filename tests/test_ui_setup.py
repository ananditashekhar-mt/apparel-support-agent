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
