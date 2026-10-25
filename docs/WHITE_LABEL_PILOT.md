# White-label NotoChat and Peoniara pilot

## Ownership and isolation

Existing account organizations map to isolated PostgreSQL schemas (development:
separate SQLite files). Signed server identities select the organization; names,
logos and public host headers do not grant access. Tenant owner/admin may edit
`/branding`, knowledge, rules, approval decisions and their own integrations.
Scoped members retain assigned/channel access; approval/reorder records follow
that scope. No reseller hierarchy or tenant-admin platform authority is introduced.

Platform operators alone configure verified host mappings, SMTP sender credentials,
pricing and deployment resources. There is no public API to change these. Existing
per-tenant integration credentials remain encrypted and excluded from exports.

## Branding

`/branding` persists business name, bounded uploaded raster logo, primary color,
widget greeting, receipt footer and requested domain in the tenant schema. White
text contrast must meet 4.5:1; invalid colors fail validation, default is #176b5b.
No remote logo fetch, SVG, scripts or HTML templates. Widget text/receipts are
escaped; logo bytes are size/dimension/type checked. Workspace shell, customer
widget, printable receipts and low-credit email use the business identity.
Account invitation text already uses the auth organization's identity. Password
reset/sign-in email is platform-account infrastructure, not a per-tenant sender.

Tenant domain requests are inert. After ownership/DNS/TLS verification, an operator
may set VERIFIED_TENANT_DOMAINS_JSON as a domain-to-org map. This routes public
widget paths to existing businesses and rejects mismatched business identities.
It does not provision DNS/certificates or implement arbitrary per-domain frontend
OAuth/cookie configuration. A full branded account frontend domain requires those
separate reviewed auth-origin settings; no domain is live-verified here.

SMTP_SENDER_VERIFIED=1 is an operator attestation after provider verification,
not automatic DNS validation. Both production account mail and low-credit mail
require it; tenants cannot override the sender domain. No email was sent.

## Five approved commerce improvements

1. Knowledge corrections: editable sources, evidence note and revision history;
   optimistic source hash prevents stale overwrites; semantic index invalidated
   on correction. Existing search uses the corrected source. This does not certify
   that merchant-entered information is true or all previously generated drafts
   are retrospectively correct; review remains required.
2. Approval inbox: typed discount/refund/unclear-order/policy proposals, automatic
   sales handover records, source-bound owner/admin decisions and retry protection.
   Source changes require a new proposal. Approval never executes money movement,
   changes a price or sends a customer reply.
3. Customer history/reorder: conversation-bound order history without sensitive
   beauty/health profiling. Idempotent draft exposes current price/availability;
   no stock reservation or order until a separate reviewed submission. UI requires
   customer confirmation; normal server stock/quote checks still apply.
4. Delivery rules: merchant-configured area, fee, minimum and offered slot labels;
   checkout selects supported values, and final orders/media quotes revalidate.
   Unknown policy has no fabricated default fee. Automated sales hands off when
   rules need area/slot review. Slots are descriptive windows, not capacity or
   courier reservations. No automatic ETA prediction.
5. Reporting: confirmed order value is distinct from unknown verified revenue;
   actual metered ledger cost is distinct from unmetered/unknown cost. Observed
   current quote/confirmation/expiry counts expose drop-offs without pretending
   to be a historical attributed conversion funnel or inferring intent.

## Peoniara pilot

Browser demo has a separate `notochat-peoniara-synthetic-v1` storage key; old demo
storage is preserved. Product/customer/order fixtures are synthetic. Prices/stock
are test values, not verified Peoniara catalog facts. No real customer imports,
store changes, provider links or outreach. No efficacy/medical/suitability claim.
Common health/suitability requests hand off; this is conservative keyword routing,
not a clinical classifier or a guarantee of complete medical detection.

Core backend has no PantaJol-specific configuration. New businesses use neutral
branding defaults; Peoniara exists only as a clearly labelled frontend fixture.
Actual catalog, shipping/returns policy, approved integrations, PostgreSQL/auth
setup and sender verification are needed for a real pilot. Free demo has no worker.

## Remaining decisions and verification

WhatsApp QR vs official API and service-fee economics remain explicit code/policy
blockers. Trial offer plumbing exists but amounts/eligibility stay unconfigured.
No new persistent credentials, paid/expiring database, DNS, TLS, customer sends or
financial actions have been provisioned. Browser/extension visual interaction QA
remains unavailable; automated tests and HTTP checks are not a substitute.

## Verification checkpoint — 2026-10-25

The white-label/Peoniara and five-improvement pass passed 183 Python tests,
21 frontend tests, the Next.js production build, disposable PostgreSQL
concurrency checks (including once-only trial/usage ledger writes), and the
local real-HTTP auth/organization/proxy/order/isolation smoke suite.
Provider actions remain mocked. No supported browser automation connection was
available for rendered visual or click-through QA. Public demo deployment is
frontend/browser-local simulation; these checks do not activate the API,
durable database, email, provider accounts, or continuous workers.
