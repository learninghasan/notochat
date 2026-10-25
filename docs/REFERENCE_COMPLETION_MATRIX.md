# Reference completion inventory — 25 October 2026

Scope evidence: user “সবগুলোর … মেসেজ আসবে একটা প্ল্যাটফর্মে”, “এবং সেলস”, “ওটার মতো … প্রোডাক্ট বানাতে”, and “amader j example diyechi setar sob kichu poneby one implement koro”; reference https://www.aipraktor.com/ reviewed as a whole. GitHub publication and a usable Vercel URL are explicit acceptance criteria. This is the consolidated inventory, not a claim of parity.

**Done locally** means implemented and covered by local automated verification, not live-provider or browser verification. **Partial** means recoverable implementation remains; deployment access does not block it. **Blocked** identifies an actual external dependency or product decision. No customer sends, live charges or courier bookings are used as tests.

| Original/reference capability | Status | Implementation and exact remaining boundary |
|---|---|---|
| Unified Facebook/Instagram/WhatsApp/website inbox, history | Done locally / live blocked | Signed official Meta adapters, isolated widget sessions, multi-page credentials and member page scopes. Approved app/accounts, hosted backend and browser verification needed. |
| Facebook public comment and private replies | Done locally / live blocked | Explicit public/private reply endpoints and UI bind replies to signed comment evidence; one private reply per comment, conservative seven-day limit, ambiguous outcomes never blindly retried. Provider permissions/live contracts still need verification. |
| Reference WhatsApp QR linked-device connection | Blocked decision | Current implementation uses official WhatsApp Business API. Reference explicitly advertises QR personal/Business linked-device mode. Transport choice and supported provider are required before changing authentication architecture; no unofficial session credential collection added. |
| Natural Bengali/English/Banglish sales replies | Partial | Structured intent, catalog-grounded templates and assistant drafts exist. Production replies are bounded templates; fluent natural-response evaluation/provider tuning remains. |
| Product categories/buttons/carousels, code matching | Partial | Category/SKU catalog and text matches exist; rich channel product messages/buttons remain. |
| Exact-image/visual match, uncertain top three | Partial | Review-only image model sees textual catalog, not a stored visual image index. Exact/perceptual matching and image catalog retrieval remain. |
| Text/voice/image sales checkout, multiple items | Done locally with confirmation boundary | Signed media analysis → validated suggested cart → operator-reviewed quote → separate verified customer text confirmation. Current price/stock revalidated atomically; failed/repeated flows protected. No irreversible order solely from model interpretation. |
| Document/video attachments | Done locally, bounded extension | Reference supports PDF knowledge; coordinator explicitly requested documents/video robustness. Signed PDF/text review and three sampled video frames, no audio. PDF≤5MB/50pages, text≤100KB, video≤8MB/60s/1080p. No claim of complete video understanding. |
| Orders, stock, receipts, advance transaction record | Done locally | Multiple products, COD confirmation, manual payment references remain unverified; printable receipt. Real payment status must use provider verification. |
| Courier booking, shipment/delivery-day tracking updates | Partial | Explicit merchant booking and authenticated status sync exist. Shipment and delivered-review source-bound drafts/opt-in jobs now trigger on status changes. Delivery-day scheduling and tracking buttons remain. Merchant setup/live verification blocked. |
| Post-order rating and post-delivery review link | Partial | Delivered-order review-link drafts/opt-in jobs now trigger automatically. Separate post-order rating collection remains. |
| Hot/warm lead follow-up within reply window | Done locally | Configurable Hot/Warm selection creates one source-bound follow-up (1h Hot, 4h Warm) inside the reply window. Draft default, explicit published automatic opt-in; changed lead/customer source, consent, human takeover and disabled opt-in block stale delivery. |
| Human handover reasons, timers, one-tap claim, longest waiting | Partial | Handover/assignee/timer/return implemented. Observed verified waiting-time prioritization is implemented; native-channel staff “.” takeover remains. Echo authenticity/account matching must be validated before treating any event as staff takeover. |
| Push/dashboard/Chrome copilot | Done locally / browser blocked | Notifications, scoped push subscriptions, MV3 side panel, summaries/drafts/questions and media context. Connected browser/device tests unavailable; membership subscription cleanup remains operational work. |
| Lead extraction/history and six-stage pipeline | Done locally | Reviewed extraction and pipeline; no unreviewed model write. |
| Configurable booking intake, owner confirmation, advance, reminders | Done locally | Manual booking, resource conflict checks, owner confirmation and 24h/2h reminder drafts/explicit delivery exist. Configurable deterministic BOOK flow asks service/name/future timezone-qualified time/custom questions, then requires REQUEST code and owner/admin confirmation. No arbitrary natural-language date interpretation or payment verification is claimed. |
| Knowledge text/PDF, hybrid semantic/keyword retrieval | Done locally | Bounded selectable PDF and optional embedding retrieval implemented. Provider quality/live evaluation blocked. Scanned OCR is an optional enhancement, not a separate advertised acceptance criterion. |
| Natural-language agent edits, old/new review, test, publish/restore | Done locally | New proposed text-only edits cannot enable automation or change prices. Diff → editor → explicit version save/publish. Isolated model preview creates no customer messages/orders. Preview is a simulation, not the real production sales pipeline. |
| Team membership/page/assigned access | Done locally | Signed organization role enforcement and request-level data scopes. Invitations/SMTP and browser end-to-end verification blocked by setup. |
| AI handling and human response-time reporting | Done locally | Measured human response-time mean/sample count, AI-handled turn percentage and oldest pending turn. Only timestamped verified inbound and confirmed replies count; local tests/drafts/unknown historical timestamps excluded. Resolution is not inferred. |
| Usage credit, recharge, low-credit email, pause/resume | Partial / policy blocked | Integer-paisa usage/verified hosted recharge/notifications and resume exist. Low-credit email remains. Free page-connect credit amount and service fee economics need operator policy; no monetary grant invented. Direct bKash/Nagad APIs are not required if approved hosted checkout supplies advertised methods. |
| Resumable guided onboarding, test then live | Partial | Auth, business/org and connections screens exist; unified resumable progress checklist remains. |
| Encrypted credentials/backups, pause preserves data, deletion | Partial / hosting blocked | Encryption, encrypted backup/restore utilities and scheduler script exist. Durable offsite scheduler provisioning blocked. Requested tenant deletion, membership cleanup and migration lifecycle remain code/operations work. |
| No marketing trackers | Done locally | No marketing trackers introduced. Necessary authentication cookies remain; reference's literal “no cookies” cannot be applied to this auth design. |
| GitHub source and usable Vercel deployment | Partial / access blocked | Main through bc664d2 passed remote CI (129 Python/18 JavaScript tests, build, PostgreSQL and HTTP stack); subsequent increment reports its own commit/CI in the checkpoint. Vercel team reads succeed but no projects exist; earlier write403 and current identity404 remain unresolved. No live URL. |

## Not separate original requirements

Chrome Web Store publication, branded server-generated/email invoices, arbitrary-format OCR, dedicated vector database, and retention-policy design are optional enhancements unless explicitly requested. They must not inflate the completion criteria. Video/audio transcription beyond the bounded support above is also not claimed.

## Current external blockers

1. Vercel connected identity/write permission for team `team_eyrljOr7HqZrKlBhliQBzYcy`; no write retries or alternate identity bypass.
2. Approved hosted database/backend/worker, SMTP and provider configuration for real operation. Synthetic fixtures/mocked services verify contracts only.
3. Supported connected-browser tooling for Chrome/PWA/UI verification; installed Chromium alone is not authorized browser control.
4. Product decisions: official WhatsApp API versus reference QR transport; trial-credit and service-fee policy. These do not block unrelated local implementation above.


## Exact reference evidence for the latest in-progress work

- Reporting: “Analytics অ্যানালিটিক্স AI কতটা সামলাল, টিম কত দ্রুত উত্তর দিল”. This authorizes observed handling/response-time reporting; it does not justify fabricated resolution statistics.
- Follow-up: “মেটার ২৪ ঘণ্টার নিয়মের ভেতরেই সুন্দর করে একবার মনে করিয়ে দেয়। কাদের মনে করাবে — হট না ওয়ার্ম — সেটা আপনি বেছে নেন।” Configurable target temperatures and bounded one-time reminders directly implement this.
- Shipment/review: “পার্সেল কুরিয়ারে দিলে, ডেলিভারির দিন সকালে — প্রতিটা আপডেট নিজে থেকেই চ্যাটে চলে যায়, ট্র্যাক করার বাটনসহ”; “ডেলিভারি → ধন্যবাদ → রিভিউ লিংক”. Only shipment/review source triggers are closed here; delivery-day prediction/buttons and separate rating intake are still partial.
- Booking: reference advertises service-business booking intake, configurable questions, request → owner confirmation and reminders. The implementation uses deterministic questions and explicit timezone input rather than claiming model date understanding.

## Finite remaining original-scope implementation after this increment

1. Rich category/product buttons/carousels and exact/perceptual/visual catalog matching.
2. More natural production customer-response generation and measured Bengali/Banglish quality; current grounded templates remain deliberate limits.
3. Delivery-day courier notifications/tracking buttons and post-order rating collection.
4. Native-channel staff “.” takeover (authenticated outbound echo support must be verified; current WhatsApp transport differs from the reference).
5. Low-credit email delivery logic; configurable trial-credit/service-fee behavior after the stated business policy decision.
6. Unified resumable onboarding/test/live checklist.
7. Requested tenant deletion, member-device cleanup and production schema-migration/backup lifecycle work. Real destructive deletion or infrastructure changes need their own concrete approval; implementing/testing those controls with disposable data does not.

No item above is automatically blocked by Vercel or browser access. Optional enhancements are excluded as described earlier. Live/provider/browser verification and the explicit WhatsApp/economics decisions remain a separate list.
