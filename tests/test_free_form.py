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
                    for message in row['messages']:
                        result=agent.chat(message,memory,session=row['id'])
                        memory=result['memory']
                    self.assertEqual(result['intent'],row['intent'])
                    if row['status']:self.assertEqual(result['status'],row['status'])
                    self.assertEqual(result['order_id'],row['order_id'])
                    for text in row['response_contains']:self.assertIn(text,result['response'])
                    for text in row['response_excludes']:self.assertNotIn(text,result['response'])
                    if row['intent'] in ('greeting','general_question','unknown'):
                        self.assertIsNone(result['pending'])
            agent.db.close()
