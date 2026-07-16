# agent/tools.py

ecommerce_tools = [
    {
        "type": "function",
        "function": {
            "name": "ai_omni_search",
            "description": "Search THE-MRU-STORE database for products using a general keyword. Returns a list of matching products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "The search keyword (e.g., 'Samsung', 'Jeans', 'mouse')"
                    }
                },
                "required": ["q"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_by_id",
            "description": "Get exact details for a single product using its unique database ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The unique ID of the product (e.g., 'prod_001')"
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a new support ticket for a user complaining about an issue. YOU MUST HAVE THE ORDER ID TO USE THIS TOOL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {"type": "string", "description": "The ID of the user"},
                    "subject": {"type": "string", "description": "A short summary of the issue"},
                    "message": {"type": "string", "description": "The detailed complaint"},
                    "orderId": {"type": "string", "description": "The related order ID, if known"}
                },
                "required": ["userId", "subject", "message", "orderId"]
            }
        }
    },
    {
            "type": "function",
            "function": {
                "name": "search_store_policy",
                "description": "Searches the store's knowledge base for FAQs, return policies, shipping rules, and general store operations. Use this whenever the user asks a question about HOW the store works rather than searching for specific products.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "q": {
                            "type": "string",
                            "description": "The specific question or topic to search for (e.g., 'return policy', 'shipping time', 'payment methods')"
                        }
                    },
                    "required": ["q"]
                }
            }
        },
]