from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, text

from backend.src.db import connection


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_mode_and_memory_migrations_are_idempotent(monkeypatch) -> None:
    engine = _engine()
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE conversation_sessions ("
            "id INTEGER PRIMARY KEY, mode TEXT DEFAULT 'interview')"
        ))
        conn.execute(text("INSERT INTO conversation_sessions (id, mode) VALUES (1, NULL)"))
        conn.commit()
    monkeypatch.setattr(connection, "engine", engine)

    connection._migrate_mode_column()
    connection._migrate_mode_column()
    connection._migrate_memory_columns()
    connection._migrate_memory_columns()

    with engine.connect() as conn:
        mode = conn.execute(text("SELECT mode FROM conversation_sessions WHERE id = 1")).scalar()
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(conversation_sessions)"))
        }
    assert mode == "normal"
    assert {"memory_summary", "summary_up_to_message_id"}.issubset(columns)
