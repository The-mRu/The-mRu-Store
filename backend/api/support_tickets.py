# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from backend.db.database import db

# router = APIRouter()

# class SupportTicket(BaseModel):
#     userId: str
#     orderId: str | None = None
#     subject: str
#     message: str
#     # priority: str = "medium"

# @router.post("/")
# def create_support_ticket(ticket: SupportTicket):
#     result = db.SupportTickets.insert_one(ticket.dict())
#     if not result.inserted_id:
#         raise HTTPException(status_code=500, detail="Failed to create support ticket")
#     return {"message": "Support ticket created", "ticketId": str(result.inserted_id)}

# @router.get("/")
# def list_support_tickets():
#     tickets = list(db.SupportTickets.find({}, {"_id": 0}))
#     return tickets


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db.database import db

router = APIRouter()

class SupportTicket(BaseModel):
    userId: str
    orderId: str 
    subject: str
    message: str
    # priority: str = "medium"

@router.post("/")
async def create_support_ticket(ticket: SupportTicket):
    # 1. Added 'async' to the function definition
    # 2. Added 'await' to the insert_one operation
    
    # result = await db.SupportTickets.insert_one(ticket.dict())
    result = await db.SupportTickets.insert_one(ticket.model_dump())
    
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create support ticket")
        
    return {"message": "Support ticket created", "ticketId": str(result.inserted_id)}

@router.get("/")
async def list_support_tickets():
    # 1. Added 'async', 2. Added 'await', 3. Swapped list() for .to_list()
    tickets = await db.SupportTickets.find({}, {"_id": 0}).to_list(length=100)
    return tickets