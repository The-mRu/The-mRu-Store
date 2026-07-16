# backend/api/chat.py
from fastapi import APIRouter, Body
from backend.db.chat_repository import ChatRepository
from agent.orchestrator import run_agent

router = APIRouter()

@router.post("/{session_id}")
async def chat_with_agent(
    session_id: str, 
    message: str = Body(...),
    user_id: str = Body(None) # Passed from frontend if logged in
):
    session = None
    active_id = session_id # We track which ID to use for the DB update
    is_master_user = False

    # 1. PRIORITY CHECK: Is the user logged in?
    if user_id:
        session = await ChatRepository.get_master_user_session(user_id)
        if session:
            # We found their global history! Use this instead of the device session.
            active_id = session["sessionId"] 
            is_master_user = True
        else:
            # First time logging in. Let's see if they have a guest session to convert.
            session = await ChatRepository.get_session(session_id)
            if session:
                await ChatRepository.link_session_to_user(session_id, user_id)
                is_master_user = True

    # 2. FALLBACK: Guest User Check
    if not session:
        session = await ChatRepository.get_session(session_id)
        if not session:
            # Brand new guest
            session = await ChatRepository.create_session(session_id, user_id)

    # 3. Run AI and Persist
    history = session.get("messages", [])
    bot_response = await run_agent(message, history)
    
    # 4. Save back to the correct document
    await ChatRepository.update_messages(active_id, history)
    
    return {"reply": bot_response}