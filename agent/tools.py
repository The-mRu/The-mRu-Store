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
            "name": "check_order_status",
            "description": "Verifies if an Order ID exists in the database and belongs to the user. ALWAYS call this BEFORE creating a support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {"type": "string", "description": "The exact ID of the logged-in user."},
                    "orderId": {"type": "string", "description": "The Order ID provided by the user."}
                },
                "required": ["userId", "orderId"]
            }
        }
    },
    
    ### Support Ticket Management Functions
    
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a new support ticket. Use this when a logged-in user has an issue. YOU MUST HAVE THE ORDER ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string", 
                        "description": "The exact ID of the logged-in user."
                    },
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
                "required": ["userId", "orderId", "subject", "message"] 
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_ticket_status",
            "description": "Check the current status and updates of an existing support ticket. YOU MUST HAVE THE TICKET ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string", 
                        "description": "The exact ID of the logged-in user."
                    },
                    "ticketId": {
                        "type": "string", 
                        "description": "The unique ID of the support ticket. It MUST start with 'tick_' or be a 24-character MongoDB ObjectId. If the user provides an ID starting with '#', it is an Order ID and you must ask them for the Ticket ID instead"
                    }
                },
                "required": ["userId", "ticketId"] 
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_ticket_comment",
            "description": "Add a new comment or additional details to an existing support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {"type": "string", "description": "The exact ID of the logged-in user."},
                    "ticketId": {"type": "string", "description": "The Ticket ID to update."},
                    "comment": {"type": "string", "description": "The new information the user wants to add."}
                },
                "required": ["userId", "ticketId", "comment"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_support_ticket",
            "description": "Close a support ticket if the user's issue is resolved or they request to cancel the ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {"type": "string"},
                    "ticketId": {"type": "string"}
                },
                "required": ["userId", "ticketId"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_ticket",
            "description": "Escalate a ticket to 'urgent' priority if the user is extremely angry, demands a human, or threatens to leave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {"type": "string"},
                    "ticketId": {"type": "string"},
                    "reason": {"type": "string", "description": "Brief reason for escalation"}
                },
                "required": ["userId", "ticketId", "reason"]
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