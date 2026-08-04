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