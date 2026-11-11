"""Damage complaints use the damage policy and never auto-approve returns."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from agent import Agent


class DamageRoutingTests(unittest.TestCase):
    def test_damage_policy_inside_and_outside_reporting_window(self):
        with tempfile.TemporaryDirectory() as temp:
            agent = Agent(Path(temp) / 'damage.sqlite')
            self.addCleanup(agent.db.close)
            order = next(o for o in agent.orders.values() if o['Order_Status'] == 'Delivered')
            delivered = date.fromisoformat(order['Delivered_Date'][:10])
            for age in (2, 7, 8):
                with self.subTest(days_since_delivery=age):
                    parsed = dict(intent='damaged_item', order_id=order['Order_ID'],
                                  size=None, colour=None, condition_issues=[])
                    with patch.object(agent.model, 'understand', return_value=(parsed, {})):
                        result = agent.chat('The garment arrived with a tear.', {},
                                            today=delivered + timedelta(days=age), condition_ok=True,
                                            session=f'damage-{age}', customer_id=order['Customer_ID'],
                                            allowed_order_ids=[order['Order_ID']])
                    self.assertEqual(result['intent'], 'damaged_item')
                    self.assertEqual(result['status'], 'escalation_proposed')
                    self.assertEqual(result['pending']['kind'], 'escalation')
                    self.assertIn('POL-03', [p['Policy_ID'] for p in result['policies']])
                    if age <= 7:
                        self.assertIn('photo', result['response'])
                    else:
                        self.assertIn('7 days', result['response'])
                    self.assertEqual(agent.actions(f'damage-{age}'), [])
