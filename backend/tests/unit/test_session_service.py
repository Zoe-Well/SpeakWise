from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from backend.src.models.profile import UserProfile
from backend.src.models.session import ConversationSession
from backend.src.services import session_service


def _db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_session_model_and_service_default_to_normal() -> None:
    assert ConversationSession(profile_id=1, name="default").mode == "normal"

    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    conv = session_service.create_session(db, profile.id, "service-default")
    assert conv.mode == "normal"


def test_update_session_can_switch_between_normal_and_interview() -> None:
    db = _db()
    profile = UserProfile(name="Zoe", is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    conv = session_service.create_session(db, profile.id, "switch")

    updated = session_service.update_session(db, conv.id, {"mode": "interview"})

    assert updated is not None
    assert updated.mode == "interview"
