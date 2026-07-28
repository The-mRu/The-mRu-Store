# agent/tools.py

ecommerce_tools = [
    {
        "type": "function",
        "function": {
            "name": "ai_omni_search",
            "description": "Search the product catalog. Use this whenever the user wants to see or browse actual products — including 'show me [brand] products', '[brand] [category]', or any request implying they want a product list, not just a list of brand names.",
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
        "description": "Lists brand NAMES available in a category — use ONLY for browse questions like 'what brands do you carry' or 'which companies make X'. Do NOT use this when the user wants to see actual products from a brand (e.g. 'show me Apple products', 'Nike shoes') — use ai_omni_search with the brand filter for that instead.",
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
    
    ### Recommend Products
    {
    "type": "function",
    "function": {
        "name": "recommend_products",
        "description": "Recommend products based on a described need (e.g. 'phone for gaming', 'laptop for university', 'best phone under $700'). Uses search plus rating/stock signals to rank recommendations, not just relevance.",
        "parameters": {
            "type": "object",
            "properties": {
                "need": {"type": "string"},
                "category": {"type": "string", "nullable": True},
                "max_price": {"type": "number", "nullable": True},
                "min_rating": {"type": "number", "nullable": True}
            },
            "required": ["need"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "compare_products",
        "description": "Compare 2-3 specific products side-by-side on price, rating, reviews, warranty, and stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["product_ids"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_similar_products",
        "description": "Find products similar to a given product — same category, similar price range, and same brand when available.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"}
            },
            "required": ["product_id"]
        }
    }
},
    
    ### ORDER MANAGEMENT FUNCTIONS
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
    {
    "type": "function",
    "function": {
        "name": "get_user_orders",
        "description": "Retrieve the list of all orders placed by the currently logged-in user, with their status and totals. Use this when the user asks to see their orders, order history, or 'my orders' without referencing a specific Order ID.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
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
        "description": (
            "Searches the store's knowledge base for FAQs, return policies, shipping rules, "
            "contact information, support email/phone, business hours, and general store operations. "
            "Use this whenever the user asks a question about HOW the store works, how to reach support, or wants contact details — rather than searching for specific products."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "The specific question or topic to search for (e.g., 'return policy', 'shipping time', 'payment methods', 'contact email', 'support phone number')"
                }
            },
            "required": ["q"]
        }
    }
    },
]