CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, session TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, session TEXT, order_id TEXT, kind TEXT, payload TEXT, UNIQUE(session,order_id,kind));
            CREATE TABLE IF NOT EXISTS stock(variant TEXT PRIMARY KEY, qty INTEGER);
            CREATE TABLE IF NOT EXISTS conversations(
                id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, mode TEXT NOT NULL,
                started_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, customer_id TEXT NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS api_usage(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, customer_id TEXT NOT NULL,
                request_id TEXT, model TEXT, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                api_requests INTEGER NOT NULL DEFAULT 0, estimated_cost_usd REAL NOT NULL,
                estimated_cost_inr REAL NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS errors(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, customer_id TEXT NOT NULL,
                mode TEXT NOT NULL, error_type TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS request_updates (action_id TEXT PRIMARY KEY, status TEXT NOT NULL, assignee TEXT NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, customer_id TEXT NOT NULL,
            order_id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(session,id));
            CREATE TABLE IF NOT EXISTS reopenings (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, customer_id TEXT NOT NULL,
            reason TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS csat (id TEXT PRIMARY KEY, session TEXT NOT NULL, customer_id TEXT NOT NULL, rating INTEGER NOT NULL, comment TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_shadows (id TEXT PRIMARY KEY, session TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_feedback (conversation_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
