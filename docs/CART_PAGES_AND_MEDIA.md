# Multi-product checkout, multiple pages and received media

This increment stays within the original online-business messaging/sales app. It does not introduce a new provider or perform live customer outreach.

## Requirement evidence and scope

The user’s exact short instructions included “সবগুলোর … মেসেজ আসবে একটা প্ল্যাটফর্মে”, “এবং সেলস”, “ওটার মতো … প্রোডাক্ট বানাতে” and “amader j example diyechi setar sob kichu poneby one implement koro”. They supplied https://www.aipraktor.com/ as the reference.

- **Multi-item checkout:** implements the existing sales/order requirement for multiple catalog products. The user did not literally say “multi-item”; this is a bounded extension of the already-authorized checkout, not a claim of a separate explicit request. It retains COD and exact text confirmation, and adds no payment or autonomous courier action.
- **Multiple pages and page permissions:** implements the existing unified messaging requirement. The reference retrieved on 25 October 2026 states “কে কোন পেজ দেখবে, সেটা আপনি ঠিক করেন।” This increment adds pages within the same business and Meta app, plus member account scopes; it does not add new messaging services or cross-business sharing.
- **Attachments:** implements the referenced inbox/AI scope. The same reference states “Messenger পেজের ইনবক্স: লেখা, ছবি, ভয়েস, বাটন” and “ছবি দেখে প্রোডাক্ট চেনা”. This increment ingests supported images/audio and prepares reviewable AI analysis. It deliberately does not claim the reference’s voice-confirmed autonomous checkout is complete.

None of these local code changes needs new account credentials or approval. **Technical/live dependencies** remain: approved Meta permissions, configured AI models/credit/worker, actual provider-media format checks and supported browser/device access. Vercel access denial/uncertainty is separate from implementation and was not retried. No real provider sends were used as tests.

## Checkout behavior

Manual Create order now has add/remove product lines, independent quantities and a displayed products subtotal. Prices are bound to the submitted quote and rechecked by the backend, not trusted from client input. The backend reserves all lines or none. Repeated identical requests, including concurrent requests waiting for stock locks, return the same order without reserving twice.

Automatic sales uses strict structured cart lines for up to 10 distinct products, at most 100 units per product. Duplicate lines merge. Unknown products, invalid quantities and extra model fields cannot create an order. The customer sees each line’s unit price/quantity/line total, address, total and one delivery charge before `CONFIRM CODE`. Confirmation requires the specific message to have verified widget/webhook provenance; authenticated local test messages cannot impersonate customer confirmation. Existing historical jobs without that provenance fail closed.

A new non-confirmation customer message supersedes a pending summary. Wrong, expired and superseded codes do not create orders. Confirmation rechecks prices under product locks. If price/stock changed, no line is reserved and the team takes over. Recovery after an order commit but before its response receipt reuses that order; confirming a cancelled order reports its recorded state instead of creating another. Previously issued single-product summaries remain readable.

## Multiple Meta pages

Each OAuth page selection adds/reconnects that page while retaining other pages and their encrypted tokens. Page selections remain available until the 15-minute authorization expires. Repeated selection is idempotent. Connecting a page disables the business-wide live-send switch until explicitly enabled again. Mixing different Meta apps is rejected instead of silently overwriting an existing app’s connection.

Webhook account identity separates conversations and deduplication. Outgoing text resolves the token from the conversation’s original page/account, not the last selected page. Pause in Connections stops inbound ingestion and outbound/automated delivery for that page and its linked Instagram account; other enabled pages are unaffected. Pausing retains the business ownership binding and credentials. Releasing/transferring an account remains unimplemented.

Team → member policy supports channel, explicit page/account IDs and assigned-only intersection. Blank account restriction disabled means all accounts in allowed channels; restriction enabled with no IDs blocks external-account chats. Website access follows its channel checkbox. Owners/admins retain full business access. Scope covers histories, mutations, orders, attachments and drafts; account IDs cannot expose another tenant.

## Received image/audio handling

Signed Messenger/Instagram and WhatsApp image/audio references appear in the conversation’s Received attachments section. Up to 3 references per message are retained. Source URLs/media IDs are encrypted and never returned by workspace/export APIs. Configure credential encryption before receiving attachments; unavailable sources need a new customer message after setup.

Choose Analyze attachment to queue a review, or publish **Received image and voice analysis** in Agent desk to opt into background analysis in AI mode. Text auto-reply alone does not opt into media analysis. Attachment messages cannot enter automatic sales checkout. Human takeover stops queued automatic analysis; operators may explicitly analyze for review in human mode.

Downloads use bounded streaming (8 MB), HTTPS Meta-owned hosts, no redirects, MIME/file-signature validation and WhatsApp SHA-256 integrity checks when supplied. WhatsApp media metadata is obtained using the conversation’s configured account token; that token is sent only to the fixed Graph endpoint and approved WhatsApp download host. Image/voice content is sent only to the configured AI analysis provider. No binary file is persisted. Audio analysis remains unavailable when metering is enabled without supported audio pricing.

Results are stored as assistant drafts, never as sent customer replies or orders. Duplicate jobs share an atomic attempt claim. Failed/interrupted analysis requires explicit retry, which may incur AI usage again; repeated background polling does not retry an ambiguous provider attempt. Media references expire after 24 hours; successful analysis deletes the encrypted source, and new inbound events purge expired sources. A scheduled purge for inactive businesses is still pending.

Unsupported documents/video or expired media require the original channel/customer resend. The feature is not a raw-media viewer, exact visual search, OCR, automatic voice reply or voice-confirmed checkout.

## Verification boundaries

Regression tests use mocked provider responses and synthetic customer data. Aggregate Python/JavaScript tests and the frontend production build are required, along with disposable PostgreSQL checks for concurrent cart requests, encrypted page/settings updates and media-job claims. The existing real local HTTP CI smoke flow now creates a multi-product order and rejects a changed quote without partially reserving inventory.

Live Meta authorization/media URLs, actual model accuracy (including Bengali voice), browser interaction and production deployment remain unverified. Those are genuine technical/configuration dependencies; they are not reasons to stop unrelated local implementation.
