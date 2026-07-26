# agent/tools.py
from backend.api.search import search_products_core

async def ai_omni_search_impl(q, category=None, gender=None, brand=None,min_price=None, max_price=None):
    """
    Called directly by the orchestrator's tool-execution loop — returns a plain
    list, never raises HTTPException, so a no-results case is just an empty
    list the LLM can react to conversationally.
    """
    return await search_products_core(
        q=q, category=category, gender=gender, brand=brand,
        min_price=min_price, max_price=max_price
    )
    
async def list_categories_impl():
    from backend.db.database import db
    categories = await db.Categories.find(
        {"isActive": True, "parentCategoryId": {"$in": [None, "cat_fashion", "cat_electronics"]}},
        {"_id": 0, "name": 1, "description": 1}
    ).to_list(length=50)
    return categories
    
ecommerce_tools = [
    {
        "type": "function",
        "function": {
            "name": "ai_omni_search",
            "description": "Search the database for products using keywords and optional filters. Use this when the user is looking for items to buy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "The main product keyword (e.g., 'dress', 'laptop', 'shirt'). DO NOT include gender, demographic, or category words here. Extract those into the category parameter instead."
                    },
                    "brand": {
                        "type": "string",
                        "description": "Specific brand to filter by (e.g., 'Dell', 'Lenovo', 'Carhartt')."
                    },
                    "category": {
                        "type": "string",
                        "description":(
                                    "ONLY use this filter if the user explicitly specifies a demographic or the 'Kids' section "
                                    "(e.g. 'men', 'women', 'kids', 'toys', 'kids clothing'). Map any children's item — clothing, "
                                    "toys, shoes, anything — to the 'Kids' category. Do NOT guess or infer categories otherwise. "
                                    "If the user just asks for 't-shirts', 'laptops', or 'shoes' with no age/gender context, leave this blank."
                                )
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum price constraint."
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price constraint."
                    }
                }
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "list_categories",
        "description": (
            "Returns the full list of product categories available in the store. "
            "Use this when the user asks broad discovery questions like 'what do you sell', "
            "'what categories do you have', 'what kind of products are available', or similar — "
            "anything where they want an overview rather than a specific search."
        ),
        "parameters": {"type": "object", "properties": {}}
    }
    },
    {
    "type": "function",
    "function": {
        "name": "list_brands",
        "description": "Returns the actual brand names available in the store, optionally filtered by category. Use whenever the user asks 'which brands', 'what companies', or similar — NEVER answer this from memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category slug to filter by, e.g. 'footwear'. Omit for all brands."}
            }
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
            "name": "check_order_status",
            "description": "Verifies if an Order ID exists in the database and belongs to the currently logged-in user. ALWAYS call this BEFORE creating a support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orderId": {
                        "type": "string",
                        "description": "The Order ID provided by the user."
                    }
                },
                "required": ["orderId"]
            }
        }
    },

    ### Support Ticket Management Functions

    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a new support ticket for the currently logged-in user. YOU MUST HAVE THE ORDER ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orderId": {
                        "type": "string",
                        "description": "The Order ID. If the issue is a general account, login, or website issue NOT related to an order, pass the exact string 'N/A'."
                    },
                    "subject": {
                        "type": "string",
                        "description": "A short, 4-6 word summary of the issue."
                    },
                    "message": {
                        "type": "string",
                        "description": "The detailed complaint from the user."
                    }
                },
                "required": ["orderId", "subject", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_ticket_status",
            "description": "Check the current status and updates of an existing support ticket belonging to the logged-in user. YOU MUST HAVE THE TICKET ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticketId": {
                        "type": "string",
                        "description": "The unique ID of the support ticket. It MUST start with 'tick_' or be a 24-character MongoDB ObjectId. If the user provides an ID starting with '#', it is an Order ID and you must ask them for the Ticket ID instead"
                    }
                },
                "required": ["ticketId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_ticket_comment",
            "description": "Add a new comment or additional details to an existing support ticket owned by the logged-in user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticketId": {
                        "type": "string",
                        "description": "The Ticket ID to update."
                    },
                    "comment": {
                        "type": "string",
                        "description": "The new information the user wants to add."
                    }
                },
                "required": ["ticketId", "comment"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_support_ticket",
            "description": "Close a support ticket owned by the logged-in user if the issue is resolved or they request to cancel it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticketId": {
                        "type": "string"
                    }
                },
                "required": ["ticketId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_ticket",
            "description": "Escalate a ticket owned by the logged-in user to 'urgent' priority if they are extremely angry, demand a human, or threaten to leave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticketId": {
                        "type": "string"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for escalation"
                    }
                },
                "required": ["ticketId", "reason"]
            }
        }
    },

    ### Store Policy Search Function

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