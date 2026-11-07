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
        instance=self.at.session_state['agent']
        case=next(r for r in agent.load('showcase_scenarios') if r['Intent']=='return_outside_window')
        order=instance.orders[case['Order_ID']]
        self.name=order['Customer_Name_Synthetic']
        picker=next(w for w in self.at.selectbox if w.label=='Preview customer')
        picker.set_value(next(label for label in picker.options if label.startswith(self.name+' · ') and order['Customer_ID'][-4:] in label)).run()
        if not any(b.key=='choose_'+order['Order_ID'] for b in self.at.button):
            count=sum(o['Customer_ID']==order['Customer_ID'] for o in instance.orders.values())
            next(b for b in self.at.button if b.label==f'View all {count} orders').click().run()
        self.at.button(key='choose_'+order['Order_ID']).click().run()
        next(b for b in self.at.button if b.label=='Return an item').click().run()

    def tearDown(self):
        self.at.session_state['agent'].db.close()
        self.factory.stop()
        self.temp.cleanup()

    def rate(self,stars):
        next(r for r in self.at.radio if r.label=='Rate your experience').set_value(stars)
        next(b for b in self.at.button if b.label=='Submit feedback').click().run()
        self.assertEqual(len(self.at.exception),0)

    def test_two_low_ratings_end_loop_and_survive_reopening(self):
        first=self.at.session_state['history'][-2]['content']
        self.assertTrue(first.startswith(f'Hi {self.name},\nI’m Tia from Threadly support.\n\n'))
        self.assertNotIn('—',first)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.rate(3)
        self.assertFalse(self.at.chat_input[0].disabled)
        self.at.chat_input[0].set_value('Can you help me return it anyway?').run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.rate(1)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('Request a Support Expert',[b.label for b in self.at.button])
        self.assertNotIn('Rate your experience',[r.label for r in self.at.radio])
        self.at.session_state['last']=None
        self.at.run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('Request a Support Expert',[b.label for b in self.at.button])
        button=next(b for b in self.at.button if b.label=='Request a Support Expert')
        button.click().run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('a live expert has not been contacted',self.at.session_state['history'][-1]['content'])
        self.assertEqual(len(self.at.session_state['agent'].actions(self.at.session_state['conversation_id'])),1)

    def test_four_stars_closes_without_reopening(self):
        self.rate(4)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertNotIn('Rate your experience',[r.label for r in self.at.radio])
        self.assertNotIn('Request a Support Expert',[b.label for b in self.at.button])
        self.assertEqual(self.at.session_state['history'][-1]['content'],'Thank you for your feedback.')
