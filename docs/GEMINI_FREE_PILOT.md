# Gemini free-tier pilot

The Gemini pilot is a separate reviewed text-draft workflow. Existing OpenAI
media, embeddings and agent workflows are not silently switched to Gemini.
No key was created and no live Gemini request was made during implementation.

1. In https://aistudio.google.com/ create/select a project eligible for free API
   usage and review its terms. Select a model currently included in its free tier.
   Model availability and quotas depend on the account; no model is assumed free.
2. After approving credential setup, place GEMINI_API_KEY in the backend secret
   environment, GEMINI_MODEL as the exact model ID (without models/ prefix), and
   GEMINI_PILOT_ENABLED=1. Do not place keys in chat, git, browser storage or
   NEXT_PUBLIC variables. Billing must remain unlinked for the intended free setup;
   the app cannot inspect Google billing status or guarantee zero cost on a paid project.
3. Deploy/connect the existing prepared backend with durable PostgreSQL and auth
   configuration. The current frontend-only Render demo cannot make Gemini calls.
4. In Website catalog, sync Peoniara; in Gemini pilot, enter a public/redacted test
   question and explicitly confirm its data scope. Review the draft before use.

The request contains only that question and selected public catalog fields, not
stored customer history, contact details, orders or private merchant knowledge.
Google's free-tier data terms may permit product improvement use; do not put real
customer personal data in this pilot. Free API quota does not provide 24/7 hosting.

Twenty attempts per tenant per UTC day and a ten-second cooldown are persisted
and serialized. Failed requests count toward the cap. A fixed Google HTTPS endpoint,
30-second timeout and 800 output-token bound apply. No tools, retries, customer
sends, purchases, credit deductions or paid fallback exist. Actual cost is unknown,
not falsely recorded as zero. Gemini 429 is reported as quota exhaustion.

Website In stock means listed available, not a count or reservation. The draft
receives the last sync timestamp, and instructions prohibit invented quantities,
shipping charges/dates and efficacy/suitability claims. Human review is required;
model instructions are not a guarantee of factual correctness. Delivery needs an
address-specific authoritative quote. Native checkout remains separately blocked.

Official references: https://ai.google.dev/gemini-api/docs/pricing and
https://ai.google.dev/gemini-api/docs/billing . Recheck eligibility in AI Studio at setup.
