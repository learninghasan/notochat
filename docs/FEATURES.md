# NotoChat: current reference comparison

Reference reviewed: https://www.aipraktor.com/. Updated 25 October 2026. This document describes implemented behavior, not claims that live providers were tested.

| Capability | Current implementation | Boundary / remaining verification |
|---|---|---|
| Business accounts | Better Auth signup/login, email verification/reset, organizations, verified invitations and membership revocation | Hosted auth database and SMTP delivery need configuration/live tests |
| Business isolation | Separate PostgreSQL schema per organization; separate SQLite files for development; signed/replay-protected API identities | Operational migrations, tenant deletion and key rotation are unfinished |
| Team access | Owner/admin mutation controls, channel allowlists, assigned-chat-only scopes enforced on request sessions | Policies apply to channels, not multiple individual pages within a channel |
| Unified inbox | Conversation history, official Meta signed message/comment ingestion, isolated website chat sessions | OAuth onboarding, multi-page management, attachment download and comment/private-reply transport pending |
| Catalog | SKU, category, size, stock, price, description and HTTPS image URLs | Rich product carousels and visual catalog indexing pending |
| AI sales | Opt-in background intent classification with validated structured output; catalog-grounded price/stock/policy replies; language/tone variants | Requires actual provider/model and worker; replies are bounded templates rather than unrestricted model prose |
| Automatic checkout | One-item order proposal, displayed total/address, expiring confirmation code, exact customer confirmation, stock/price recheck and idempotent order creation | Multiple-item autonomous checkout and voice-to-confirmed-order flow pending |
| Human handover | Complaints/refund keywords and uncertain intents hand over; reason, assignee user ID, notifications and timed return | Complaint recognition uses conservative keywords plus AI intent; refunds are never issued automatically |
| Voice / image analysis | Uploaded voice transcription and image/catalog candidate analysis via configured AI provider | Automatic Meta attachment processing, exact/perceptual image indexing and measured Bengali quality pending |
| Orders / receipts | Stock reservation/restoration, transitions, JSON receipts and escaped printable invoice with browser Save as PDF | Branded server-rendered PDF and invoice email delivery pending |
| Courier | Explicit Steadfast and Pathao merchant booking, duplicate-attempt protection, authenticated status sync and webhook-triggered provider reconciliation | Contracts checked against published SDKs, not live merchant accounts; Pathao sandbox is default; live booking opt-in required |
| Leads | Six-stage pipeline, temperature, next-contact dates and AI lead extraction draft | Lead extraction still requires operator review/save |
| Bookings | Resource overlap checks, request/confirm/cancel/complete and reminder drafts | Automatic reminder sending is not implemented |
| Knowledge | Text/Markdown/PDF extraction, keyword search, optional embedding indexing and cited semantic passages | Scanned PDF OCR pending; vector search currently uses bounded stored vectors, not a dedicated vector index |
| Agent desk | Language, tone, business rules, delivery/return policies; draft/publish/restore versions; draft/autoreply opt-ins | Natural-language rule editing and a dedicated agent test console pending |
| Follow-ups / broadcasts | Durable reminder preparation, execution-time reply-window checks, recent-audience broadcast preview | Customer-facing automatic follow-up/review/broadcast sending and consent/template management pending |
| Billing / recharge | SSLCommerz hosted recharge, server-side amount/currency/status/risk validation, duplicate-safe integer-paisa ledger, token-based charging, low-credit notification and resume of credit-blocked jobs | Store credentials, prices and live gateway tests required; sandbox balance cannot fund real AI; direct bKash/Nagad APIs not implemented |
| PWA / push | Manifest/icon, installable shell, offline fallback without customer-data caching, opt-in device subscriptions and worker-driven generic push | VAPID configuration and real device testing required; removed members' subscriptions need lifecycle cleanup; Chrome copilot extension pending |
| Analytics | Record-derived ownership/order/lead/booking counts and provider token usage | Ownership is not AI-resolution rate; response-time metrics pending |
| Data / audit | Owner export excludes credentials/tokens; business-scoped audit of successful account mutations/exports | Audit sink failures are best effort; automated tenant/account deletion and retention jobs pending |
| Backups | Streaming authenticated encryption, SQLite snapshots, PostgreSQL custom archive backup, authenticated decryption and nightly scheduler script | Install scheduler/pg_dump and store backups durably/offsite; automatic restore verification and retention management pending |

## Verification

- Automated Python tests cover the business workflows, isolation, permissions, signed callbacks, credit and shipping idempotency, confirmation-gated sales, push payload privacy, PDF extraction, semantic retrieval, export and backup authentication.
- JavaScript tests cover real Better Auth handler flows, signed identities, browser-demo invariants and invoice escaping.
- Disposable PostgreSQL checks cover schema/channel isolation, concurrent stock/booking requests, concurrent payment callbacks, account migrations/signup and encrypted backup archive round-trip.
- A production Next.js build passes.
- **Not performed:** browser UI/device testing, live Meta/OpenAI/courier/payment/SMTP tests, deployment of the backend/worker/database or a verified live Vercel deployment.

Core code is considerably broader than the initial demo. This does **not** mean every capability advertised by the reference product is complete. Remaining items in the right column still need code or real-service setup as indicated.
