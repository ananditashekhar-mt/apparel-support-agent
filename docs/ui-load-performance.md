# UI load performance — 11 November 2026

This release reduces ordinary rendering work without changing the design,
model prompts, customer ownership rules or feedback persistence.

- Sidebar history fetches the latest event with each owned conversation in one
  query, with the twelve-item limit applied in SQL. The full history view uses
  the same batched labels. There is no global customer-history cache.
- PostgreSQL schema/index setup and conflict-ignore catalogue seeding run once
  per process/database/schema/catalogue version, rather than per session. A
  lock serializes initialization; failures roll back and remain retryable.
  Every session retains its own connection and Agent. New catalogue variants
  remain seedable, and existing stock quantities are never reset.
- Indexes support customer history, conversation messages and latest events.
- Static JSON parsing is cached by file modification time and size. Callers
  receive independent copies so mutations cannot cross customer sessions.
- Feedback reads are reused only within one script render and updated after
  successful saves. The next rerun reads the database again.
- The Agent resource version changes so already-open sessions acquire the
  updated methods after rollout.

## Validation

Real Neon read-only timing, from the local machine, for twelve saved chats:

| Run | Previous requests/time | Optimized requests/time |
| --- | --- | --- |
| 1 | 25 / 1.570 seconds | 1 / 0.100 seconds |
| 2 | 25 / 1.752 seconds | 1 / 0.051 seconds |

All labels matched. These are history-query timings, not browser page-load
benchmarks. The first measurement attempt lost its database connection; a
fresh connection completed both paired measurements. A subsequent retry was
delayed by an automatic permission-review timeout before execution.

A real Postgres check created and removed its own isolated scratch schema,
without writing production tables. Two separate sessions initialized schema
only once. First-session setup took 2.420 seconds; subsequent-session setup
took 0.433 seconds. Stock changes and saved CSAT survived, customer isolation
held, and all three indexes were present.

Automated suite: 94 tests run, 92 passed, 2 gated Postgres tests skipped, in
37.497 seconds. The separate real-Postgres scratch-schema check passed.
The build passed TypeScript checking, Python compilation and the 13-table
schema check. Four regression tests cover query count, limits, fresh labels,
ownership, bootstrap retry and cache mutation/invalidation.

Streamlit/Neon wake-up time after inactivity and model-response latency remain
separate from this reduction in ordinary UI work. Free-host cold starts are
not eliminated by these changes.
