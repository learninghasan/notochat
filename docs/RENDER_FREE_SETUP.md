# Render free testing deployment

The root `render.yaml` provisions only a **free Docker web service** named
`notochat-api-demo`. It does not provision a database, disk, worker, cron job,
paid service, provider credential or generated secret. Automatic deploys are off.
Frontend remains the existing Vercel Next.js deployment.

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
or user-flow check. Then configure Vercel `BACKEND_URL` to the verified Render
HTTPS origin. For account mode, Vercel also needs durable `AUTH_DATABASE_URL`,
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

Vercel **Explore NotoChat** remains a browser-local sample until backend wiring
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
