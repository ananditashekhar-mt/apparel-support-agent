import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import COLUMNS, open_database, initialize_database, postgres_sql
from migrate_database import snapshot


class DatabaseTests(unittest.TestCase):
    def test_explicit_path_isolated_from_hosted_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'DATABASE_URL': 'invalid-secret-url'}):
            db = open_database(Path(directory) / 'test.sqlite')
            initialize_database(db)
            self.assertEqual(len(COLUMNS), 13)
            self.assertEqual(db.execute('SELECT count(*) FROM csat').fetchone()[0], 0)
            db.close()

    def test_owned_sql_translation(self):
        self.assertEqual(postgres_sql('INSERT OR IGNORE INTO stock VALUES(?,?)'),
                         'INSERT INTO stock (variant,qty) VALUES(%s,%s) ON CONFLICT DO NOTHING')
        self.assertIn('ON CONFLICT (conversation_id) DO UPDATE SET payload=EXCLUDED.payload',
                      postgres_sql('INSERT OR REPLACE INTO chat_feedback VALUES(?,?)'))
        self.assertEqual(postgres_sql('SELECT a.id FROM actions a ORDER BY a.rowid DESC'),
                         'SELECT a.id FROM actions a ORDER BY a._seq DESC')

    def test_snapshot_keeps_committed_rows_and_binary_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source, backup = [Path(directory) / name for name in ('source.sqlite', 'backup.sqlite')]
            db = open_database(source)
            initialize_database(db)
            db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)', ('id','session','customer','order','photo','image/png',b'\x00\xff','date'))
            db.commit()
            snapshot(source, backup)
            copy = open_database(backup)
            self.assertEqual(copy.execute('SELECT data FROM evidence').fetchone()[0], b'\x00\xff')
            copy.close()
            db.close()
