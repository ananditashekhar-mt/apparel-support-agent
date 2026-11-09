"""Preserve the live host's SQLite before using Neon on its first upgraded run."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from database import COLUMNS, PostgresDatabase, initialize_database
from migrate_database import snapshot


def preserve_and_import(source, url):
    """Archive the complete database first, then merge disjoint runtime records.

    Conflicting IDs stop the cutover with the archive retained. Stock is already
    authoritative in Neon; only previously unseen exchange reservations affect it.
    """
    source = Path(source)
    if not source.is_file():
        return {'status': 'no_legacy_file', 'counts': {}}
    with tempfile.TemporaryDirectory() as directory:
        backup = Path(directory) / 'legacy.sqlite'
        snapshot(source, backup)
        payload = backup.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        with sqlite3.connect(backup) as original:
            available = {r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if available - set(COLUMNS) - {'sqlite_sequence'}:
                raise ValueError('Legacy database has unknown tables. Cutover stopped for review.')
            rows = {table: original.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid").fetchall()
                    if table in available else [] for table, columns in COLUMNS.items()}
        db = PostgresDatabase(url)
        try:
            initialize_database(db)
            # Commit the source archive independently: a later merge failure
            # must never discard the backup we are relying on for recovery.
            with db:
                db.connection.execute('''CREATE TABLE IF NOT EXISTS legacy_sqlite_backups (
                    id TEXT PRIMARY KEY, data BYTEA NOT NULL, created_at TEXT NOT NULL,
                    counts TEXT NOT NULL, imported_at TEXT)''')
                db.connection.execute('''INSERT INTO legacy_sqlite_backups(id,data,created_at,counts)
                    VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                    (digest,payload,datetime.now(timezone.utc).isoformat(),json.dumps({k:len(v) for k,v in rows.items()})))
            counts = {}
            with db:
                db.connection.execute('SELECT pg_advisory_xact_lock(84720351)')
                receipt = db.connection.execute('SELECT imported_at FROM legacy_sqlite_backups WHERE id=%s FOR UPDATE',(digest,)).fetchone()
                if receipt[0]:
                    return {'status': 'already_imported', 'counts': {k:len(v) for k,v in rows.items()}}
                db.connection.execute('LOCK TABLE '+','.join(COLUMNS)+' IN EXCLUSIVE MODE')
                # Preserve existing Neon stock, seeded only if this is a new DB.
                existing_variants = {r[0] for r in db.execute('SELECT variant FROM stock')}
                new_stock = [r for r in rows['stock'] if r[0] not in existing_variants]
                seeded_variants = {r[0] for r in new_stock}
                if new_stock:
                    db.executemany('INSERT OR IGNORE INTO stock VALUES(?,?)',new_stock)
                for table, columns in COLUMNS.items():
                    if table == 'stock':
                        continue
                    counts[table] = 0
                    selected = ','.join(columns)
                    if not rows[table]:
                        continue
                    existing_rows = {r[0]: r for r in db.connection.execute(
                        f'SELECT {selected} FROM {table} WHERE {columns[0]}=ANY(%s)',
                        ([r[0] for r in rows[table]],)).fetchall()}
                    inserts = []
                    for row in rows[table]:
                        existing = existing_rows.get(row[0])
                        if existing is not None:
                            if tuple(existing) != tuple(row):
                                raise ValueError(f'Legacy {table} conflicts with Neon. Archive saved; cutover stopped for review.')
                            continue
                        if table == 'actions' and row[3] == 'exchange':
                            reservation = json.loads(row[4])
                            if reservation['variant'] not in seeded_variants:
                                changed = db.execute('UPDATE stock SET qty=qty-? WHERE variant=? AND qty>=?',
                                                     (reservation['qty'],reservation['variant'],reservation['qty'])).rowcount
                                if not changed:
                                    raise ValueError('Legacy exchange stock needs review. Archive saved; cutover stopped.')
                        inserts.append(row)
                        counts[table] += 1
                    if inserts:
                        db.executemany(f'INSERT INTO {table} ({selected}) VALUES('+','.join(['?']*len(columns))+')',inserts)
                db.connection.execute('UPDATE legacy_sqlite_backups SET imported_at=%s WHERE id=%s',
                                      (datetime.now(timezone.utc).isoformat(),digest))
            return {'status': 'imported', 'counts': counts}
        finally:
            db.close()
