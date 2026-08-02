# backend/api/chat.py
from fastapi import APIRouter, Body
from backend.db.chat_repository import ChatRepository
from agent.orchestrator import run_agent
from fastapi import APIRouter, Body, HTTPException
from backend.db.database import db

router = APIRouter()


@router.post("/{session_id}")
async def chat_with_agent(
    session_id: str,
    message: str = Body(...),
    user_id: str = Body(None)  # Passed from frontend if logged in
):
    session = None
    active_id = session_id
    is_master_user = False

    # 1. PRIORITY CHECK: Is the user logged in?
    if user_id:
        session = await ChatRepository.get_master_user_session(user_id)
        if session:
            active_id = session["sessionId"]
            is_master_user = True
        else:
            session = await ChatRepository.get_session(session_id)
            if session:
                await ChatRepository.link_session_to_user(session_id, user_id)
                is_master_user = True

    # 2. FALLBACK: Guest User Check
    if not session:
        session = await ChatRepository.get_session(session_id)
        if not session:
            session = await ChatRepository.create_session(session_id, user_id)

    # 3. Run AI and Persist
    history = session.get("messages", [])
    bot_response = await run_agent(message, history, user_id=user_id)

    # 4. Save back to the correct document
    await ChatRepository.update_messages(active_id, history)

    return {"reply": bot_response}


@router.post("/admin/{session_id}")
async def chat_with_admin_agent(
    session_id: str,
    message: str = Body(...),
    admin_id: str = Body(...)
):
    """
    Admin-facing chat endpoint. Requires a real, active Admins document —
    admin_id is NOT trusted by string presence alone.
    """
    admin = await db.Admins.find_one({"id": admin_id, "isActive": True})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid or inactive admin account.")

    session = await ChatRepository.get_session(session_id)
    if not session:
        session = await ChatRepository.create_session(session_id, admin_id)

    history = session.get("messages", [])
    bot_response = await run_agent(message, history, user_id=admin_id, is_admin=True)

    await ChatRepository.update_messages(session_id, history)

    return {"reply": bot_response}