import json
import tempfile
import unittest
from pathlib import Path
from agent import Agent, ROOT


class FreeFormTests(unittest.TestCase):
    def test_exchange_variant_survives_general_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent=Agent(Path(tmp)/'runtime.sqlite')
            first=agent.chat('Exchange ORD-20001 for size XL')
            policy=agent.chat('What is your return policy?',first['memory'])
            resumed=agent.chat('Yes, condition confirmed',policy['memory'])
            self.assertEqual(resumed['memory']['size'],'XL')
            self.assertEqual(resumed['memory']['intent'],'exchange_size')
            agent.db.close()

    def test_evaluation_dataset_responses_and_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent=Agent(Path(tmp)/'runtime.sqlite')
            for row in json.loads((ROOT/'data/free_form_conversations.json').read_text()):
                with self.subTest(row['id']):
                    memory={}
                    for index,message in enumerate(row['messages']):
                        result=agent.chat(message,memory,history=agent.messages(row['id']),session=row['id'])
                        memory=result['memory']
                        if row.get('turn_intents'):
                            self.assertEqual(result['intent'],row['turn_intents'][index])
                        if result['intent']=='order_help':
                            self.assertEqual(result['status'],'needs_information')
                            self.assertIsNone(result['pending'])
                            self.assertNotIn('order ID',result['response'])
                            self.assertNotIn('get_order',result['tools'])
                    self.assertEqual(result['intent'],row['intent'])
                    if row['status']:self.assertEqual(result['status'],row['status'])
                    self.assertEqual(result['order_id'],row['order_id'])
                    for text in row['response_contains']:self.assertIn(text,result['response'])
                    for text in row['response_excludes']:self.assertNotIn(text,result['response'])
                    if row['intent'] in ('greeting','general_question','unknown'):
                        self.assertIsNone(result['pending'])
            agent.db.close()

    def test_hosted_semantic_order_help_and_ambiguous_reply(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        for intent,message in [('order_help','Something is up with my purchase'),
                               ('clarification','the other one')]:
            with self.subTest(intent=intent), tempfile.TemporaryDirectory() as tmp:
                create=Mock(return_value=SimpleNamespace(
                    output_text=json.dumps(dict(intent=intent,order_id=None,size=None,colour=None,condition_issues=[])),
                    usage=SimpleNamespace(input_tokens=10,output_tokens=5)))
                client=SimpleNamespace(responses=SimpleNamespace(create=create))
                agent=Agent(Path(tmp)/'hosted.sqlite',mode='OpenAI',model='test-model',client=client)
                history=[{'role':'assistant','content':'How can I help you today?'}]
                result=agent.chat(message,history=history)
                self.assertEqual(result['intent'],intent)
                self.assertEqual(result['status'],'needs_information')
                self.assertIsNone(result['pending'])
                self.assertEqual(create.call_count,1)
                call=create.call_args.kwargs
                self.assertEqual(json.loads(call['input'])['history'],history)
                self.assertIn('Read the recent conversation',call['instructions'])
                self.assertNotIn('get_order',result['tools'])
                agent.db.close()

    def test_screenshot_conversation_in_customer_ui(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        import agent as module
        original=module.Agent
        with tempfile.TemporaryDirectory() as tmp:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(tmp)/'ui.sqlite'
                return original(*args,**kwargs)
            with patch('agent.Agent',side_effect=isolated), patch.dict('os.environ',{'APP_ENV':'local','APP_MODE':'Demo'}):
                app=AppTest.from_file(str(ROOT/'app.py')).run()
                for message in ['Hi','with an order','need help with an order']:
                    app.chat_input[0].set_value(message).run()
                    self.assertEqual(len(app.exception),0)
                result=app.session_state['last']
                self.assertEqual(result['intent'],'order_help')
                self.assertIn('What’s happening with your order',result['response'])
                self.assertFalse(app.chat_input[0].disabled)
                self.assertFalse(app.session_state['memory'].get('order_id'))
                self.assertIsNone(result['pending'])
                app.session_state['agent'].db.close()
