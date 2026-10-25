# Synthetic language and safety evaluation

Scope: the original reference promises natural Bangla/English/Banglish replies. Optional `natural_replies` adds a separately metered structured-output phrasing call for greeting, product/catalog, delivery and return-policy inquiries. It is off by default. Checkout summaries/confirmation codes and booking requests remain deterministic.

The model receives the customer text as untrusted data and a server-built fact block. The exact fact block remains visible beneath accepted prose. Numeric additions, unprovided URLs, unsupported free/guarantee promises and common English/Bangla/Banglish completed-action claims are rejected; the original factual answer is the fallback. Current catalog values are reread after intent extraction and checked again after phrasing. These checks reduce risk; they are **not a proof that arbitrary model prose is factually correct**.

The synthetic rubric in `backend/test_language_rubric.py` checks:

1. Bangla, English and Banglish fixtures preserve actual price/product facts through the complete verified widget → queued sales response path.
2. Numeric normalization handles Bangla digits without permitting an invented price.
3. Invented payment URLs, free-delivery promises and completed-order claims fail validation.
4. Phrasing alone creates no orders; validated catalog cards retain the authoritative facts.

Fixtures and provider responses are synthetic/mocked. Passing this rubric establishes code-path and specified guard behavior, **not native-human review, fluency scoring, live OpenAI quality, or a hallucination-free guarantee**. Before enabling it for real customers, evaluate approved representative examples with the configured provider and a native Bengali reviewer. No live provider call or customer data was used here.
