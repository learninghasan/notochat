# Commerce Inbox

Development MVP: Next.js (JavaScript), FastAPI (Python), SQLAlchemy and PostgreSQL. SQLite fallback for quick local evaluation. Single workspace with sample data, not a production SaaS.

## Run

From this directory:

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env: choose a strong APP_TOKEN. Never commit .env.
docker compose up -d
set -a
. ./.env
set +a
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from frontend:

```bash
npm install
npm run dev
```

Open http://localhost:3000 and click Try interactive demo to use browser-local sample data. No credentials needed for demo. For the real backend, set BACKEND_URL=http://127.0.0.1:8000 in the frontend server environment, restart Next.js, choose the backend connection section, and enter APP_TOKEN. Demo messages persist only in that browser; AI and external channels remain disconnected. To evaluate without Postgres, leave DATABASE_URL unset; the backend creates a local SQLite file. API docs: http://127.0.0.1:8000/docs.

## Implemented

- Persisted sample conversations, channel/customer filtering, catalog and stock.
- AI/human ownership switching; human replies only after takeover.
- Replies saved locally with an explicit offline status; no pretend message delivery.
- Optional real AI draft endpoint using OpenAI Responses API. Set OPENAI_API_KEY and OPENAI_MODEL in backend environment to a model available to your account. Drafts require human review; no automatic send or order creation.
- Server-side shared access token on all customer/product endpoints; secrets never embedded in frontend source.

## Before production

Not connected: Messenger, Instagram, WhatsApp, couriers, payments, voice, image matching, website customer widget. No order creation, multi-tenant isolation, user accounts, roles, rate limits, webhook signature verification, durable worker, delivery receipts or automated replies yet. Do not expose this development MVP as a production customer system. Each integration requires official API credentials, webhook verification, permissions and end-to-end tests. Implement tenant-scoped authentication before onboarding multiple businesses. Production deployment should fail closed if database configuration is missing, replace create_all with migrations and implement backup/retention policies.

## Verify

```bash
cd backend
../.venv/bin/pytest -q
```

## Vercel deployment

Deploy the frontend directory as a Next.js project. The default deployment supports a browser-local interactive demo without server secrets. For backend mode, deploy FastAPI separately with a durable PostgreSQL DATABASE_URL and APP_TOKEN, then set BACKEND_URL in Vercel and redeploy. No live AI, Meta or courier credentials are included.
