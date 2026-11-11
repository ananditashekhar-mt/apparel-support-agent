"""Runtime storage: SQLite offline, TLS PostgreSQL when DATABASE_URL is set.

The SQL adapter handles only this application's owned SQL, never customer SQL.
Explicit SQLite paths always win, so tests cannot write to the hosted database.
"""
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import threading

ROOT = Path(__file__).resolve().parent
SCHEMA = (ROOT / 'migrations/001_runtime.sql').read_text()
_READY_DATABASES = set()
_INITIALIZE_LOCK = threading.Lock()


def schema_columns():
    with sqlite3.connect(':memory:') as db:
        db.executescript(SCHEMA)
        return {row[0]: [col[1] for col in db.execute(f'PRAGMA table_info({row[0]})')]
                for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


COLUMNS = schema_columns()


def database_fingerprint():
    return hashlib.sha256(os.getenv('DATABASE_URL', '').encode()).hexdigest()[:16]


def postgres_sql(statement):
    """Translate the small SQLite dialect used by Agent to parameterized Postgres."""
    statement = statement.strip().rstrip(';')
    match = re.match(r'INSERT( OR (IGNORE|REPLACE))? INTO (\w+)\s*(.*)', statement, re.I | re.S)
    if match:
        _, conflict, table, tail = match.groups()
        columns = COLUMNS[table]
        if tail.lstrip().upper().startswith('VALUES'):
            tail = '(' + ','.join(columns) + ') ' + tail
        statement = f'INSERT INTO {table} {tail}'
        if conflict == 'IGNORE':
            statement += ' ON CONFLICT DO NOTHING'
        elif conflict == 'REPLACE':
            primary = columns[0]
            statement += f' ON CONFLICT ({primary}) DO UPDATE SET ' + ','.join(
                f'{column}=EXCLUDED.{column}' for column in columns[1:])
    statement = re.sub(r'\browid\b', '_seq', statement)
    # All placeholders in owned statements are outside literals.
    return statement.replace('?', '%s')


class PostgresDatabase:
    backend = 'postgres'

    def __init__(self, url):
        self._url = url
        self._connect()

    def _connect(self):
        import psycopg
        import certifi
        try:
            self.connection = psycopg.connect(
                self._url, autocommit=True, connect_timeout=15,
                keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
                sslmode='verify-full', sslrootcert=certifi.where())
        except Exception:
            raise RuntimeError('Unable to connect to PostgreSQL. Check DATABASE_URL and database availability.') from None

    def check_connection(self):
        """Reconnect an idle Streamlit session before any new writes begin."""
        import psycopg
        from psycopg.pq import TransactionStatus
        if self.connection.closed:
            self._connect()
        elif self.connection.info.transaction_status == TransactionStatus.IDLE:
            try:
                self.connection.execute('SELECT 1')
            except psycopg.OperationalError:
                self.connection.close()
                self._connect()

    def _begin(self):
        from psycopg.pq import TransactionStatus
        if self.connection.info.transaction_status == TransactionStatus.IDLE:
            self.connection.execute('BEGIN')

    def execute(self, statement, parameters=None):
        if re.match(r'\s*(INSERT|UPDATE|DELETE|CREATE|ALTER)', statement, re.I):
            self._begin()
        return self.connection.execute(postgres_sql(statement), parameters)

    def executemany(self, statement, rows):
        self._begin()
        with self.connection.cursor() as cursor:
            cursor.executemany(postgres_sql(statement), rows)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        self._begin()
        return self

    def __exit__(self, error_type, error, traceback):
        self.rollback() if error_type else self.commit()
        return False


def open_database(db_path=None, db_url=None):
    url = db_url if db_url is not None else os.getenv('DATABASE_URL', '')
    if db_path is None and url:
        return PostgresDatabase(url)
    return sqlite3.connect(str(db_path or ROOT / 'runtime_india_2026.sqlite'), check_same_thread=False)


def initialize_database(db):
    if not isinstance(db, PostgresDatabase):
        db.executescript(SCHEMA)
        db.executescript('''CREATE INDEX IF NOT EXISTS conversations_customer_updated ON conversations(customer_id,updated_at);
            CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS events_session ON events(session);''')
        return
    with db:
        # Serialize first-run schema creation across Streamlit sessions.
        db.connection.execute('SELECT pg_advisory_xact_lock(84720351)')
        for statement in SCHEMA.split(';'):
            if not statement.strip():
                continue
            statement = re.sub(r'\bBLOB\b', 'BYTEA', statement)
            statement = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', statement)
            end = statement.rfind(')')
            statement = statement[:end] + ', _seq BIGINT GENERATED BY DEFAULT AS IDENTITY UNIQUE' + statement[end:]
            db.execute(statement)
        db.execute('CREATE INDEX IF NOT EXISTS conversations_customer_updated ON conversations(customer_id,updated_at DESC)')
        db.execute('CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id)')
        db.execute('CREATE INDEX IF NOT EXISTS events_session ON events(session,_seq DESC)')


def prepare_runtime_database(db, stock):
    """Bootstrap once per process/database/version, never reseeding sold stock.

    Each Agent retains its own connection. The lock and readiness marker share
    only bootstrap status, not customer data or a mutable agent/transaction.
    SQLite files are initialized independently for offline use and isolation.
    """
    if not isinstance(db, PostgresDatabase):
        initialize_database(db)
        db.executemany('INSERT OR IGNORE INTO stock VALUES(?,?)', stock)
        db.commit()
        return
    key=hashlib.sha256((db._url+SCHEMA+repr(stock)).encode()).hexdigest()
    with _INITIALIZE_LOCK:
        if key in _READY_DATABASES:
            return
        try:
            initialize_database(db)
            db.executemany('INSERT OR IGNORE INTO stock VALUES(?,?)', stock)
            db.commit()
        except Exception:
            db.rollback()
            raise
        # Failed initialization must be retried on the next session.
        _READY_DATABASES.add(key)
