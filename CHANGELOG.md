##### August 5, 2026
## Cart & Search Stability

### Fixed
- Cart add/remove using wrong product IDs — orchestrator now validates against actual cart contents before API call
- LLM showing stale cart from memory instead of real database state — post-tool reminder forces fresh data
- `BadRequestError` from missing tool responses — safety fallback guarantees every tool_call gets appended
- Checkout disabled in chatbot — directs users to `/checkout/` for address/payment
- Search missing products (saree, chiffon) — regex now searches name, category, description alongside $text
- Lexical search rewritten: $text + regex merged into one scored list before RRF ranking
- Vector search pool now includes lexical matches, not just random 300 products

### Added
- `cart_product_ids` tracking in orchestrator — persists across conversation rounds
- Safety fallback: `api_response_data` never `None` before tool response append

### Changed
- Cart prompt rules consolidated: add/view/update/remove/checkout with explicit disambiguation
- `manage_cart` added to `PRODUCT_ID_TOOLS` and `AUTH_REQUIRED_TOOLS`
- 10 inactive saree products activated in database

## Summary
Complete test suite for cart management API endpoints

## Changes
- ✅ 8 passing tests (100% pass rate)
- 🔧 Fixed response format handling
- 🗄️ Using real database products for testing
- 🧹 Automatic test data cleanup

## Test Coverage
- [x] Add to cart
- [x] View cart
- [x] Update quantity
- [x] Remove items
- [x] Empty cart
- [x] Invalid products
- [x] Multiple products
- [x] Checkout disabled

##### August 4, 2026

### Admin Dashboard - Phase 2

### New Features

#### Product Performance Analysis
- Endpoint: `GET /admin/product-performance?product_name=...`
- Analyzes sales, reviews, pricing, and category averages
- Explains why a product is or isn't selling well

#### Inventory Alerts
- Endpoint: `GET /admin/inventory-alerts`
- Shows out-of-stock, low-stock, and at-risk products
- Calculates estimated days of stock left based on sales velocity

#### Pending Tickets Summary
- Endpoint: `GET /admin/tickets-summary`
- Shows urgent tickets, oldest unanswered, and unassigned tickets
- Includes user contact info (name + email) for follow-up

#### Order Status Breakdown
- Endpoint: `GET /admin/order-status-breakdown`
- Shows order counts by status with flexible date ranges
- Includes actual stuck order details with customer names

### Fixes
- Normalized ticket statuses (`in_progress` → `under review`)
- Normalized order statuses for consistent casing
- Fixed `get_top_selling_products` date range bug ($lt was missing)
- Backfilled OrderItems from embedded orders data
- Added user info to ticket summary responses
- Enforced minimum 3 products in top products response

### Tests
- 5/5 pytest tests passing for admin analytics
- Cross-verified all metrics against MongoDB