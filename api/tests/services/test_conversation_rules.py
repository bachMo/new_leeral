from datetime import timedelta

from app.core.clock import utcnow
from app.services.conversation_service import is_guest_session_expired


def test_a_guest_session_within_the_ttl_is_not_expired() -> None:
    assert not is_guest_session_expired(utcnow() - timedelta(hours=4), ttl_hours=5)


def test_a_guest_session_past_the_ttl_is_expired() -> None:
    assert is_guest_session_expired(utcnow() - timedelta(hours=6), ttl_hours=5)
