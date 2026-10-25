# Meta onboarding, customer outreach and Chrome copilot

Implemented 25 October 2026. Provider calls in tests are mocked; real Meta authorization and Chrome installation still need verification on the hosted application.

## Meta OAuth setup

1. Host the frontend and gateway on HTTPS. Configure the account database, SMTP, shared `INTERNAL_API_SECRET` and backend `CREDENTIAL_ENCRYPTION_KEY` first.
2. Backend: set `META_OAUTH_APP_ID`, `META_OAUTH_APP_SECRET`, `META_OAUTH_GRAPH_VERSION`, `META_OAUTH_VERIFY_TOKEN` and `PUBLIC_FRONTEND_URL` to the exact frontend origin. Frontend: `BETTER_AUTH_URL` must match that origin; set `BACKEND_URL` to the gateway.
3. In the Meta app, register the exact redirect `https://YOUR-FRONTEND/api/oauth/meta/callback` and webhook `https://YOUR-BACKEND/webhooks/meta`, using the configured verification token. Configure the required Facebook/Instagram messaging webhook fields in the app dashboard. Obtain approved permissions appropriate to your use: `pages_show_list`, `pages_messaging`, `pages_manage_metadata`, `pages_read_engagement`, `instagram_basic`, `instagram_manage_messages`. Availability depends on Meta app configuration, review and account eligibility.
4. As a business owner/admin, open Connections → Continue with Facebook. After returning, reopen your business and choose Connections → Load authorized pages → Connect selected page. Selection expires after 15 minutes. Repeat page selection to connect multiple Facebook pages and linked Instagram business accounts from the same Meta app. Previously selected pages remain connected.
5. Verify actual inbound events. Refresh encrypted connection settings before explicitly enabling live sending. OAuth selection keeps live sending disabled.

Authorization state expires in 10 minutes, is single-use, and is bound to the original account/business plus an HttpOnly browser cookie. Changing the active business interrupts completion. Candidate page tokens are encrypted and never returned to the browser. Shared-app account bindings are unique across businesses. The gateway validates the original webhook signature before routing; each workspace also validates the signature and recipient account.

WhatsApp still uses its configured official credentials; this flow does not implement WhatsApp Embedded Signup. App review, token expiry/revocation UX, account-transfer/release workflows remain operational/product follow-ups. Expired encrypted pending OAuth records are purged tenant-locally when an owner/admin starts a new authorization. A scheduled purge for inactive businesses is not installed. If OAuth is configured, the root `/webhooks/meta` belongs to the shared app; business-specific legacy/manual callbacks remain at `/business/ORGANIZATION_ID/webhooks/meta`.

## Follow-ups and broadcasts

- Record actual customer marketing opt-in under the conversation’s Marketing consent panel, including when/how it was obtained. Revocation blocks queued promotional messages.
- A reminder defaults to preparation for review. To send automatically, select the automatic-send checkbox when creating it and activate that reminder. A running worker is required.
- Follow-up/review messages require recorded consent. Booking/delivery reminders are treated as transactional. Choose the category accurately.
- Broadcast preview shows recent conversations, not a promise of delivery. Review the saved preview and type `SEND ELIGIBLE RECIPIENTS` to queue opted-in eligible recipients. Preview expires after 15 minutes.
- At both enqueue and execution, sending requires a verified supported source, AI mode, inbound within 23 hours, and an enabled transport for Meta channels. Local test messages cannot reopen the verified outreach window. Human takeover pauses automated delivery.
- The worker records actual delivery counts. Cancel pending jobs from Follow-ups. Repeated confirmation/retries reuse stable jobs and messages. Unconfirmed provider attempts require operator inspection rather than blind resend.
- Website delivery means the message was persisted to the authenticated visitor conversation; Meta delivery means the provider accepted it. Neither means the customer read it. Template messaging outside the window is not implemented.

Run `python worker.py` from `backend/` using the same database, encryption and provider configuration as the gateway. Use a supervised, persistent worker service; a one-off serverless invocation is not a scheduler.

## Chrome copilot installation

1. Open `chrome://extensions`, turn on Developer mode, choose Load unpacked, and select the repository’s `chrome-extension` folder. This is an unpacked source build, not a Chrome Web Store release.
2. Keep your hosted NotoChat tab signed in with the correct business selected. Click the extension icon to open its side panel.
3. Enter only your app origin, e.g. `https://your-project.vercel.app`. Approve access to that specific origin and connect the workspace.
4. Choose the matching customer. Request a summary, draft or answer. Optionally select customer text on the active page, click the extension icon on that page to grant temporary active-tab access, then choose Use selected text. Review that text and customer before asking AI.
5. Copy the answer only after reviewing it. The extension has no send-message, order or credential API capability.

Only the app origin persists in extension storage. Business IDs, chosen customer and output stay in the panel’s memory. Server signing keys, channel secrets and auth session tokens never enter the extension. Requests run as same-origin fetches in the explicitly chosen signed-in app tab and retain backend membership/channel restrictions. A business-context header prevents stale tabs from silently operating on a different active business. Connect again after switching business or closing/navigating the app tab.

Permissions: side panel UI, local origin preference, scripting for bounded API calls/explicit selected text, temporary active-tab access, and optional access to the app origin selected by the user. No background page scraping or remote script injection. Real Chrome UX/permission behavior still needs a browser check.

## Hosting status

The GitHub source is available. Vercel project creation/deployment previously returned HTTP 403 through the connected integration; a current project lookup still returns no `notochat` project. There is no verified live URL. Vercel deployment access must be fixed (or the repository imported from an authorized dashboard), and the backend/database/worker/SMTP/provider configuration must be supplied before real customers can use this system. No credentials belong in the public repository.
