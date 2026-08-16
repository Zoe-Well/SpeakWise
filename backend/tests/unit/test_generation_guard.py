from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession
from backend.src.services.generation_guard import GenerationGuard, validate_owned_session


def _db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_guard_blocks_parallel_generation_for_same_key() -> None:
    guard = GenerationGuard(max_requests=10, window_seconds=30)

    assert guard.try_acquire("session:1") is None
    assert guard.try_acquire("session:1") == "上一个请求尚未完成，请稍后"
    guard.release("session:1")
    assert guard.try_acquire("session:1") is None


def test_guard_rate_limits_after_completed_requests() -> None:
    now = [100.0]
    guard = GenerationGuard(max_requests=2, window_seconds=30, clock=lambda: now[0])

    assert guard.try_acquire("session:1") is None
    guard.release("session:1")
    assert guard.try_acquire("session:1") is None
    guard.release("session:1")
    assert guard.try_acquire("session:1") == "请求过于频繁，请稍后再试"
    now[0] += 31
    assert guard.try_acquire("session:1") is None


def test_validate_owned_session_rejects_other_profile() -> None:
    db = _db()
    owner = UserProfile(name="owner", is_active=True)
    other = UserProfile(name="other", is_active=False)
    db.add(owner)
    db.add(other)
    db.commit()
    db.refresh(owner)
    db.refresh(other)
    conv = ConversationSession(profile_id=other.id, name="private")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    try:
        validate_owned_session(db, conv.id, owner.id)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("cross-profile session access must be rejected")
