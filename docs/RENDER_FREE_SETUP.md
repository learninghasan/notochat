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
