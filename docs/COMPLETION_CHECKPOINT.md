# Completion checkpoint — 25 October 2026

## Original acceptance criteria

NotoChat is the chosen name for an online-business all-in-one messaging and sales app, based on the AIPraktor reference. The user requested Facebook, Instagram, WhatsApp and website conversations in one platform; natural AI customer replies and operator guidance; reference features implemented one by one; source in the existing `learninghasan/notochat` GitHub repository; and a usable Vercel deployment URL. They authorized continuing implementation and deployment, but no real customer outreach is used for tests.

The actual feature-by-feature implementation and outstanding product work are in [FEATURES.md](FEATURES.md). This is not full feature parity or production readiness. In particular, multi-page support, attachment ingestion, rich product messages, multi-item/voice checkout, OCR, natural-language rule editing/test console, production migrations, retention/deletion and device-membership lifecycle still need work. Shipping the existing draft features does not resolve those gaps.

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
