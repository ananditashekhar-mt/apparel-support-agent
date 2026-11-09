# Threadly database on Neon

The UI remains a Python Streamlit app. Neon hosts its runtime Postgres database;
`neon deploy` provisions database services, not the Streamlit website. The customer,
order, product and policy sample data continue to come from versioned JSON in `data/`.
Conversations, tickets, inventory reservations, ratings, comments, photo evidence,
usage and errors use PostgreSQL when `DATABASE_URL` is configured.

## Local setup

Install the Python dependencies with `.venv/bin/pip install -r requirements.txt`.
Neon CLI configuration is in `neon.ts`; the private project link is in ignored `.neon`.
`neon deploy` pulls `DATABASE_URL` (pooled app traffic) and
`DATABASE_URL_UNPOOLED` (direct migrations) into the existing ignored `.env`.
Existing OpenAI settings are retained. Never paste connection strings in chat or git.

The app uses psycopg with TLS hostname and certificate verification via certifi.
A configured connection failure is an error; it never silently writes to SQLite.
An explicit Agent SQLite path always wins, keeping unit tests isolated.
Changing the database URL recreates the Streamlit session's database connection.

## Migration

Stop source writes during final cutover. The command takes a consistent SQLite
backup, leaves the original untouched, and verifies every value (including bytes
and insertion order) before committing the Postgres transaction.

```sh
.venv/bin/python migrate_database.py --source runtime_india_2026.sqlite
.venv/bin/python migrate_database.py --source runtime_india_2026.sqlite --apply
```

The first command is a dry run and backup only. The second uses
`DATABASE_URL_UNPOOLED`. It copies all 13 runtime tables. An unchanged snapshot is
safe to rerun. Different existing destination rows abort the entire copy: this
is intentionally not a merge or an overwrite tool. Backups are retained under
ignored `outputs/db-backups/`; keep a separate secure copy before deployment.

Test migrations on a Neon branch before production. No additional Neon Auth,
Functions, AI Gateway or Object Storage services are required by this migration.

## Verification

`npm run build` checks neon.ts with TypeScript, compiles the Python entry points,
and validates the canonical schema. It is a verification command for this Python
app, not a JavaScript frontend bundle. It expects the project's `.venv`.

```sh
npm run build
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m streamlit run app.py --server.port 8503
```

The opt-in `tests/test_postgres.py` uses `THREADLY_TEST_DATABASE_URL` containing a
test branch's direct connection. It creates and removes a uniquely named test
schema. It exercises migration, idempotency, conflicts, rollback, chat, support
updates, binary photo evidence, feedback and persistence across reconnection.
It is skipped when this variable is absent. Do not put this URL in command text.

## Hosted cutover (separate from local setup)

The existing hosted Streamlit app is unchanged by `neon deploy`. The local
snapshot does not contain separate hosted activity. On its first upgraded hosted
run, `hosted_cutover.py` snapshots any existing `runtime_india_2026.sqlite` and
commits its complete bytes and row counts to the private `legacy_sqlite_backups`
table before attempting import. It merges previously unseen runtime IDs and
ignores exact duplicates. Different records with the same ID stop the cutover
for review, with the archive retained. It preserves Neon stock and applies only
new legacy exchange reservations. A receipt makes later restarts idempotent.

This can preserve only a SQLite file still present on the running host. Verify
the archive's counts and imported timestamp after deployment; do not assume a
rebuild preserved the file. A missing legacy file is reported separately and
must not be described as a successful legacy-data backup.

Install the updated requirements and save the production `DATABASE_URL` in
Streamlit Settings → Secrets using the same key name. For the first hosted
cutover, also provide `DATABASE_URL_UNPOOLED` for the archive/import connection.
The app's ongoing traffic uses only `DATABASE_URL`. Reboot after saving, then
verify a new conversation, ticket update and submitted rating from Support.
Remove the direct URL from hosted Secrets after the cutover has been verified
if it is no longer needed for future migration work.
Do not delete SQLite backups after cutover. If rolling back code, keep PostgreSQL
configured to avoid splitting new feedback between two databases.

Neon Free has resource limits and is not an independent backup. Monitor storage
and compute in the Neon console, especially uploaded photo evidence stored in
BYTEA. Product thumbnails remain static repository assets.
