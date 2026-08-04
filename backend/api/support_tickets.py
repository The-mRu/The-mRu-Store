# backend/api/support_tickets.py
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db.database import db

router = APIRouter()


# ---------- Models ----------
class SupportTicket(BaseModel):
    """Legacy ticket model (kept for reference)."""
    userId: str
    orderId: str
    subject: str
    message: str
    # priority: str = "medium"


class TicketRequest(BaseModel):
    userId: str
    orderId: str
    subject: str
    message: str
    # priority: str = "medium"  # Optional if AI doesn't send it


class CommentRequest(BaseModel):
    user_id: str
    comment: str


class EscalateRequest(BaseModel):
    reason: str


# ---------- Helper ----------
def get_ticket_query(ticket_id: str, user_id: str) -> dict:
    """
    Build a MongoDB query that matches a ticket by its string `id` field
    or by the legacy `_id` ObjectId, always scoped to the given user.
    """
    query = {"userId": user_id}
    try:
        query["$or"] = [{"id": ticket_id}, {"_id": ObjectId(ticket_id)}]
    except InvalidId:
        query["id"] = ticket_id
    return query


# ---------- Routes ----------

@router.post("/", status_code=201)
async def create_support_ticket(ticket: TicketRequest):
    """Create a support ticket, preventing duplicates for the same order."""
    
    # --- Duplicate prevention check ---
    if ticket.orderId and ticket.orderId.upper() != "N/A":
        existing_ticket = await db.SupportTickets.find_one({
            "userId": ticket.userId,
            "orderId": ticket.orderId,
            "status": {"$in": ["open", "under review", "urgent"]}
        })
        if existing_ticket:
            raise HTTPException(
                status_code=400,
                detail=f"You already have an active ticket ({existing_ticket.get('id')}) for this order."
            )
    # ----------------------------------

    ticket_data = ticket.model_dump()
    ticket_data["id"] = f"tick_{uuid4().hex[:6]}"
    ticket_data["status"] = "open"
    ticket_data["assignedAdmin"] = "unassigned"
    ticket_data["createdAt"] = datetime.now(timezone.utc)
    ticket_data["comments"] = []  # ensures the array always exists

    result = await db.SupportTickets.insert_one(ticket_data)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create support ticket")

    return {
        "success": True,
        "ticket_id": ticket_data["id"],
        "status": ticket_data["status"],
        "message": "Ticket successfully routed to the support queue.",
    }


@router.get("/")
async def list_support_tickets():
    """Return a list of support tickets (up to 100)."""
    tickets = await db.SupportTickets.find({}, {"_id": 0}).to_list(length=100)
    return tickets


@router.get("/{ticket_id}")
async def get_ticket_status(
    ticket_id: str,
    user_id: str = Query(..., description="ID of the ticket owner"),
):
    """Retrieve the status and details of a specific support ticket."""
    # Guard against accidentally supplying an Order ID
    if ticket_id.startswith("#") or len(ticket_id) > 30:
        raise HTTPException(
            status_code=400,
            detail="This appears to be an Order ID. Please provide a valid Ticket ID (e.g., tick_123456).",
        )

    query = get_ticket_query(ticket_id, user_id)
    ticket = await db.SupportTickets.find_one(query)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found. Please verify the Ticket ID.")

    created_date = ticket.get("createdAt")
    formatted_date = (
        created_date.strftime("%B %d, %Y")
        if created_date
        else "Date unknown (Legacy Ticket)"
    )
    display_id = ticket.get("id") or str(ticket["_id"])

    return {
        "ticket_id": display_id,
        "subject": ticket.get("subject", "No Subject"),
        "status": ticket.get("status", "open").upper(),
        "created_on": formatted_date,
        "assigned_to": ticket.get("assignedAdmin", "Pending Assignment"),
        'comments': ticket.get("comments", []),
    }


@router.post("/{ticket_id}/comments")
async def add_comment(ticket_id: str, payload: CommentRequest):
    """Append a user comment to the ticket."""
    query = get_ticket_query(ticket_id, payload.user_id)

    new_comment = {
        "text": payload.comment,
        "addedAt": datetime.now(timezone.utc),
        "author": "user",
    }

    result = await db.SupportTickets.update_one(
        query, {"$push": {"comments": new_comment}}
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found or you do not have permission to update it.",
        )

    return {"status": "success", "message": "Comment added successfully."}


@router.patch("/{ticket_id}/close")
async def close_ticket(
    ticket_id: str,
    user_id: str = Query(..., description="ID of the ticket owner"),
):
    """Close a ticket by setting its status to 'resolved'."""
    query = get_ticket_query(ticket_id, user_id)

    result = await db.SupportTickets.update_one(
        query,
        {"$set": {"status": "resolved", "closedAt": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found or already closed.")

    return {"status": "success", "message": "Ticket has been closed."}


@router.patch("/{ticket_id}/escalate")
async def escalate_ticket(
    ticket_id: str,
    user_id: str = Query(..., description="ID of the ticket owner"),
    payload: EscalateRequest = ...,
):
    """Flag a ticket as urgent for admin attention."""
    query = get_ticket_query(ticket_id, user_id)

    result = await db.SupportTickets.update_one(
        query,
        {
            "$set": {
                "priority": "urgent",
                "escalationReason": payload.reason,
                "escalatedAt": datetime.now(timezone.utc),
            }
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    return {"status": "success", "message": "Ticket escalated to human administrators."}

@router.get("/user/{user_id}")
async def get_user_tickets(user_id: str):
    """Return all support tickets for a specific user."""
    tickets = await db.SupportTickets.find(
        {"userId": user_id},
        {"_id": 0, "id": 1, "subject": 1, "status": 1, "createdAt": 1, "orderId": 1}
    ).sort("createdAt", -1).to_list(length=50)

    if not tickets:
        return {"tickets": [], "message": "No tickets found."}

    return {
        "tickets": [
            {
                "ticket_id": t.get("id"),
                "subject": t.get("subject", "No Subject"),
                "status": t.get("status", "open"),
                "order_id": t.get("orderId"),
                "created_at": t.get("createdAt").strftime("%B %d, %Y") if t.get("createdAt") else None
            }
            for t in tickets
        ],
        "total": len(tickets)
    }