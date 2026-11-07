"""A hosted clone without .env must not expose operational pages by default."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent


class HostedReleaseTests(unittest.TestCase):
    def test_hosted_defaults_use_openai_and_hide_model_switch(self):
        from streamlit.testing.v1 import AppTest
        original=agent.Agent
        with tempfile.TemporaryDirectory() as t:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(t)/'hosted.sqlite';return original(*args,**kwargs)
            with patch.dict(os.environ,{'APP_ENV':'hosted'},clear=True),patch('dotenv.load_dotenv'),patch('agent.Agent',side_effect=isolated):
                app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
                self.assertEqual(len(app.exception),0)
                self.assertEqual(app.session_state['agent'].model.mode,'OpenAI')
                self.assertEqual(app.session_state['agent'].model.model,'gpt-4.1-mini')
                self.assertNotIn('Assistant',[r.label for r in app.radio])
                app.session_state['agent'].db.close()

    def test_hosted_operational_pages_stay_closed_without_codes(self):
        from streamlit.testing.v1 import AppTest
        original=agent.Agent
        with tempfile.TemporaryDirectory() as t:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(t)/'closed.sqlite';return original(*args,**kwargs)
            with patch.dict(os.environ,{'APP_ENV':'hosted'},clear=True),patch('dotenv.load_dotenv'),patch('agent.Agent',side_effect=isolated):
                app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
                for name in ['Support','Admin']:
                    next(r for r in app.radio if r.label=='Interface').set_value(name).run()
                    self.assertEqual(len(app.exception),0)
                    self.assertTrue(any(name+' is unavailable' in w.value for w in app.warning))
                    self.assertNotIn('Status',[w.label for w in app.selectbox])
                app.session_state['agent'].db.close()
