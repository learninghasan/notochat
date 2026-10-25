# NotoChat: current reference comparison

Reference reviewed: https://www.aipraktor.com/. Updated 25 October 2026. This document describes implemented behavior, not claims that live providers were tested. The consolidated original-scope inventory and remaining local work are in [REFERENCE_COMPLETION_MATRIX.md](REFERENCE_COMPLETION_MATRIX.md).

| Capability | Current implementation | Boundary / remaining verification |
|---|---|---|
| Business accounts | Better Auth signup/login, email verification/reset, organizations, verified invitations and membership revocation | Hosted auth database and SMTP delivery need configuration/live tests |
| Business isolation | Separate PostgreSQL schema per organization; separate SQLite files for development; signed/replay-protected API identities | Operational migrations, tenant deletion and key rotation are unfinished |
| Team access | Owner/admin mutation controls, channel and page/account allowlists, assigned-chat-only scopes enforced on request sessions | Explicit page scope applies to members; owners/admins retain business-wide access |
| Unified inbox | Conversation history, official Meta signed message/comment ingestion, isolated website chat sessions | Multiple same-app Facebook pages/linked Instagram accounts, encrypted per-page tokens, pause controls, account-specific delivery and signed image/audio ingestion implemented; approved app/live tests and comment/private-reply transport pending |
| Catalog | SKU, category, size, stock, price, description and HTTPS image URLs | Rich product carousels and visual catalog indexing pending |
| AI sales | Opt-in background intent classification with validated structured output; catalog-grounded price/stock/policy replies; language/tone variants | Requires actual provider/model and worker; replies are bounded templates rather than unrestricted model prose |
| Automatic checkout | Up to 10 distinct products per AI proposal; per-line quantities/prices, one delivery charge, exact verified text confirmation, atomic stock/quote checks, retries and stale-code rejection; manual multi-item form | Reviewed media-assisted proposals now require separate verified customer text confirmation; AI item extraction and language quality need live evaluation |
| Human handover | Complaints/refund keywords and uncertain intents hand over; reason, assignee user ID, notifications and timed return | Complaint recognition uses conservative keywords plus AI intent; refunds are never issued automatically |
| Voice / image analysis | Uploaded media plus signed Meta image/voice ingestion, encrypted temporary sources, bounded downloads and manual/opt-in background review drafts | Bounded selectable PDF/text and three-frame short-video review added; raw-media viewer, exact/perceptual indexing and measured Bengali quality pending; 3 attachments/message, 8 MB/file, 24-hour source validity |
| Orders / receipts | Stock reservation/restoration, transitions, JSON receipts and escaped printable invoice with browser Save as PDF | Branded server-rendered PDF and invoice email delivery pending |
| Courier | Explicit Steadfast and Pathao merchant booking, duplicate-attempt protection, authenticated status sync and webhook-triggered provider reconciliation | Contracts checked against published SDKs, not live merchant accounts; Pathao sandbox is default; live booking opt-in required |
| Leads | Six-stage pipeline, temperature, next-contact dates and AI lead extraction draft | Lead extraction still requires operator review/save |
| Bookings | Resource overlap checks, request/confirm/cancel/complete and reminder drafts | Explicit automatic reminder sending with fresh source/mode/window checks; draft preparation remains default |
| Knowledge | Text/Markdown/PDF extraction, keyword search, optional embedding indexing and cited semantic passages | Scanned PDF OCR pending; vector search currently uses bounded stored vectors, not a dedicated vector index |
| Agent desk | Language, tone, business rules, delivery/return policies; draft/publish/restore versions; draft/autoreply opt-ins | Natural-language text-only suggestions with old/new review and isolated version preview implemented; explicit save/publish remains required; preview is a model simulation |
| Follow-ups / broadcasts | Durable draft preparation or explicit automatic send; customer consent records; confirmed broadcasts; rechecks at execution; idempotent delivery and actual sent counters | Requires worker/live transport; templates outside the 23-hour window and consent collection UI for customers pending |
| Billing / recharge | SSLCommerz hosted recharge, server-side amount/currency/status/risk validation, duplicate-safe integer-paisa ledger, token-based charging, low-credit notification and resume of credit-blocked jobs | Store credentials, prices and live gateway tests required; sandbox balance cannot fund real AI; direct bKash/Nagad APIs not implemented |
| PWA / push | Manifest/icon, installable shell, offline fallback without customer-data caching, opt-in device subscriptions and worker-driven generic push | VAPID configuration and real device testing required; removed members' subscriptions need lifecycle cleanup |
| Chrome copilot | MV3 side panel, explicit app-origin access, signed-in account/organization binding, customer selection, summaries, drafts and selected-text questions | Source package ready; unpacked extension/browser verification and Chrome Web Store release pending; no automatic sending |
| Analytics | Record-derived ownership/order/lead/booking counts and provider token usage | Ownership is not AI-resolution rate; response-time metrics pending |
| Data / audit | Owner export excludes credentials/tokens; business-scoped audit of successful account mutations/exports | Audit sink failures are best effort; automated tenant/account deletion and retention jobs pending |
| Backups | Streaming authenticated encryption, SQLite snapshots, PostgreSQL custom archive backup, authenticated decryption and nightly scheduler script | Install scheduler/pg_dump and store backups durably/offsite; automatic restore verification and retention management pending |

## Verification

- Automated Python tests cover the business workflows, isolation, permissions, signed callbacks, credit and shipping idempotency, confirmation-gated sales, push payload privacy, PDF extraction, semantic retrieval, export and backup authentication.
- JavaScript tests cover real Better Auth handler flows, signed identities, browser-demo invariants and invoice escaping.
- Disposable PostgreSQL checks cover schema/channel isolation, concurrent stock/booking requests, concurrent payment callbacks, concurrent broadcast confirmation/worker delivery, account migrations/signup and encrypted backup archive round-trip.
- Real local HTTP verification covers signup, the signed frontend/backend proxy, support replies, order/stock/idempotency, export, business isolation, stale-business rejection and logout using disposable data. This does not verify browser UI.
- GitHub Actions runs frontend tests/build and backend tests/PostgreSQL checks; the first remote run passed.
- A production Next.js build passes. The current increment’s aggregate verification is recorded in COMPLETION_CHECKPOINT.md.
- **Not performed:** browser UI/device testing, live Meta/OpenAI/courier/payment/SMTP tests, deployment of the backend/worker/database or a verified live Vercel deployment.

Core code is considerably broader than the initial demo. This does **not** mean every capability advertised by the reference product is complete. Remaining items in the right column still need code or real-service setup as indicated.
