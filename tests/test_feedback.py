"""Exercise the rating flow with an isolated database and deterministic Demo replies."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent
from streamlit.testing.v1 import AppTest


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        original=agent.Agent
        def isolated(*args,**kwargs):
            kwargs['db_path']=Path(self.temp.name)/'test.sqlite'
            return original(*args,**kwargs)
        self.factory=patch('agent.Agent',side_effect=isolated)
        self.factory.start()
        self.at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        self.at.chat_input[0].set_value('I want to return this item').run()

    def tearDown(self):
        self.at.session_state['agent'].db.close()
        self.factory.stop()
        self.temp.cleanup()

    def rate(self,stars):
        # Streamlit 1.50 AppTest does not serialize the stars widget correctly.
        # Supply the same zero-based value returned by st.feedback in the browser.
        for widget in self.at.get('button_group'):widget.set_value([])
        with patch('streamlit.feedback',return_value=stars-1):
            self.at.run()
        self.assertEqual(len(self.at.exception),0)

    def test_two_low_ratings_end_loop_and_survive_reopening(self):
        first=self.at.session_state['history'][-2]['content']
        self.assertTrue(first.startswith('Hi Aarav,\nI’m Tia from Threadly support.\n\n'))
        self.assertNotIn('—',first)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.rate(3)
        self.assertFalse(self.at.chat_input[0].disabled)
        self.at.chat_input[0].set_value('Can you help me return it anyway?').run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.rate(1)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('Request support engineer',[b.label for b in self.at.button])
        self.assertEqual(len(self.at.get('button_group')),0)
        self.at.session_state['last']=None
        self.at.run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('Request support engineer',[b.label for b in self.at.button])
        button=next(b for b in self.at.button if b.label=='Request support engineer')
        button.click().run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('No support engineer has been contacted',self.at.session_state['history'][-1]['content'])
        self.assertEqual(len(self.at.session_state['agent'].actions(self.at.session_state['conversation_id'])),1)

    def test_four_stars_closes_without_reopening(self):
        self.rate(4)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertEqual(len(self.at.get('button_group')),0)
        self.assertNotIn('Request support engineer',[b.label for b in self.at.button])
        self.assertEqual(self.at.session_state['history'][-1]['content'],'Thank you for your feedback.')
