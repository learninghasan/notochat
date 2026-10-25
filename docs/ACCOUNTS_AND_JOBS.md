# Accounts, isolated businesses and background preparation

This describes the account/worker increment. The later [sales/service setup](SALES_PAYMENTS_AND_DELIVERY.md) and [current feature map](FEATURES.md) supersede its older limitations about automatic sales, channel permissions, billing and push.

## Services

Run the Next.js frontend, FastAPI gateway and a separate Python worker. Production requires durable PostgreSQL storage; browser demo remains independent and browser-local.

```bash
# Backend (from backend/, with backend environment loaded)
../.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000

# Worker, in a separate process with the same database/key configuration
../.venv/bin/python worker.py

# One processing pass, useful in staging
../.venv/bin/python worker.py --once
```

`main:app` remains a legacy token-only single workspace. Account-backed requests must use `server:app`. Do not configure the Vercel proxy against a legacy-only server and expect business sessions to work.

## Frontend configuration

- `BACKEND_URL`: public/private-reachable FastAPI gateway origin.
- `AUTH_DATABASE_URL`: native PostgreSQL connection URL for Better Auth. This may use a separate database from operational data.
- `BETTER_AUTH_SECRET`: independent random secret of at least 32 characters.
- `BETTER_AUTH_URL`: exact public frontend origin. Production login and mutating account-backed API requests use this origin.
- `INTERNAL_API_SECRET`: independent random secret of at least 32 characters, shared only with the backend gateway. Never use a NEXT_PUBLIC variable.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_FROM` and, if required, `SMTP_USER`, `SMTP_PASSWORD`: email transport for verification, reset and invitations. Production authentication refuses to initialize without email host/from configuration. SMTP connectivity/deliverability must still be verified.

For persistent local development on Node 22+, `AUTH_SQLITE_PATH` is supported only when NODE_ENV is not production. Do not use it for Vercel persistence. Without SMTP, local signup can sign in without verification, but invitation acceptance still requires a verified email. Use a local test mail server for the full email flow.

Run account migrations once, with frontend configuration loaded:

```bash
cd frontend
npm run auth:migrate
```

Migrations are explicit and are never run on a visitor request. The script uses the installed Better Auth version's migration API. Better Auth uses secure session cookies, password hashing, token-based email verification/reset, persisted rate-limit counters and its organization plugin. Configure trusted proxy/client-IP handling for your deployment; the default shared fallback rate bucket can limit unrelated users when a trusted client IP is unavailable.

## Backend configuration

- `DATABASE_URL`: SQLAlchemy PostgreSQL connection URL, typically `postgresql+psycopg://…`.
- `INTERNAL_API_SECRET`: must match the frontend, not a browser-facing key.
- `CREDENTIAL_ENCRYPTION_KEY`: a Fernet key generated with `cryptography.fernet.Fernet.generate_key()`. Keep it outside the database and source repository; losing it makes saved channel tokens unreadable. Key rotation/re-encryption is not implemented.
- `APP_TOKEN`: optional legacy workspace access. This token never grants access to account-backed business schemas.
- `SEED_SAMPLE_DATA=0`: recommended for hosted data. Isolated businesses are never seeded even when development legacy seeding is enabled.
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TRANSCRIBE_MODEL`: provider configuration; actual account-supported model IDs required.

The operational database role needs permission to create business schemas and tables. PostgreSQL namespaces are generated server-side from organization IDs. Local development uses separate files under TENANT_SQLITE_DIR. Do not store the SQLite directory in Git.

## Request trust and permissions

The frontend API route verifies the Better Auth session and **current** active organization membership on every account-backed request. It does not trust an organization ID from a browser header. It signs the user, business, role, HTTP method, full path/query, request-body hash, short timestamp and random nonce. The gateway validates all fields and rejects reused nonces. Cookies alone never authenticate a backend request. Session-cookie caching is disabled so membership revocation is not hidden behind the client cache.

Each business gets a separate PostgreSQL schema (or development SQLite file) for conversations, products, orders, documents, credentials, jobs and other records. The legacy workspace is separate. Owners/admins can change catalog, agent rules, connection configuration and team profiles; members can handle conversations, orders, leads, bookings and notification acknowledgement. The backend enforces those mutation permissions. Better Auth enforces real invitation/membership operations. Channel-specific or assigned-chat-only permissions are still unfinished; the profile directory's channels do not enforce them.

## Per-business channel setup

Open **Connections** as an owner/admin. Enter the business's Meta secrets/IDs and supported Graph API version. Messenger Page ID and Instagram professional-account ID are separate fields; an Instagram access token can be supplied independently, with the Page token as fallback for the Facebook-login integration. Secrets are encrypted in that business's data store. API responses show configured flags and non-secret IDs; saved secrets are not returned.

Callbacks for business `ORGANIZATION_ID`:

- `https://BACKEND/business/ORGANIZATION_ID/webhooks/meta`
- `https://BACKEND/business/ORGANIZATION_ID/widget`

Only registered business IDs route to public callbacks. Meta callbacks still require the business's verify token and app-secret signature. Widget sessions use their own expiring capability tokens. Legacy global environment credentials never silently apply to an isolated business. Enable website chat and set exact allowed HTTPS embedding origins in Connections.

Explicit live text sending is off by default. Enable it only after testing the provider app/permissions and signed inbound flow. There is no automatic AI send, template send or automatic courier/payment operation.

## Background work

Jobs are stored durably with pending/running/done/failed/cancelled states, leases, bounded attempts and exponential retry backoff. Atomic claims prevent two workers from claiming the same pending state. Expired leases are recoverable. The worker also returns expired handovers without requiring dashboard refresh.

- A reminder draft can be **activated for preparation**. At execution time the worker rechecks the reply window and marks it ready or blocked, with a persistent notification. It never sends a customer message.
- **Queue AI draft** prepares a reviewable response in the background.
- Agent rules can opt into **automatic draft preparation** for incoming messages while a conversation is in AI mode. Newer messages or human takeover cause stale automatic work to be skipped. It is disabled by default and still requires a running worker/provider.
- Prepared drafts appear in the customer's sidebar; the operator copies/reviews them and saves a reply. Live Meta delivery remains a separate explicit action.

This is draft automation, not autonomous sales. Automatic order confirmation, payment verification, delivery, customer messaging, broadcast sending and low-credit shutdown are not implemented.

## Verification performed

- Real Better Auth handler tests: signup, password login, organization ownership, unauthorized organization access, verified invitation acceptance, member denial, member removal and logout.
- Gateway tests: business data isolation, owner/member mutations, signed method/path/query/body binding, expiry/replay rejection, encrypted credential storage and public callback isolation.
- Durable worker tests: preparation exactly once in normal processing, execution-time eligibility, cancellation, retry backoff, expired-lease recovery and takeover cancellation of automatic drafts.
- A disposable PostgreSQL 17 instance: schema isolation, concurrent stock contention, idempotent order retries, serialized booking conflicts, auth migrations, signup and organization creation.

No live Meta/OpenAI/SMTP provider test or browser UI run has been performed. Billing, courier integrations, PWA/push, Chrome copilot, per-channel access, production backups and account/tenant deletion remain unfinished.
