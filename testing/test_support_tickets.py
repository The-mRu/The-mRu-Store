# testing/test_support_tickets.py
import pytest
from backend.api.support_tickets import create_support_ticket, get_ticket_query, TicketRequest

@pytest.mark.asyncio
async def test_ticket_scoped_to_owner():
    query = get_ticket_query("tick_6c2be0", "some_other_user_id")
    # should include userId in the query so wrong-user lookups fail
    assert query["userId"] == "some_other_user_id"

@pytest.mark.asyncio
async def test_ticket_id_or_objectid_lookup():
    query = get_ticket_query("tick_6c2be0", "user123")
    assert "$or" in query or query.get("id") == "tick_6c2be0"
    
### pytest testing/test_support_tickets.py -v