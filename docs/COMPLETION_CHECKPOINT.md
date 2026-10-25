# Completion checkpoint — 25 October 2026

## Original acceptance criteria

NotoChat is the chosen name for an online-business all-in-one messaging and sales app, based on the AIPraktor reference. The user requested Facebook, Instagram, WhatsApp and website conversations in one platform; natural AI customer replies and operator guidance; reference features implemented one by one; source in the existing `learninghasan/notochat` GitHub repository; and a usable Vercel deployment URL. They authorized continuing implementation and deployment, but no real customer outreach is used for tests.

The consolidated, original-scope completion inventory is [REFERENCE_COMPLETION_MATRIX.md](REFERENCE_COMPLETION_MATRIX.md). It distinguishes implemented local behavior, remaining recoverable product work, external dependencies and optional enhancements. This is not full feature parity or production readiness.

## Evidence reconciled

- Remote `main` was verified at `e93060296b87eedd39434b2195ac6ab6e01f0c6f`, matching the local tree before continuation.
- That commit had zero GitHub check runs; the repository had no workflow. Local tests/build previously passed, but no remote CI success existed. A two-job workflow is now supplied for Node tests/build, extension syntax, Python tests and disposable PostgreSQL concurrency/isolation tests. Its actual run outcome must be recorded separately.
- OAuth cleanup now removes expired one-time states and encrypted candidate tokens on the next authorization start, tenant-locally. Its regression test also protects active authorizations, unrelated records and another business’s pending selection. Scheduled deletion for inactive businesses remains pending.
- Chrome extension contracts and syntax are tested. Browser UI, actual Chrome extension permissions/side-panel behavior, PWA/push devices and live provider integrations are not verified. Available Browser tools were searched after reading the browser skill: no connected `js`, browser tab tools or supported CUA runtime is exposed. An installed Chromium binary does not establish a supported connected browser session; no shell/browser fallback was used.

## Read-only Vercel diagnosis

Target: team `team_eyrljOr7HqZrKlBhliQBzYcy`, named `learninghasan22-3359's projects`, slug `learninghasan22-3359s-projects`; desired project `notochat`.

- List teams/get team succeed for that team.
- List projects and deployments both succeed with empty results. There is no project ID or deployment URL to inspect.
- `GET /v2/user` through the same integration returns HTTP 404 `not_found`, `User not found`. Request ID: `sin1:sfo1::l99z9-1792939385957-569dd994e893`.
- Earlier progress recorded project creation/deployment HTTP 403. The original failure response/request ID is not retained in the repository; this continuation did not repeat writes. Therefore the exact original create/deploy endpoint payload and permission cause are uncertain. Read access to a team does not establish project-creation permission. No alternate account/CLI identity was used to bypass it.

User/operator-dependent: restore/verify the connected Vercel identity and write access for the exact team before retrying creation/deployment. Supply the hosted database, backend/worker, SMTP and approved provider configuration for live use. No live customer message, real payment, courier booking or new persistent credential was created during this continuation.

## GitHub access boundary

Reading commits, check runs and Actions run lists succeeds. Reading repository Actions settings via `GET /repos/learninghasan/notochat/actions/permissions` returns HTTP 403 `Resource not accessible by integration`. This prevents diagnosing settings through that integration; it does not prove workflows are disabled. Do not change accounts to evade the denial. Observe the workflow’s run after the authorized push and report its actual outcome.

## Continuation results

- Commit `6d5294ae23d659764b8b948f758844b5620d2500` was pushed to the existing repository. Its first remote [GitHub Actions run](https://github.com/learninghasan/notochat/actions/runs/40203620653) passed both jobs: 68 Python tests, 15 JavaScript tests, production build, extension syntax and disposable PostgreSQL isolation/concurrency checks. Repository settings access remains denied, but actual Actions execution is now verified.
- A real local Next.js development server and FastAPI gateway, with fresh disposable SQLite auth/tenant databases, passed `scripts/http-smoke.mjs`: signup, business creation, signed proxy, local support reply, order/stock/idempotency, export, second-business isolation, stale-business rejection and logout. No external providers or customer sends were used. This is HTTP integration verification, not browser interaction or production-host verification.
- The same HTTP smoke test is now part of the backend CI job. The test refuses non-local origins and requires `NOTOCHAT_DISPOSABLE_STACK=1`. Local testing requires fresh disposable auth/database paths, the same trust secret on frontend/backend, `BACKEND_URL`, a migrated auth schema and servers on ports 18030/18000. Never point this test at customer data.
- `next dev` generated `frontend/AGENTS.md`; it is retained as repository guidance. No production service or persistent provider credentials were provisioned.

## Product-gap continuation

[Scope evidence, behavior and limits](CART_PAGES_AND_MEDIA.md) records the original user quotations and the relevant reference text for all three pursued gaps.

- Multi-product manual/automatic text checkout is implemented with strict cart validation, quoted-price/stock locking, atomic reservation, specific verified-message confirmation, expired/superseded code rejection and idempotent concurrent/recovery behavior.
- Multiple same-app Meta pages retain distinct encrypted credentials. Recipient account determines ingestion/delivery, pause controls are independent, and member page/account scopes also protect histories, mutations and attachments.
- Signed image/audio attachment ingestion is implemented with encrypted source locations, bounded/restricted downloads, explicit/opt-in background analysis and review drafts. Unsupported formats and voice/image-confirmed autonomous checkout remain outside this increment’s completion claim.
- Aggregate local verification passed 105 Python tests, 18 JavaScript tests and production build. Disposable PostgreSQL checks exercise concurrent identical carts, page/settings mutations and media analysis claims in addition to previous isolation/concurrency coverage. All provider calls in these tests are mocked. Updated HTTP smoke/remote CI outcomes are reported with the pushed commit; no live provider or browser result is implied.
- No new scope/approval question was necessary for these local extensions. Vercel writes remain unattempted; real provider configuration/sends and supported browser/device verification retain the previously documented boundaries. Remaining product work is implementation work, not falsely attributed to those deployment/browser dependencies.


## Documents, media checkout and agent review continuation

Reference evidence: voice/image shopping and natural-language agent changes with old/new review, test and explicit publication are advertised by AIPraktor; the user requested the reference features one by one. Bounded document/video handling was also explicitly requested by the coordinator.

- Signed PDF/text and short-video attachments use resource-limited isolated parsing, fixed formats, restricted downloads and review-only output. Video samples three frames, excludes audio and requires system FFmpeg/FFprobe; PDF extraction rejects encryption and excessive pages. This is resource isolation, not a claim of a full OS container sandbox.
- Media cart suggestions are strict catalog-ID data. Operator-reviewed customer details and quote lead to a proposal, never an immediate order. Existing verified customer confirmation, expiry, quote/stock and duplicate protections finish the flow. Failed cart suggestions have explicit retry UI; no automatic retries hide additional AI usage.
- Natural-language agent changes produce a before/after diff without saving, changing automation flags/prices, publishing or sending. The editor and saved-version preview provide separate review steps; preview is simulated model output with no action tools.
- The consolidated matrix records all remaining original-scope local work at once, including comment reply transport, rich product messages/visual matching, automatic status/lead triggers, booking intake, waiting/response metrics and lifecycle cleanup. They are not external-access blockers.

Verification for this increment: 129 Python tests, 18 JavaScript tests, production Next.js build and disposable PostgreSQL isolation/concurrency checks passed locally. Signed document/video and media-cart provider calls are mocked; parser fixtures are synthetic real PDF/MP4 bytes. Real HTTP-stack checks will run again in remote CI after publication. Browser, live-provider and deployment verification remain unperformed.
