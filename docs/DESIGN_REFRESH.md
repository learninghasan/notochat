# NotoChat workspace refresh

The October 25 design pass uses actual viewed Mobbin images as references, not
copied branding/assets. Primary references selected with the user:

- [Gorgias inbox](https://mobbin.com/screens/3dc49cfa-55d8-4bc7-9d95-b19b93451711): conversation list, broad central thread/composer, separate customer tools.
- [Plain threads](https://mobbin.com/screens/8e4cfdce-b787-4dc9-8618-19cf31ba5658): restrained backgrounds, compact navigation/rows and ample reading space.
- [Uvodo orders](https://mobbin.com/screens/b04dfcb1-2317-46d5-addd-2f04ccca1706): search above a quiet table and small status labels.

Additional inspected references were [Front](https://mobbin.com/screens/f445cb7a-fbdf-4fba-96c1-aaa0f8e24c59) and [Intercom](https://mobbin.com/screens/4bfa129c-0cf2-4185-bc90-1f1b4f583cb0). Gorgias and Plain remain the primary pair.

## Implemented

- Light grouped sidebar, consistent outline icons and teal/sage accent; explicit current page and keyboard focus.
- Overview shows real workspace counts and direct routes to existing tasks. No fabricated revenue/growth charts. Saved order value is labelled as unverified revenue.
- Inbox gives the thread more emphasis; compact filters, readable bubbles, loading text, bordered composer and collapsible customer tools.
- On small screens, menu expands on demand and inbox switches between list and conversation, with an explicit back button. Customer tools remain available below the thread.
- Order search across customer/phone/order/product, status filter and collapsed management actions preserve all existing actions and gates.
- Welcome screen prioritizes the browser-local demo. Account sign-in and legacy token entry remain under labelled disclosures.
- Removed repeated global KPI cards from unrelated work areas; overview/analytics retain the information.

## Verification and limitations

Frontend tests: 19 passed. Production build passed. No browser control/CUA tool
was available for desktop/mobile rendered screenshots or click-through testing.
Responsive rules and JSX were reviewed, but visual QA is not claimed. Any
AI-generated design preview must be labelled **design mockup, not implementation
screenshot**. The deployed demo remains browser-local; this pass does not enable
AI/providers, change tenant authentication, create secrets or provision databases.

Latest user direction: GoDaddy-inspired clean style. Actually viewed Mobbin
[GoDaddy conversations overview](https://mobbin.com/screens/cde6da18-2458-4ef9-8221-992bb995c84a)
and [GoDaddy dashboard](https://mobbin.com/screens/1ce6e490-de61-4b64-b7ca-052607481327).
Applied confident headings, pale navigation, restrained borders/no panel shadows,
and a crisp primary overview action. Retained Gorgias/Plain inbox structure and
tenant-configurable accent. No GoDaddy branding copied; no rendered visual QA claimed.
