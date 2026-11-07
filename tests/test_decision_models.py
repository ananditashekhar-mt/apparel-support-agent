"""Shadow failures and disagreements must not change authoritative outcomes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import Agent
from decision_models import JevShadow


def provider(payload):
    answers = {}
    for name, question in payload['questions'].items():
        if question['type'] == 'noul':
            answers[name] = {'type': 'noul', 'noul': .95}
        else:
            selected = 'unknown' if name == 'intent' else 'unresolved'
            answers[name] = {'type': 'choice', 'choice': selected, 'confidence': .9,
                             'probabilities': {key: float(key == selected) for key in question['criteria']}}
    return {'model': 'test-jev', 'answers': answers,
            'usage': {'input_tokens': 123, 'output_tokens': 12}}


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'JEV_SHADOW_ENABLED': 'true', 'TYPESAFE_API_KEY': 'test-key'})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.agent = Agent(db_path=Path(self.temp.name) / 'test.sqlite')
        self.agent.jev = JevShadow(provider)

    def tearDown(self):
        self.agent.db.close()
        self.temp.cleanup()
        self.env.stop()

    def test_intent_disagreement_leaves_result_and_extraction_unchanged(self):
        with patch.dict(os.environ, {'JEV_SHADOW_ENABLED': 'false'}):
            baseline = self.agent.chat('Where is ORD-20002?', session='baseline')
        result = self.agent.chat('Where is ORD-20002?', session='shadow')
        for field in ('intent', 'status', 'response', 'memory', 'pending'):
            self.assertEqual(result[field], baseline[field])
        row = self.agent.shadow_rows('shadow')[0]
        self.assertFalse(row['agrees_with_baseline'])
        self.assertEqual(row['usage']['input_tokens'], 123)
        self.assertNotIn('Where is', json.dumps(row))

    def test_provider_failure_does_not_fail_chat_or_csat(self):
        def fail(payload):
            raise TimeoutError('secret provider body')
        self.agent.jev = JevShadow(fail)
        result = self.agent.chat('Where is ORD-20002?', session='failure', customer_id='owner')
        self.assertEqual(result['intent'], 'order_tracking')
        self.agent.save_csat('failure', 'owner', 'feedback', 5, 'Still unresolved')
        self.assertEqual(self.agent.csat_responses('failure')[0]['rating'], 5)
        self.assertTrue(all(row['status'] == 'error' for row in self.agent.shadow_rows()))
        self.assertNotIn('secret', json.dumps(self.agent.shadow_rows()))

    def test_csat_idempotency_empty_comment_and_ownership(self):
        self.agent.ensure_conversation('csat', 'owner')
        self.agent.db.commit()
        self.agent.save_csat('csat', 'owner', 'first', 5, 'Still waiting. Please get a human.')
        self.agent.save_csat('csat', 'owner', 'first', 1, 'duplicate')
        self.agent.save_csat('csat', 'owner', 'second', 2, '')
        self.assertEqual(len(self.agent.shadow_rows()), 1)
        row = self.agent.shadow_rows()[0]
        self.assertEqual(row['answers']['reason']['choice'], 'unresolved')
        self.assertEqual(row['baseline']['rating'], 5)
        with self.assertRaises(ValueError):
            self.agent.save_csat('csat', 'intruder', 'third', 2, 'human')
        self.assertEqual(len(self.agent.shadow_rows()), 1)

    def test_disabled_and_missing_key_make_no_request(self):
        with patch.object(self.agent.jev, 'transport') as transport:
            with patch.dict(os.environ, {'JEV_SHADOW_ENABLED': 'false'}):
                self.assertIsNone(self.agent.jev.evaluate({}, {}))
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': ''}):
                self.assertEqual(self.agent.jev.evaluate({}, {})['status'], 'unconfigured')
            transport.assert_not_called()

    def test_malformed_provider_answer_is_recorded_as_error(self):
        self.agent.jev = JevShadow(lambda payload: {'answers': {'x': {'type': 'noul', 'noul': float('nan')}}})
        result = self.agent.jev.evaluate({}, {'x': {'type': 'noul', 'instructions': 'test'}})
        self.assertEqual(result['status'], 'error')
