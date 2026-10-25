# Automatic sales, delivery, billing and device setup

Read [account/worker setup](ACCOUNTS_AND_JOBS.md) first. This document supersedes that earlier increment's statements that no automatic sales, courier, credit or device code exists.

## Automatic sales

Publish Agent desk rules with **Automatic customer replies** enabled. Keep it off while preparing catalog/policies. Run the backend worker beside the API. For Meta channels, business connection settings must also enable live text sending; a signed inbound event inside the conservative 23-hour window is required. Website chat uses isolated customer sessions.

The AI produces a validated intent and catalog IDs, not an arbitrary executable action. Actual price/stock text comes from saved products. Customer details must appear in the conversation before a proposal is prepared. The customer sees product, quantity, address, delivery charge and total, then must type `CONFIRM CODE` (or its supported Bengali equivalent) exactly. The code expires after 30 minutes. Stock/price are checked again and the order uses an idempotency key. COD only is created automatically. Delivery charges use the configured outside-Dhaka rate conservatively; the complete charge is displayed before confirmation.

Complaints/refunds and uncertain intents hand over to the team. Refunds, discounts, payments and courier bookings cannot be performed by the model. Human takeover/newer customer messages invalidate stale generated work. Website responses appear directly; Meta responses go through the official text adapter. Duplicate/unconfirmed transport attempts are not blindly retried.

`OPENAI_MODEL` must support Responses API structured JSON schemas. Actual Bengali/Banglish intent quality and model compatibility require a live evaluation. Image/voice uploads are still reviewable analysis, not automatic attachment-to-checkout processing.

## Courier setup

Enter merchant credentials in Connections; they remain encrypted. Pathao uses its sandbox by default. Explicitly enable **live courier bookings** before booking a real shipment. Booking can incur merchant courier fees; it is an operator action, not an AI tool.

- Steadfast: API key and secret key. No sandbox adapter is available here.
- Pathao: client ID/secret, merchant username/password, pickup store and recipient city/zone/area IDs. Use the merchant account/location documentation for IDs.
- Book from an order's **Book courier** action. Prepaid orders require verified payment; current ordinary orders are unverified, so COD is the supported path.
- **Sync courier status** reads the authenticated courier API. Delivered status is updated only from that provider response. Sandbox shipments do not mark real orders shipped/delivered.
- Optional webhook: configure a bearer token and `/business/ORGANIZATION_ID/webhooks/courier`. The webhook body is only a trigger; status is rechecked with the provider instead of trusted directly.

Network timeouts leave booking **unconfirmed** and block duplicate requests. Reconcile with the merchant dashboard before manually recording a shipment. Refund/courier cancellation reconciliation is not implemented.

Public contracts inspected: [Steadfast SDK](https://github.com/shahria7k/steadfast-courier) and [Pathao SDK](https://github.com/codeboxrcodehub/pathao-courier). Merchant documentation was not publicly accessible in this session. Mocks validate adapter shapes; no live booking was made.

## Recharge / usage

Server-only configuration:

- `SSLCOMMERZ_STORE_ID`, `SSLCOMMERZ_STORE_PASSWORD`.
- `SSLCOMMERZ_LIVE=0` defaults to the sandbox. Set to `1` only for an approved live store.
- `PUBLIC_BACKEND_URL`: public HTTPS gateway origin for callbacks.
- `AI_BILLING_ENABLED=1` to enforce credits in development; `APP_ENV=production` enforces billing regardless of that development toggle.
- `AI_INPUT_PAISA_PER_MILLION`, `AI_OUTPUT_PAISA_PER_MILLION`: positive operator-disclosed service rates for input/output tokens. They are not assumed to equal provider USD costs. Credits are rounded up to whole paisa per request.

Recharge uses hosted checkout. Payment methods depend on the merchant's enabled SSLCommerz channels; this is not a direct bKash/Nagad API integration. The callback calls the provider's validation API and checks transaction, amount, currency, status, validation reference, risk and environment before posting credit. Duplicate callbacks are safe. Sandbox test credits use a separate balance and **cannot fund real AI**. Confirmed live credit resumes credit-exhausted pending/failed jobs.

Provider token usage creates ledger debits only when billing is enabled. A positive balance is checked before a request; a request can finish below zero if its measured cost exceeds the remaining balance, and subsequent AI processing then stops. Prices are operator configured. Audio metering is not configured, so audio processing is blocked while credit enforcement is enabled. Low-credit alerts are persistent notifications/push, not email yet.

Payment callback paths: `/business/ORGANIZATION_ID/payments/ipn` and `/business/ORGANIZATION_ID/payments/return`. A redirect never proves successful payment. See [SSLCommerz v4 documentation](https://developer.sslcommerz.com/doc/v4/).

## PWA / push

The app registers a service worker and advertises its manifest. The offline fallback caches no authenticated pages, API data or tokens. Browser installation support varies by device.

Set backend `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (usually `mailto:...`). Enable device notifications explicitly from Notifications. The worker sends generic update messages; customer names/addresses/message contents are never included. Endpoint hosts are restricted to supported browser push providers. Dead subscriptions are removed; device/member lifecycle cleanup still needs completion. Production browser/device delivery was not tested.

## Knowledge and invoices

PDF import accepts unencrypted PDFs up to 5 MB / 50 pages with selectable text. Scanned PDF OCR is not available. Set `OPENAI_EMBEDDING_MODEL` to enable document indexing and semantic search; query results cite saved document IDs/titles. A dedicated vector index is not implemented. Token usage is metered at the configured service input rate.

Order invoices can be printed and saved as PDF by the browser. Dynamic content is HTML escaped and the document marks unverified payments. This is not a signed tax invoice or an emailed receipt.

## Exports, audit and backups

Connections offers owner/admin export and account activity. Export excludes private connection records, session tokens and push subscriptions. Audit records contain user/business IDs, method/path/time/status, without request bodies or secrets. The audit sink is best effort after a committed operation, not tamper-proof compliance storage.

Set a separate `BACKUP_ENCRYPTION_KEY` (32 random bytes encoded as URL-safe base64). `CREDENTIAL_ENCRYPTION_KEY` and backup keys must stay outside the database and backup archive. Install `pg_dump` for PostgreSQL. From the backend:

```bash
python backups.py --output /durable-backups/notochat-unique-timestamp.ncb
python backups.py --decrypt --input /durable-backups/notochat-unique-timestamp.ncb --output /private-restore/archive
```

Backup/decrypt output files are private and cannot overwrite an existing target. Truncation, tampering and reordering fail authentication. PostgreSQL decrypts to a custom archive for pg_restore; SQLite decrypts to an SQL snapshot. The tool does not execute restoration automatically.

Use `scripts/nightly-backup.sh` in your hosting scheduler with BACKUP_DIR, database/key environment and NOTOCHAT_PYTHON configured. Scheduling is not installed by the assistant. Run separate backups for separate auth databases and for each development SQLite tenant file. Offsite copy, retention, key rotation and a complete disaster-recovery drill still need deployment work.
