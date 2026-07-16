# backend/db/chat_repository.py
from backend.db.database import db
from datetime import datetime

class ChatRepository:
    @staticmethod
    async def get_session(session_id: str):
        return await db.ChatSessions.find_one({"sessionId": session_id})

    @staticmethod
    async def create_session(session_id: str, user_id: str = None):
        new_session = {
            "sessionId": session_id,
            "userId": user_id,
            "messages": [],
            "updatedAt": datetime.utcnow()
        }
        await db.ChatSessions.insert_one(new_session)
        return new_session

    @staticmethod
    async def update_messages(session_id: str, messages: list):
        await db.ChatSessions.update_one(
            {"sessionId": session_id},
            {"$set": {"messages": messages, "updatedAt": datetime.utcnow()}}
        )

    @staticmethod
    async def link_session_to_user(session_id: str, user_id: str):
        # Links a guest session to a permanent user account
        await db.ChatSessions.update_one(
            {"sessionId": session_id},
            {"$set": {"userId": user_id}}
        )

    @staticmethod
    async def get_history_by_user(user_id: str):
        # Fetches all session threads for a logged-in user
        cursor = db.ChatSessions.find({"userId": user_id}).sort("updatedAt", -1)
        return await cursor.to_list(length=50)
    
    @staticmethod
    async def get_master_user_session(user_id: str):
        # Finds the single unified document for a registered user
        return await db.ChatSessions.find_one({"userId": user_id})