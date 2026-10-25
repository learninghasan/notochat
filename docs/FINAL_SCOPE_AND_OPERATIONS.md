# Final bounded scope and operational prerequisites

The original seven-group inventory is fixed. This pass adds no unrelated features.

- **Rich catalog / visual search:** explicit team cards, automatic grounded product cards, category quick replies, Messenger/Instagram generic templates, WhatsApp interactive lists and website rendering. Selections remain inquiries. Uploaded JPEG/PNG/WebP catalog images are parsed in a resource-limited subprocess (4 MB, 16M pixels, no animation), indexed by canonical pixel hash, perceptual hash and color histogram. Top-three similarity suggestions are reviewed; AI vision receives candidate thumbnails when configured. No arbitrary image URL fetch or claim of semantic identity.
- **Customer language:** optional natural phrasing with immutable verified facts, conservative validators and fallback; [synthetic rubric](LANGUAGE_EVALUATION.md). Real model/native-human evaluation remains unperformed.
- **Delivery/rating:** an operator supplies the actual expected-delivery notification time and official courier tracking URL; no ETA is invented. Replaced plans, changed order state, overdue calendar day, human takeover, reply window and consent block stale work. Messenger/website use tracking buttons; WhatsApp/Instagram use supported clickable text links. Optional post-order RATE-code requests bind one rating to a verified customer/order; cancelled/expired and duplicate replies are handled. Defaults remain drafts unless explicitly enabled.
- **Native dot takeover:** signed, recent Messenger native page echo with text `.` and no API app_id pauses automation for one hour; customer dots and API echoes do not claim chats. The provider does not identify the particular staff account. WhatsApp linked-device/native echo parity remains dependent on the pending transport decision; no unofficial login added.
- **Low-credit email:** business opt-in, generic outbox, TLS SMTP, explicit `ENABLE_EMAIL_SEND=1`; no email was sent. Ambiguous SMTP outcomes are not blindly retried. SMTP_HOST/SMTP_PORT/SMTP_FROM/SMTP_USER (or SMTP_USERNAME)/SMTP_PASSWORD require operator configuration. Trial credits and service fees remain unconfigured pending user policy. Audio metering also requires an explicitly disclosed AI_AUDIO_PAISA_PER_MINUTE and provider-reported duration; missing duration/rate fails closed.
- **Resumable onboarding:** saved business profile/timezone, resume step, actual configuration checks and version-preview evidence. Configured is never labeled live-verified. Account, channel and rule actions retain their existing explicit flows.
- **Lifecycle:** owner request → expiring exact confirmation → recoverable quarantine. Processing pauses and conversations return to human mode. Owner can restore; no automatic purge exists. Offline `backend/qa/purge_workspace.py` defaults to no deletion, requires the exact known organization, seven-day recovery period, explicit confirmation and NOTOCHAT_ALLOW_PURGE=1 for execution. Only synthetic test databases were purged. Auth account removal and offsite backup disposition are separate operations requiring actual user authorization. Authentication member removal/leave revokes devices first, and rejoining clears the revocation through a signed server-only event. Authentication organization removal quarantines the workspace and cancels devices without permanent data deletion.

## Schema / backup operations

`backend/migrations.py` records current schema baseline version 1 and rejects missing required columns or a database newer than the code. The current pass changes JSON records rather than requiring destructive DDL. This is not a generic automatic migration/rollback generator: future schema changes require explicit versioned migrations and a backup. Existing disposable PostgreSQL/SQLite restore checks remain part of verification.

The nightly backup script now authenticates the completed archive without writing plaintext. Provisioning a durable/offsite destination, keys, scheduler and a production restore drill still requires hosting access. No infrastructure or credentials were created.

## External blockers — not additional local feature groups

- User reports Vercel import/deploy completed. Its URL/team has not yet been supplied. Current connector reads team `team_eyrljOr7HqZrKlBhliQBzYcy` but finds no NotoChat project/deployment; GET /v2/user still returns 404 User not found. Latest request ID: `sin1:sfo1::bm5v6-1792944991525-623cdc0902d5`. Earlier write403 was not retried. Need the user's exact project/live link and corrected connector identity/access, not guessed project changes.
- Supported browser-control tools are not exposed in this task. No browser, Chrome extension or PWA-device verification is claimed.
- Hosted backend/worker/database, SMTP/VAPID and approved Meta/AI/courier/payment configuration remain necessary. No real message, email, payment, booking or deletion has been used as a test.
- Decisions still pending: official WhatsApp API versus reference QR transport; trial credit/service-fee policy. Existing defaults remain unchanged.

## Remaining-work closure: explicit offer hook

`PAGE_CONNECT_TRIAL_PAISA`, `PAGE_CONNECT_TRIAL_POLICY_ID` and
`PAGE_CONNECT_TRIAL_SCOPE=workspace` jointly configure an optional trial offer.
All are unset by default. The amount is integer paisa; no public endpoint grants
credits. A successful authenticated Meta page subscription posts one tenant-scoped
ledger entry and wallet credit in the same transaction as connection persistence.
Concurrent connections, reconnects and changed policy IDs do not grant it twice.
Rollback leaves no credit. Existing connections do not receive a retroactive
background grant; a future successful connection is the eligible event if policy
is activated. The operator must approve the amount, scope and eligibility before
activation. The public billing response/UI discloses configured terms.

Usage ledger retries now acquire the wallet lock before the idempotency check,
preventing simultaneous repeated usage from charging twice on PostgreSQL.
Synthetic integration, rollback, tenant-isolation and real PostgreSQL concurrency
checks cover this behavior; no real monetary grant or provider connection occurred.

Service-fee economics remain a real code/policy blocker, not an unset numeric field:
choose fee basis, rate/amount, disclosure and refund behavior. WhatsApp QR transport
is also a real code/provider-choice blocker. Other bounded capabilities above are
not promoted to unsupported autonomous behavior. Render read-only discovery found
no PostgreSQL instances; database/secret provisioning requires approval. No paid or
expiring database has been created. Browser/extension/mobile visual QA remains blocked
by absent supported browser tools. See the matrix's current-status section.
