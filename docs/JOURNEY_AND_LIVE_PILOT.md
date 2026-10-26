# Journey lab and controlled live channel pilot

26 October 2026. Open the Render frontend → Explore NotoChat → Journey lab.
The 18 guided workflows use existing screens and preserve browser-local demo data.
Each step describes an action and expected result; opening a step is not recorded
as successful verification. Start a new sample conversation creates labelled
synthetic data only in demo mode. Fictional prices and quantities are not Peoniara facts.

## Verified deployment boundary

The Render frontend now connects to the free Render FastAPI service and dedicated
Neon `notochat` database. Workspace-token access works; multi-user email signup
still requires SMTP and auth database migration. Gemini reviewed drafts have been
live-tested using `gemini-3.1-flash-lite`. They do not automatically answer customer
conversations. Browser screenshots and click-through QA remain unavailable.

## Website live test

Explicit `PILOT_WEBSITE_CHAT=1` plus `WIDGET_ENABLED=1` permits website chat on the
free testing entrypoint. Other external-send and payment gates remain closed.
Open https://notochat-api.onrender.com/widget in a visitor tab. Start with a name
such as `TEST — website pilot`, send a message, and view it from the token-authenticated
workspace's Website inbox. Save a team reply in human mode and verify it appears
in the visitor tab. Visitor sessions cannot read each other's messages.

For Peoniara installation, a website administrator can embed:

```html
<iframe src="https://notochat-api.onrender.com/widget"
  title="Chat with our team" style="width:100%;max-width:420px;height:560px;border:0"
  loading="lazy"></iframe>
```

Set WIDGET_FRAME_ANCESTORS to the exact approved website origins, e.g.
`'self' https://peoniara.com https://www.peoniara.com`. This does not install the
widget on the website. Website admin access/installation is still required.
No admin token is embedded. Use test visitors first; the free service sleeps and
cannot promise continuous unattended replies. Website AI automation is not enabled.

## WhatsApp: current user has only the Business mobile app

Use the official Cloud API test number first. Do not migrate or unlink the existing
Peoniara mobile number. Meta app creation/terms, test-recipient verification and
provider credentials require the merchant's account access. Required configuration:
WhatsApp phone number ID, access token, Meta app secret, webhook verify token and
supported Graph version. Configure secrets in the backend/Connections, not chat.
Use the callback URL reported by Connections, subscribe to messages, and verify a
signed inbound event from the approved test recipient before enabling outbound.
The free entrypoint still blocks ENABLE_LIVE_SEND=1; a recipient-restricted outbound
pilot must be implemented and tested once the actual test account/recipient is known.
No real provider send has been made. Official API, not QR linked-device transport.
Messenger/Instagram require their own approved page/account permissions.

## Still not simulated as real functionality

Media parsing, provider delivery, push/Chrome device permissions, courier booking,
verified payments, automatic background jobs and authenticated team membership need
actual backend/provider/device setup. Journey lab explains these boundaries; it
must not fabricate successful sends, payments, AI calls, or live verification.
