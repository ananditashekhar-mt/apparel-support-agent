import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent import Model


class HostedProvidersTest(unittest.TestCase):
    def test_hosted_providers_extract_and_compose_using_chat_api(self):
        for provider in ('Gemini', 'Groq'):
            with self.subTest(provider=provider):
                calls = []
                def create(**kwargs):
                    calls.append(kwargs)
                    content = (json.dumps(dict(intent='order_tracking', order_id='ORD-10003',
                                               size=None, colour=None))
                               if 'response_format' in kwargs else 'Please provide your order ID.')
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                                           usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4))
                client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
                model = Model(provider, 'test-model', client)
                parsed, usage = model.understand('Track ORD-10003', [], {})
                reply, _ = model.compose('Track my order', dict(response='Please provide your order ID.',
                                                              status='needs_info', policies=[]))
                self.assertEqual(parsed['intent'], 'order_tracking')
                self.assertEqual(usage['input_tokens'], 12)
                self.assertTrue(reply)
                self.assertTrue(calls[0]['response_format']['json_schema']['strict'])
                self.assertIn('authoritative_decision', calls[1]['messages'][1]['content'])

    def test_missing_keys_fail_before_request(self):
        for provider in ('Gemini', 'Groq'):
            with self.subTest(provider=provider), patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, provider.upper() + '_API_KEY'):
                    Model(provider, 'test-model').ensure_client()
