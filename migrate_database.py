"""Copy a consistent SQLite snapshot into Neon, without changing the source.

Usage: .venv/bin/python migrate_database.py --source runtime_india_2026.sqlite --apply
Without --apply this only creates a local backup and reports source counts.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from database import COLUMNS, PostgresDatabase, initialize_database


def snapshot(source, destination):
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError('Source SQLite file does not exist.')
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(destination) as backup:
            original.backup(backup)


def migrate(source, target):
    """All-or-nothing copy. Existing equal rows are safe to rerun; conflicts abort."""
    initialize_database(target)
    counts = {}
    with sqlite3.connect(source) as original, target:
        target.connection.execute('SELECT pg_advisory_xact_lock(84720351)')
        available = {r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unknown = available - set(COLUMNS) - {'sqlite_sequence'}
        if unknown:
            raise ValueError('Source has unknown tables; update the migration before proceeding.')
        # Prevent writes while verifying/copying; acquire all locks in canonical order.
        target.connection.execute('LOCK TABLE ' + ','.join(COLUMNS) + ' IN EXCLUSIVE MODE')
        for table, columns in COLUMNS.items():
            selection = ','.join(columns)
            rows = original.execute(f'SELECT rowid,{selection} FROM {table} ORDER BY rowid').fetchall() if table in available else []
            existing = target.connection.execute(f'SELECT _seq,{selection} FROM {table} ORDER BY _seq').fetchall()
            if existing:
                if existing != rows:
                    raise ValueError(f'Destination {table} contains different data; migration rolled back. Use an empty destination.')
            elif rows:
                with target.connection.cursor() as cursor:
                    cursor.executemany(f'INSERT INTO {table} (_seq,{selection}) VALUES (' + ','.join(['%s'] * (len(columns)+1)) + ')', rows)
            copied = target.connection.execute(f'SELECT _seq,{selection} FROM {table} ORDER BY _seq').fetchall()
            if copied != rows:
                raise ValueError(f'Row verification failed for {table}; migration rolled back.')
            counts[table] = len(rows)
        for table in COLUMNS:
            # Identity sequences are advanced beyond imported SQLite row IDs.
            target.connection.execute(f"SELECT setval(pg_get_serial_sequence('{table}','_seq'), COALESCE((SELECT MAX(_seq) FROM {table}),0)+1, false)")
    return counts


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    directory = Path(__file__).parent / 'outputs/db-backups'
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite')
    snapshot(args.source, backup)
    print('Consistent source backup saved:', backup)
    if not args.apply:
        with sqlite3.connect(backup) as db:
            for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                if table in COLUMNS:
                    print(table, db.execute(f'SELECT count(*) FROM {table}').fetchone()[0])
        print('Dry run only. Pass --apply to copy and verify every row in Neon.')
        return
    url = os.getenv('DATABASE_URL_UNPOOLED', '')
    if not url:
        raise ValueError('Set DATABASE_URL_UNPOOLED for migration; use the direct connection.')
    target = PostgresDatabase(url)
    try:
        counts = migrate(backup, target)
        for table, count in counts.items():
            print(f'{table}: {count} rows verified')
        print('Migration committed. Source SQLite retained unchanged.')
    finally:
        target.close()


if __name__ == '__main__':
    main()
