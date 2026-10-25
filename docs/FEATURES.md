# NotoChat implementation map

Reference: https://www.aipraktor.com/ (reviewed 25 October 2026). Implementations are original; this is a functional comparison, not a copy of the reference brand or site.

## Completed in this increment

| Feature | Browser demo | FastAPI backend | External verification |
|---|---|---|---|
| Unified inbox: Messenger, Instagram, WhatsApp, comments, Website | Seeded sample conversations | Persisted conversation storage; signed Meta message/comment ingestion; website widget | Meta credentials and permissions required |
| Human handover, reason, assignment, timed return | Works on workspace reads | Works on workspace reads | Background timer worker not implemented |
| Persistent notifications and acknowledgement | Implemented | Implemented | Phone/web push not implemented |
| Catalog: SKU, category, descriptions, sizes, images, price, stock | Create/edit/search | Create/edit/search with unique non-empty SKU | Images are merchant-supplied HTTPS URLs |
| Order capture, totals, stock reservation | Implemented | Transactional stock checks; idempotent order requests | Courier and payment are not automatic |
| Order lifecycle & cancellation | Manual statuses, stock restoration | Locked transitions, stock restoration | Tracking references are manually recorded |
| Receipts | JSON download | Receipt endpoint | Branded PDF/invoice emails pending |
| Lead pipeline | Six stages, temperatures, next contact | Persisted lead upsert/update | AI extraction returns a reviewable draft, not an automatic save |
| Bookings | Conflict checks, confirm/cancel/complete | Overlap checks serialized on Postgres | Advance amounts and transaction IDs are unverified |
| Booking reminders | Drafts at 24h / 2h when in future | Same | Background execution/sending pending |
| Knowledge base | Text/Markdown import, save/search/delete | CRUD and Unicode keyword search | PDF ingestion, vector retrieval/embeddings pending |
| Agent rules | Language, tone, delivery, return/review settings | Same, server-side validation | Rules only affect connected assistant calls |
| Agent versions | Draft, publish, restore previous | Same | Natural language rule editing / test suite pending |
| AI copilot | Explicitly unavailable without provider | Customer summary, Q&A, reply draft, lead-extraction draft | OpenAI key and account-supported model required |
| Image recognition | Explicitly unavailable | Vision input plus catalog candidates, human review required | Model compatibility and matching accuracy need real tests |
| Voice transcription | Explicitly unavailable | Audio transcription; result shown for review | Transcription model and real Bengali audio tests required |
| Reply delivery | Browser-only persistence | Explicit text send for signed inbound Meta conversations; default disabled; duplicate-send guard | App permission review and live send/receipt tests pending |
| Follow-ups / reviews / delivery reminders | Draft scheduling, window eligibility | Same | Transport worker and platform opt-in/template requirements pending |
| Broadcasts | 23h audience preview, zero sent | Same | Batch delivery, consent and template handling pending |
| Analytics | Derived from saved records | Derived from saved records | Ownership is not an AI-resolution metric; payments not verified |
| Team directory | Profiles and intended channels | Profiles and intended channels | No invitations, individual login or role enforcement |
| Billing | No fabricated balance or charges | Actual provider token usage recorded; cost unknown | Credit ledger, pricing, top-ups and verified payment webhooks pending |
| Website widget | Dashboard preview data only | Real iframe chat; expiring isolated session tokens; admin token never exposed | Enable on a durable backend and configure allowed origins |

## Explicitly unfinished reference capabilities

1. Multi-business signup, tenant isolation, separate user accounts, invitation acceptance, owner/agent/channel permissions. Current backend is **one shared workspace** with an admin token.
2. Fully automatic AI sales agent: customer intent, product carousels, tool-based order creation with customer confirmation, automatic escalation, bounded autonomous actions and safety evaluation.
3. Image code/exact/perceptual matching pipeline and voice-to-validated-order flow.
4. Meta OAuth onboarding, multi-page token lifecycle, attachment download, comment replies/private replies, account health and delivery receipts.
5. Pathao/Steadfast courier booking and verified tracking webhooks.
6. Durable background jobs, retries, scheduling, daily encrypted backups and operational monitoring.
7. Verified bKash/Nagad/bank recharge, usage pricing, real credit ledger, low-balance email and billing-gated automatic processing.
8. Browser push, installable PWA and Meta Business Suite Chrome copilot extension.
9. PDF/document extraction, embeddings, semantic retrieval, catalog visual indexing and measured language-quality evaluations.
10. Data export/deletion controls, retention jobs, production migrations, audit trails, account recovery and encrypted credentials for multiple businesses.

These items are **not represented as completed just because a menu exists**. Missing credentials block external verification; the other items still require implementation. The UI labels unavailable functions and draft-only workflows accordingly.
