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
### ANALYTICS TOOLS
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
            "description": "Get the best or worst selling products by units sold. Use for 'top selling products', 'best selling phones', 'worst selling products'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "nullable": True, "description": "How many products to return, default 5."},
                    "order": {"type": "string", "enum": ["best", "worst"], "nullable": True}
                }
            }
        }
    },
]