"""Opt-in real Postgres test, using a unique schema on a temporary Neon branch.

Supply THREADLY_TEST_DATABASE_URL with the test branch's direct connection.
No test data is added to the branch's public schema.
"""
from datetime import date
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

from agent import Agent
from database import PostgresDatabase
from migrate_database import migrate, snapshot


@unittest.skipUnless(os.getenv('THREADLY_TEST_DATABASE_URL'), 'Neon integration URL not supplied')
class PostgresIntegrationTests(unittest.TestCase):
    def test_hosted_archive_import_and_conflict_preservation(self):
        from psycopg.conninfo import make_conninfo
        from hosted_cutover import preserve_and_import
        schema = 'threadly_test_' + uuid.uuid4().hex
        root = PostgresDatabase(os.environ['THREADLY_TEST_DATABASE_URL'])
        root.connection.execute(f'CREATE SCHEMA {schema}')
        url = make_conninfo(os.environ['THREADLY_TEST_DATABASE_URL'], options=f'-c search_path={schema}')
        destination = Agent(db_url=url)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'hosted.sqlite'
                source = Agent(path)
                source.ensure_conversation('hosted-only','CUST-HOSTED')
                source.db.commit()
                source.save_csat('hosted-only','CUST-HOSTED','hosted-rating',5,'Hosted feedback')
                source.db.close()
                result = preserve_and_import(path,url)
                self.assertEqual(result['counts']['csat'],1)
                self.assertEqual(destination.csat_responses('hosted-only')[0]['rating'],5)
                self.assertEqual(preserve_and_import(path,url)['status'],'already_imported')
                archived = destination.db.connection.execute('SELECT data FROM legacy_sqlite_backups').fetchone()[0]
                restored = Path(directory)/'restored.sqlite'
                restored.write_bytes(archived)
                import sqlite3
                with sqlite3.connect(restored) as db:
                    self.assertEqual(db.execute('SELECT comment FROM csat').fetchone()[0],'Hosted feedback')
                # A differing record is archived but must never overwrite Neon.
                with sqlite3.connect(path) as db:
                    db.execute('UPDATE csat SET comment=?',('Conflicting feedback',))
                with self.assertRaisesRegex(ValueError,'Archive saved'):
                    preserve_and_import(path,url)
                self.assertEqual(destination.csat_responses('hosted-only')[0]['comment'],'Hosted feedback')
                self.assertEqual(destination.db.connection.execute('SELECT count(*) FROM legacy_sqlite_backups').fetchone()[0],2)
        finally:
            destination.db.close()
            root.connection.execute(f'DROP SCHEMA {schema} CASCADE')
            root.close()

    def test_migration_and_customer_support_round_trip(self):
        from psycopg.conninfo import make_conninfo
        from PIL import Image
        schema = 'threadly_test_' + uuid.uuid4().hex
        root = PostgresDatabase(os.environ['THREADLY_TEST_DATABASE_URL'])
        root.connection.execute(f'CREATE SCHEMA {schema}')
        url = make_conninfo(os.environ['THREADLY_TEST_DATABASE_URL'], options=f'-c search_path={schema}')
        target = PostgresDatabase(url)
        hosted = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'source.sqlite'
                local = Agent(source)
                oid = 'ORD-20251'
                cid = local.orders[oid]['Customer_ID']
                session = 'migration-fixture'
                result = local.chat('Marked delivered but not received ' + oid, session=session,
                                    customer_id=cid, today=date(2026,11,20))
                action = local.confirm(result, session)
                local.update_request(action, 'in_progress', 'Test support', 'Checking delivery')
                local.save_csat(session, cid, 'test-rating', 5, 'Helpful and clear')
                photo = io.BytesIO()
                Image.new('RGB', (8,8), 'red').save(photo, format='PNG')
                local.add_photo(session, cid, oid, 'evidence.png', photo.getvalue())
                local.db.execute('INSERT INTO chat_feedback VALUES(?,?)', (session,json.dumps({'ended':True})))
                local.db.commit()
                local.db.close()
                backup = Path(directory) / 'backup.sqlite'
                snapshot(source, backup)
                counts = migrate(backup, target)
                self.assertEqual(counts['csat'], 1)
                self.assertEqual(counts['evidence'], 1)
                self.assertEqual(counts, migrate(backup, target))  # safe rerun
                target.close()
                hosted = Agent(db_url=url)
                self.assertEqual(hosted.db.backend, 'postgres')
                self.assertEqual(hosted.csat_responses(session)[0]['rating'], 5)
                self.assertEqual(hosted.photos(session,cid)[0]['data'], photo.getvalue())
                self.assertEqual(hosted.support_actions()[0]['status'], 'in_progress')
                self.assertTrue(hosted.support_conversations())
                self.assertTrue(hosted.messages(session,cid))
                hosted.update_request(action, 'completed', 'Test support', 'Checked')
                self.assertEqual(hosted.support_actions()[0]['status'], 'completed')
                hosted.save_csat(session,cid,'second-rating',4,'Works after reconnect')
                hosted.save_csat(session,cid,'second-rating',4,'Must not duplicate')
                self.assertEqual(len(hosted.csat_responses(session)),2)
                key, before = hosted.db.execute('SELECT variant,qty FROM stock LIMIT 1').fetchone()
                with self.assertRaises(RuntimeError):
                    with hosted.db:
                        hosted.db.execute('UPDATE stock SET qty=qty-1 WHERE variant=?',(key,))
                        raise RuntimeError('Test rollback')
                self.assertEqual(hosted.db.execute('SELECT qty FROM stock WHERE variant=?',(key,)).fetchone()[0],before)
                # A conflicting migration cannot overwrite newly collected feedback.
                target = PostgresDatabase(url)
                with self.assertRaisesRegex(ValueError,'different data'):
                    migrate(backup,target)
                self.assertEqual(len(hosted.csat_responses(session)),2)
                target.close()
                response = hosted.chat('Where is my order '+oid,session='new-neon-chat',customer_id=cid,today=date(2026,11,20))
                self.assertEqual(response['status'],'answered')
                hosted.db.close()
                hosted = Agent(db_url=url)
                self.assertEqual(len(hosted.messages('new-neon-chat',cid)),2)
                self.assertEqual(len(hosted.csat_responses(session)),2)
        finally:
            if hosted is not None:
                hosted.db.close()
            target.close()
            root.connection.execute(f'DROP SCHEMA {schema} CASCADE')
            root.close()
