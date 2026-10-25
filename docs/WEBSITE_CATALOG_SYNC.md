# Read-only website catalog sync

Peoniara public WooCommerce Store API was verified on 2026-10-25:
https://peoniara.com/wp-json/wc/store/v1/products?per_page=100&page=1
returned 60 listings (57 simple, 3 grouped). Pagination was separately checked.
The versioned frontend snapshot contains verified public product data, not the
synthetic demo inventory. Its capture time and source are displayed. It is always
marked stale in browser demo; no claim of live refresh or live inventory is made.

Tenant owner/admin selects the allowlisted source and manually syncs. Fixed HTTPS
origin/paths, no redirects or supplied arbitrary URL, 15-second request timeout,
4 MB per response, maximum ten pages/1,000 listings, one sync per minute.
All pages must validate before replacing the tenant snapshot; failure keeps the
last good snapshot and marks it stale. Stable source IDs prevent duplicate entries;
complete replacements reflect removed listings. No private/customer API is used.
HTML is converted to bounded plain text and rendered as React text, not HTML.
Images and canonical links are limited to the source site. Prices retain decimal
precision and source currency/minor units. Grouped IDs, variant IDs and attribute
labels are preserved when exposed. No hidden variation endpoint is assumed.

Website listings deliberately remain separate from local inventory: the existing
order engine requires numeric stock, while public API exposes only availability.
We never encode unknown stock as zero, unlimited, or an invented quantity. Public
listed availability, price, ID, image and descriptions can sync without credentials.
Stock quantity, reservations and address-specific shipping fees/timing are unknown.
A product recheck fetches the current public listing, returns no order, and explicitly
requires operator confirmation of quantities and delivery through the store.
The UI links to the canonical store page for its actual checkout. Imported listings
cannot silently enter the local order/stock pipeline. Merchant descriptions are
source text, not independently verified efficacy or suitability advice.

For native NotoChat checkout against store inventory, a separately approved scoped
WooCommerce integration and authoritative address-specific shipping/stock contract
are still needed. No credentials were created; no cart, order, payment, shipping,
stock or live website mutation was performed. Static schema shipping examples are
not installed as authoritative delivery rules. No periodic worker or keepalive is
added; live manual sync needs the hosted backend/database already pending setup.

UI: Website catalog navigation. Demo shows captured public listings; backend mode
provides configure/sync and individual listing recheck. Other white-label tenants
start unconfigured and do not inherit Peoniara snapshots. Additional stores require
explicit operator allowlist support rather than arbitrary URL fetching.
