"""Guard round trips, initialization retries and customer isolation."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import agent
import database


class PerformanceTests(unittest.TestCase):
    def test_history_is_one_query_limited_fresh_and_customer_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            instance=agent.Agent(Path(temp)/'history.sqlite')
            self.addCleanup(instance.db.close)
            for i in range(15):
                session=f'owned-{i}'
                instance.ensure_conversation(session,'customer-a')
                instance.log_message(session,'customer-a','user','Help')
                instance.db.execute('INSERT INTO events VALUES(?,?,?)',
                    (str(uuid.uuid4()),session,json.dumps(dict(intent='return_request',order_id=f'ORD-{i}'))))
            instance.ensure_conversation('empty','customer-a')
            instance.ensure_conversation('private','customer-b')
            instance.log_message('private','customer-b','user','Other customer')
            instance.db.commit()
            queries=[];instance.db.set_trace_callback(queries.append)
            rows=instance.customer_conversations('customer-a',limit=12)
            self.assertEqual(len(rows),12)
            self.assertEqual(len(queries),1)
            self.assertNotIn('private',[r['id'] for r in rows])
            self.assertNotIn('empty',[r['id'] for r in rows])
            target=rows[0]['id']
            instance.db.execute('INSERT INTO events VALUES(?,?,?)',
                (str(uuid.uuid4()),target,json.dumps(dict(intent='damaged_item',order_id='ORD-UPDATED'))))
            instance.db.commit()
            latest=instance.customer_conversations('customer-a',limit=12)
            self.assertEqual(next(r['label'] for r in latest if r['id']==target),'Damaged item · ORD-UPDATED')
            self.assertEqual([r['id'] for r in instance.customer_conversations('customer-b')],['private'])
            self.assertEqual(instance.customer_conversations('no-customer'),[])

    def test_postgres_bootstrap_once_across_separate_session_connections(self):
        url='test-'+uuid.uuid4().hex
        def connection():
            db=object.__new__(database.PostgresDatabase);db._url=url
            db.executemany=Mock();db.commit=Mock();db.rollback=Mock()
            return db
        first,second=connection(),connection()
        with patch('database.initialize_database') as initialize:
            database.prepare_runtime_database(first,[('variant',5)])
            database.prepare_runtime_database(second,[('variant',5)])
            initialize.assert_called_once_with(first)
            second.executemany.assert_not_called()
            first.commit.assert_called_once()
            # A catalogue update triggers setup, using conflict-ignore stock inserts.
            database.prepare_runtime_database(second,[('variant',6)])
            self.assertEqual(initialize.call_count,2)
            self.assertIn('OR IGNORE',second.executemany.call_args.args[0])

    def test_failed_bootstrap_is_not_marked_ready(self):
        db=object.__new__(database.PostgresDatabase);db._url='test-'+uuid.uuid4().hex
        db.executemany=Mock();db.commit=Mock();db.rollback=Mock()
        with patch('database.initialize_database',side_effect=[RuntimeError('temporary outage'),None]) as initialize:
            with self.assertRaises(RuntimeError):database.prepare_runtime_database(db,[('variant',1)])
            database.prepare_runtime_database(db,[('variant',1)])
            self.assertEqual(initialize.call_count,2)
            db.rollback.assert_called_once()
            db.commit.assert_called_once()

    def test_static_cache_keeps_callers_independent_and_invalidates_on_file_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'data').mkdir();path=root/'data/sample.json'
            path.write_text('[{"name":"first"}]')
            with patch.object(agent,'ROOT',root):
                value=agent.load('sample');value[0]['name']='mutated'
                self.assertEqual(agent.load('sample')[0]['name'],'first')
                path.write_text('[{"name":"updated value"}]')
                self.assertEqual(agent.load('sample')[0]['name'],'updated value')
