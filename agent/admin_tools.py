# agent/admin_tools.py
from datetime import datetime

def get_admin_system_prompt():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
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
}
]