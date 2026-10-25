# NotoChat

**সব চ্যাট, এক জায়গায়।** A commerce workspace built with Next.js (JavaScript), FastAPI (Python), SQLAlchemy and PostgreSQL. SQLite fallback supports local evaluation. Account mode adds Better Auth business organizations and isolated operational workspaces; the legacy token workspace remains separate. Production operations and several integrations are still unfinished.

## New: accounts and background preparation

Business signup/login, verified invitations, membership removal, owner/member permissions, isolated business storage, encrypted per-business channel settings and durable background draft jobs are implemented. See [account and worker setup](docs/ACCOUNTS_AND_JOBS.md) before deployment. Use `uvicorn server:app` for account-backed requests.

## What you can use

- Inbox across sample channels, human takeover, reasons/assignment, timed return on refresh, customer history and acknowledged notifications.
- Product create/edit/search with SKU, category, image URL, size, price and stock.
- Orders, catalog-priced totals, stock reservation/restoration, idempotent requests, status transitions, manual tracking and receipt downloads.
- Six-stage leads, hot/warm/cold classification and next-contact dates.
- Booking requests, overlap checks, confirmation/cancellation/completion and reminder drafts.
- Knowledge documents with text/Markdown import and keyword search.
- Agent rules with explicit draft, publish and restore workflows.
- Follow-up scheduling, durable background reminder/AI draft preparation and broadcast audience previews; no automatic send.
- Record-based analytics, team profiles and genuine provider token-usage records.
- Backend AI copilot, image analysis and voice transcription when models are configured.
- Signed Meta webhook ingestion, explicit official text delivery (off by default), and isolated website-chat sessions.

See [the complete reference feature map](docs/FEATURES.md) for exact scope and unfinished capabilities.

## Local setup

Requires Python 3.12+, Node 22+ and optionally Docker for PostgreSQL.

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env: replace APP_TOKEN with a long random value.
docker compose up -d
set -a
. ./.env
set +a
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000. **Explore NotoChat** opens a browser-local sample workspace without credentials. **Connect your backend** uses the configured APP_TOKEN. The token is held in page memory, not embedded in code or persisted to browser storage.

To evaluate without PostgreSQL, leave DATABASE_URL unset; the backend creates an SQLite file. Sample conversation/product seeding defaults on for SQLite and off for PostgreSQL. Set SEED_SAMPLE_DATA explicitly if needed. Use PostgreSQL for concurrency: SQLite does not provide the row-lock semantics used by booking and delivery operations.

API documentation: http://127.0.0.1:8000/docs.

## Vercel frontend deployment

Import `learninghasan/notochat` into Vercel and set **Root Directory = frontend**, framework **Next.js**. Without a backend, the deployment provides the interactive browser-local demo. Data stays in that browser and is not shared between devices.

To use server persistence, deploy FastAPI to an ASGI host with a durable PostgreSQL DATABASE_URL and APP_TOKEN, then set BACKEND_URL on the Vercel frontend and redeploy. The native Next.js `/api/*` route proxies workspace requests after verifying account membership; `/api/auth/*` is handled by Better Auth. Do not point BACKEND_URL at localhost in a hosted deployment.

## AI setup

Set OPENAI_API_KEY and OPENAI_MODEL on the backend. Choose a current account-supported Responses API model with image input if using image analysis. Set OPENAI_TRANSCRIBE_MODEL separately for speech-to-text. No model is silently assumed.

Copilot output always needs review. It cannot automatically create orders, verify payment, issue refunds or change stock. Media is limited to 8 MB, sent to the configured AI provider and not saved as a file. Provider token usage is recorded; BDT costs are unknown until pricing is configured. Live model quality has not been evaluated without credentials.

## Official Meta setup

1. Create/review a Meta developer app and grant the appropriate page/account permissions.
2. Configure META_APP_SECRET, META_VERIFY_TOKEN, META_GRAPH_VERSION, META_PAGE_ID and META_PAGE_ACCESS_TOKEN. For WhatsApp, set WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN.
3. Register `https://YOUR-BACKEND/webhooks/meta`. Verification uses the configured verify token; POSTs must carry a valid `X-Hub-Signature-256`.
4. Subscribe approved Messenger/Instagram message and Facebook comment events, or WhatsApp message events. Signed events are deduplicated and create real conversations in the inbox. Attachments currently show a placeholder directing the operator to the original channel.
5. Keep ENABLE_LIVE_SEND=0 until you verify app permissions and real inbound events. Set it to 1 to allow an authenticated human operator to explicitly deliver a saved team reply.

Only a verified recent Meta inbound event qualifies a chat for live text sending. Local test messages cannot open that gate. A conservative 23-hour window is used; template messaging is not implemented. An unconfirmed transport attempt cannot be blindly retried, to avoid duplicate messages. Comment replies, private replies and automatic AI sending are not implemented.

Official references checked: [Messenger send API](https://developers.facebook.com/docs/messenger-platform/send-messages/), [webhooks](https://developers.facebook.com/docs/messenger-platform/webhooks/), [WhatsApp messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages).

## Website chat

Set WIDGET_ENABLED=1 on the backend and WIDGET_FRAME_ANCESTORS to your permitted site origins, for example `https://your-shop.example`. The default is same-origin only.

```html
<iframe src="https://YOUR-BACKEND/widget" title="Chat with our team" width="380" height="580"></iframe>
```

Each visitor gets an expiring capability token stored only in the frame's memory; the server stores its hash. Visitors can read only their conversation. Team replies saved in the backend appear in the frame. The operator dashboard polls server data every 6 seconds when visible; this is polling, not WebSockets. New-session and per-session message limits are enforced. The development session limit uses the direct peer IP; configure trusted proxy handling before a high-volume public rollout. Refreshing the frame starts a new session; anonymous session recovery is not implemented.

## Tests

```bash
cd backend
../.venv/bin/pytest -q
cd ../frontend
npm test
npm run build
```

Tests cover stock atomicity/idempotency, order transitions, booking overlap/reminders, version publication, Unicode knowledge, handover, notification acknowledgement, reply-window gates, signed webhook deduplication, explicit text transport with a mocked provider, isolated website sessions and AI usage recording with a mocked provider. Browser UI verification and live third-party tests remain unperformed.

## Deployment limits

External courier/payment integrations, per-channel access control, push notifications, autonomous AI sales workflows and production operations remain unfinished. Directory entries are profiles; real account members/invitations are managed separately with Better Auth; advance amounts are unverified; reminder/broadcast entries are drafts. Database schema creation is additive via SQLAlchemy create_all; managed migration/rollback and backup procedures are still required. Review [FEATURES.md](docs/FEATURES.md) before onboarding real businesses.
