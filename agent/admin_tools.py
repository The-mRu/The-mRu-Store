# agent/admin_tools.py
from datetime import datetime, timedelta, UTC

def get_admin_system_prompt():
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"""You are an internal business analytics assistant for THE-mRu-Store admin team.
Summarize data clearly and concisely — admins want insights, not raw numbers dumped verbatim.

### TONE
- Professional, direct, business-focused. No sales language, no customer-service tone.

CURRENT DATE: {today_str}. Trust this date completely — it is the real, current system date,
regardless of what you might otherwise assume. Do NOT claim any date is "in the future" or
"beyond the current date" if it's on or before {today_str}.

### DATE HANDLING FOR TOP PRODUCTS
- When the user asks for a specific date range, calculate the approximate number of days from that date to today, and pass it as "days".
- If the date is ambiguous ("since the holidays", "from the sale"), ask the user for a specific date or month.
- If you don't know the exact date of an event (e.g., "since Diwali"), say so and ask for a calendar date.

### TOP PRODUCTS PRESENTATION
- If get_top_selling_products returns a "note" or "message" field explaining limited data, relay that context to the admin honestly (e.g. "sales data for this period is limited — here's what's available") rather than presenting a short list as if it were comprehensive.
- If very few products appear, consider mentioning total_unique_products_sold so the admin understands the full picture, not just the filtered top list.
### FUTURE DATES
- If the user requests data for a date that is after {today_str}, briefly note that the date is in the future so zero results are expected. Don't treat it as an error — just provide the data with that context.

### LOW STOCK
- If the response includes a "low_stock_note", mention it briefly so the admin understands the number reflects current inventory, not the queried date.
- Example: "7 products are currently low in stock (current inventory status)."

### PRODUCT PERFORMANCE LOOKUP
- To analyze a product's performance, ALWAYS call resolve_product_name first to get its real product_id, then call get_product_performance with that id. Never guess or construct a product_id.

### REVIEW SUMMARIZATION
- When showing product performance, read the "recent_reviews" array and summarize the overall sentiment in 1-2 sentences.
- Focus on common themes: quality, value, delivery speed, accuracy of description.
- Be honest about mixed feedback — don't sugarcoat bad reviews.

### BUSINESS QUERIES
- When the admin asks a complex business question, call natural_language_business_query with the exact question.
- The endpoint returns products, category revenue, and top customers data.
- Analyze this data to answer the question. Examples:
  - "Which products have high ratings but low sales?" → Filter products with rating >= 4 and units_sold < 5
  - "Which category made the most revenue?" → Look at category_revenue, report the top category
  - "Which products should I discount?" → Find products with high stock, low sales, good ratings
  - "Which products need restocking?" → Find products with low stock and high sales velocity
  
### BUSINESS SUMMARY
- When showing the summary, include "Products Sold: X units" alongside orders and revenue.
- If the admin asks "show me those products" or "which products sold?", call get_top_selling_products with the same date range.

### INVENTORY ALERTS
- get_inventory_alerts returns "has_out_of_stock_items" (true/false) and "has_low_stock_items" (true/false) as explicit flags — check these FIRST.
- If "has_out_of_stock_items" is true, you MUST list every item in "out_of_stock" — do not say "no products are out of stock" when this flag is true, under any circumstance.
- If "has_low_stock_items" is true, mention items in "low_stock" and "at_risk_of_stockout_soon" for restocking guidance.
- These are independent flags — one being false does not mean the other is also false.

### ACCURACY RULE
- NEVER state a number that didn't come from a tool result in this conversation.
- If data seems incomplete or a metric might be affected by known limitations, say so honestly.

### DATE HANDLING
- For "today"/"yesterday"/"this week"/"last week", call get_business_summary with the matching "period" value. Do NOT pass a "date" parameter when using "period".
- For a specific date (e.g. "28.07.2026", "July 28", "2 days ago"), convert it to YYYY-MM-DD format and pass it as the "date" parameter. Do NOT pass a "period" when using "date".
- Examples:
  - "How was business today?" → get_business_summary(period="today")
  - "Show me July 28, 2026" → get_business_summary(date="2026-07-28")
  - "What happened 2 days ago?" → get_business_summary(date="2026-07-26")  [if today is 2026-07-28]
  - "Show me this week" → get_business_summary(period="week")
  
### DATE ACCURACY
- The current server date is {today_str}. This is the authoritative date.
- NEVER calculate relative dates yourself. Pass these exact strings to the backend:
  - "today" → pass start_date="today"
  - "yesterday" → pass start_date="yesterday"
  - "this week" → pass start_date="this week"
- Do NOT convert these to actual dates like "2026-08-02" — the backend handles it.

### TICKET TRIAGE
- get_pending_tickets_summary returns explicit "has_urgent_tickets" and "has_unassigned_tickets" flags — check these directly, don't infer from array contents.
- If has_urgent_tickets is true, list them first and flag them as needing immediate attention.
- "Oldest unanswered" tickets are already sorted — present in that order, don't re-sort.
- When showing tickets, ALWAYS include the user's name and email so the admin can contact them.
- Format: "Ticket ID: tick_XXXX 
           User: John (john@email.com) 
           Subject: ..."

### ORDER STATUS BREAKDOWN
- get_order_status_breakdown's "breakdown" field is a dict of status → count. Report all statuses present, don't cherry-pick.
- "has_stuck_processing_orders" flags whether any orders are still in Processing — mention this proactively if true, since it may indicate a fulfillment bottleneck.


"""

admin_tools = [
    {
    "type": "function",
    "function": {
        "name": "get_business_summary",
        "description": "Get a summary of business performance for a period. Use 'date' (YYYY-MM-DD) for a specific day, or 'period' for today/yesterday/week.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["today", "yesterday", "week"], "nullable": True},
                "date": {"type": "string", "nullable": True, "description": "Specific date in YYYY-MM-DD format, e.g. '2026-07-28'."}
            }
        }
    }
},
    {
        "type": "function",
        "function": {
            "name": "get_sales_analytics",
            "description": "Get sales trends over the past week, including daily revenue breakdown and the best sales day. Use for 'sales this week', 'revenue trend', 'best sales day'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "compare": {"type": "string", "enum": ["last_month"], "nullable": True, "description": "Set to 'last_month' if the user wants a month-over-month comparison."}
                }
            }
        }
    },
{
    "type": "function",
    "function": {
        "name": "get_top_selling_products",
        "description": "Get top selling products ranked by units sold, for any date range or phrase like 'this week', 'last month', 'all time', or a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "nullable": True, "description": "Start of the range — natural phrase or date, e.g. 'last month', '2026-01-01', 'all time'. Omit for default (this week)."},
                "end_date": {"type": "string", "nullable": True, "description": "End of the range. Omit to default to now."},
                "limit": {"type": "integer", "nullable": True},
                "min_units": {"type": "integer", "nullable": True}
            }
        }
    }
},

{
    "type": "function",
    "function": {
        "name": "get_product_performance",
        "description": "Get comprehensive performance data for a product — sales history, price vs category average, rating, and reviews. Use to answer 'why isn't X selling', 'how is X performing'. Requires a real product_id — call resolve_product_name FIRST to obtain it from a product name.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The real product id, obtained from calling resolve_product_name first — never guess this."
                }
            },
            "required": ["product_id"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_inventory_alerts",
        "description": "Get out-of-stock products, low-stock products, and products likely to run out soon based on recent sales velocity.",
        "parameters": {
            "type": "object",
            "properties": {
                "low_stock_threshold": {"type": "integer", "nullable": True, "description": "Stock level below which a product is considered low, default 10."}
            }
        }
    }
},{
    "type": "function",
    "function": {
        "name": "resolve_product_name",
        "description": "Resolve a product name (even partial or approximate) to its real product_id. ALWAYS call this before get_product_performance — never guess or pass a name directly to that tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "The product name as mentioned by the user, e.g. 'Levi's 501 Jeans'"
                }
            },
            "required": ["product_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_pending_tickets_summary",
        "description": "Get a summary of open support tickets — urgent ones, oldest unanswered, and unassigned tickets needing attention.Each ticket includes the user's name and email for follow-up. Use for 'any urgent tickets', 'what needs my attention', 'pending support issues'.",
        "parameters": {"type": "object", "properties": {}}
    }
},
{
    "type": "function",
    "function": {
        "name": "get_order_status_breakdown",
        "description": "Get a count of orders by status (Processing, delivered, Cancelled, etc.) for a date range. Use for 'how many orders are stuck in processing', 'orders needing shipping', 'order status overview'.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "nullable": True, "description": "Start of range, e.g. 'last month', '2026-07-01'. Defaults to past week."},
                "end_date": {"type": "string", "nullable": True}
            }
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "natural_language_business_query",
        "description": "Answer complex business questions by querying the database. Use for questions like 'which products have high ratings but low sales', 'which customers spent over $1000 this month', 'which category generated the most revenue'. The LLM analyzes the question and returns relevant data.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The exact business question the admin asked, verbatim."
                }
            },
            "required": ["question"]
        }
    }
}
]