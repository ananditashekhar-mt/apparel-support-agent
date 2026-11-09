from star_widget_testing import enable_star_testing, set_stars
"""Exercise the rating flow with an isolated database and deterministic Demo replies."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent
from streamlit.testing.v1 import AppTest


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        enable_star_testing(self)
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
        set_stars(self.at,stars)
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
        self.assertEqual(len(self.at.get('button_group')),0)
        self.at.session_state['last']=None
        self.at.run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertIn('Request a Support Expert',[b.label for b in self.at.button])
        button=next(b for b in self.at.button if b.label=='Request a Support Expert')
        button.click().run()
        self.assertFalse(self.at.chat_input[0].disabled)
        self.assertTrue(any('a live expert has not been contacted' in m['content'] for m in self.at.session_state['history']))
        next(b for b in self.at.button if b.label=='No, end chat').click().run()
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertEqual(len(self.at.session_state['agent'].actions(self.at.session_state['conversation_id'])),1)

    def test_four_stars_closes_without_reopening(self):
        self.rate(4)
        self.assertTrue(self.at.chat_input[0].disabled)
        self.assertEqual(len(self.at.get('button_group')),0)
        self.assertNotIn('Request a Support Expert',[b.label for b in self.at.button])
        self.assertEqual(self.at.session_state['history'][-1]['content'],'Thank you for your feedback.')


    def test_fifth_star_saves_five(self):
        self.rate(5)
        rows=self.at.session_state['agent'].csat_responses(self.at.session_state['conversation_id'])
        self.assertEqual(rows[-1]['rating'],5)

    def test_second_star_saves_two(self):
        self.rate(2)
        rows=self.at.session_state['agent'].csat_responses(self.at.session_state['conversation_id'])
        self.assertEqual(rows[-1]['rating'],2)

class FeedbackReportingTests(unittest.TestCase):
    def test_multiple_tickets_do_not_duplicate_ratings(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            instance=agent.Agent(Path(directory)/'feedback.sqlite')
            try:
                instance.ensure_conversation('chat','customer')
                instance.save_csat('chat','customer','rating',2,'Still waiting')
                instance.save_csat('chat','customer','rating',2,'Still waiting')
                for index,kind in enumerate(['return','escalation']):
                    instance.db.execute('INSERT INTO actions VALUES(?,?,?,?,?)',
                        (f'T-{index}','chat','ORD-1',kind,json.dumps({})))
                rows=instance.support_feedback()
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['rating'],2)
                self.assertEqual(rows[0]['comment'],'Still waiting')
                self.assertEqual(set(rows[0]['ticket_ids'].split(', ')),{'T-0','T-1'})
                self.assertEqual(rows[0]['order_id'],'ORD-1')
            finally:instance.db.close()

    def test_support_feedback_tab_renders_saved_comment(self):
        original=agent.Agent
        with tempfile.TemporaryDirectory() as directory:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(directory)/'ui.sqlite'
                return original(*args,**kwargs)
            with patch('agent.Agent',side_effect=isolated):
                app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
                instance=app.session_state['agent']
                cid=next(iter(app.session_state['agent'].orders.values()))['Customer_ID']
                instance.ensure_conversation('feedback-chat',cid)
                instance.save_csat('feedback-chat',cid,'feedback-ui',5,'Helpful service')
                next(r for r in app.radio if r.label=='Interface').set_value('Support').run()
                self.assertEqual(len(app.exception),0)
                self.assertIn('CSAT & feedback',[tab.label for tab in app.tabs])
                self.assertTrue(any(m.value=='100%' for m in app.metric))
                self.assertIn('Helpful service',[m.value for m in app.markdown])
                instance.db.close()
