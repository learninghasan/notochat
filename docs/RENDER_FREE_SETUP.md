# Render free testing deployment

The root `render.yaml` provisions only a **free Docker web service** named
`notochat-api-demo`. It does not provision a database, disk, worker, cron job,
paid service, provider credential or generated secret. Automatic deploys are off.
Frontend runs on the existing free Render Node service `notochat-demo` at
https://notochat-demo.onrender.com; Vercel is not required for this setup.

Build: `deploy/Dockerfile.render`, repository-root context, Python 3.12,
`pip install -r backend/requirements.txt`, FFmpeg/FFprobe, Pillow and pypdf.
Start: `python render_start.py`, then `uvicorn server:app --host 0.0.0.0
--port $PORT --workers 1`. Health path: `/health`.

## Prerequisites and handoff

Connect the Render account and authorize access to `learninghasan/notochat`.
Review/import its Blueprint on the **Free** plan. Any sign-in, new terms,
persistent repository grant or new credential creation requires the user's
approval; no credentials belong in chat, source control or build logs.

Supply an existing approved durable PostgreSQL `DATABASE_URL` using
`postgresql+psycopg://` and the provider's TLS options. The database role must
support the app's tables and tenant schemas. Neon free PostgreSQL is an option
only after separate provisioning/credential approval. Do not substitute Render
Free Postgres as durable storage: it expires after 30 days.

Supply approved `APP_TOKEN`, `INTERNAL_API_SECRET` (each at least 32 characters)
and Fernet `CREDENTIAL_ENCRYPTION_KEY` via Render secret environment fields.
The startup guard rejects SQLite/missing configuration before importing the app.
It never generates credentials or enables customer sends. Keep all configured
send/payment/widget flags at zero. Do not add real provider credentials for this
limited test. Manual AI calls also incur provider costs; they are not free hosting.

After deployment, verify the exact deployed Git commit, HTTPS `/health`, and
unauthenticated `/conversations` rejection. Health alone is not a full database
or user-flow check. Then configure the existing Render frontend `BACKEND_URL` to the verified Render
HTTPS origin. For account mode, that frontend also needs durable `AUTH_DATABASE_URL`,
`BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, matching `INTERNAL_API_SECRET`, approved
SMTP configuration and the existing auth migration. These are separate setup
steps, not automatically performed by this Blueprint. A legacy token session
can exercise a synthetic single-workspace backend without account provisioning;
do not use real customer data. Do not execute migrations against an unknown DB.

## Limits

Render free services sleep after 15 minutes without inbound traffic, have cold
starts and share 750 free instance hours/month per workspace. Filesystem changes
are ephemeral. No customer records or backups may rely on that filesystem.
Transient media parsing uses temporary files only. Media workloads can exceed
free CPU/memory limits; this is not a production capacity guarantee.

No worker is started, and no keep-alive workaround is provided. Automatic AI
replies, scheduled follow-ups, push/email flushing and other background jobs will
not execute reliably on this configuration. Do not enable or promise them.
The worker's existence in the image does not mean it runs.

The frontend **Explore NotoChat** remains a browser-local sample until backend wiring
is complete. A deployed backend with verified synthetic API flows is a
backend-connected demo, not live-verified messaging or production readiness.

Official limits checked: https://render.com/docs/free
Blueprint fields: https://render.com/docs/blueprint-spec

## Verified frontend demo — 2026-10-25

A separate native Node free web service is live at
https://notochat-demo.onrender.com in confirmed workspace
`tea-darmhfp7lnhs73e0d5n0`, Singapore. Service:
`srv-dbf36ht9fdbs738lj200`; deploy: `dep-dbf36id9fdbs738lj3ig`.
Deployed commit: `6bf20769121c317f5de3b04a8a1ef1ee7726d6ed`.
Build: `npm --prefix frontend ci && npm --prefix frontend run build`.
Start: `npm --prefix frontend start`; Node 24; automatic deploys off.
This direct-created frontend is NOT managed by the backend `render.yaml`.

Render status was `live`; public homepage HTTP 200, demo disclaimer/entry and
nine referenced assets verified. Browser click-through was unavailable.
177 Python tests and 19 frontend tests passed locally; backend Docker image
build/runtime dependencies and Blueprint official JSON Schema validated.
Render CLI validation was unavailable (CLI absent). Git push/remote SHA verified;
GitHub Actions status lookup returned HTTP 401 Bad credentials, so this commit's
remote CI result is unverified. No replacement credentials were created.

Only the browser-local demo is deployed. No API, DB, worker or provider credentials
were provisioned. Account login and live AI/messaging remain unconfigured. Existing
MealOps service was not changed; both free services share workspace free hours.

## Pilot readiness — 26 October 2026

The frontend is live; the backend Blueprint is prepared, not deployed. The current
free-test startup guard deliberately refuses live sends, live payments, email sends
and widget activation. Supplying credentials alone will not activate these paths.
An explicitly approved live-pilot configuration and its checks would be a separate
step; do not bypass the test guard by silently changing flags.

Minimum sequence:
1. Approve/select a durable PostgreSQL project and securely configure the database
   and app/auth secrets listed above; approve migrations only for that known DB.
2. Connect the existing frontend to the API, configure verified account email, and
   verify tenant signup/login plus manual catalog sync using synthetic test records.
3. Select one pilot channel, approve its official provider connection and sender
   identity, and define permitted live actions. AI needs an approved provider/budget.
4. Confirm Peoniara shipping/returns policy and inventory authority. The public
   Store API supplies listings, not stock quantity or address-specific shipping.
   Scoped WooCommerce access/checkout contracts are needed for native store orders.
5. Choose reliable worker hosting before enabling unattended replies/follow-ups;
   the free sleeping web service is suitable for manual testing only.

Trial/service-fee decisions can stay disabled and need not block manual evaluation.
WhatsApp QR transport remains a code gap only if that transport is selected.
No supported browser control tools were available for English navigation/visual QA;
HTTP checks and saved-demo migration tests do not substitute for browser testing.
