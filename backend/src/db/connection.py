"""SQLite 数据库连接与初始化"""

import os
import logging
from sqlmodel import SQLModel, create_engine, Session, text

logger = logging.getLogger(__name__)

# 生产环境使用 SPEAKWISE_DATA_DIR（Electron 传入 userData 路径），开发环境使用项目 data/
DB_DIR = os.environ.get("SPEAKWISE_DATA_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "copilot.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
)


def _migrate_thinking_column():
    """为 messages 表新增 thinking 列（幂等迁移）。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN thinking TEXT"))
            conn.commit()
            logger.info("Migration: added thinking column to messages")
    except Exception:
        pass


def _migrate_mode_column():
    """为 conversation_sessions 表新增 mode 列（幂等迁移）。"""
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE conversation_sessions ADD COLUMN mode TEXT DEFAULT 'normal'"))
            except Exception:
                pass
            # 即使列已存在，也修复历史 NULL 值。
            conn.execute(text("UPDATE conversation_sessions SET mode = 'normal' WHERE mode IS NULL"))
            conn.commit()
            logger.info("Migration: ensured conversation session mode column")
    except Exception:
        pass


def _migrate_memory_columns():
    """为已有会话表增加滚动摘要字段（幂等）。"""
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE conversation_sessions ADD COLUMN memory_summary TEXT"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE conversation_sessions ADD COLUMN summary_up_to_message_id INTEGER"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass


def init_db():
    """创建所有表（若不存在）。后续可替换为 Alembic 迁移。"""
    # 确保所有模型被导入以注册到 SQLModel.metadata
    import backend.src.models.session  # noqa: F401
    import backend.src.models.profile  # noqa: F401
    import backend.src.models.document  # noqa: F401
    import backend.src.models.template  # noqa: F401
    import backend.src.models.settings  # noqa: F401
    import backend.src.models.voice_adapter  # noqa: F401
    import backend.src.models.job_context  # noqa: F401
    import backend.src.models.apikey      # noqa: F401

    os.makedirs(DB_DIR, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _migrate_thinking_column()
    _migrate_mode_column()
    _migrate_memory_columns()

    # Ensure api_keys table exists
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS api_keys ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, "
                "provider VARCHAR(30) DEFAULT 'deepseek', name VARCHAR(100) DEFAULT '', "
                "api_key VARCHAR(200) DEFAULT '', is_active BOOLEAN DEFAULT 0, "
                "created_at DATETIME)"
            ))
            conn.commit()
    except Exception:
        pass

    # is_active columns for profile/JD/document versioning
    try:
        with engine.connect() as conn:
            for tbl, col in [("user_profiles","is_active"), ("job_contexts","is_active"), ("source_documents","is_active")]:
                try: conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} BOOLEAN DEFAULT 1"))
                except Exception: pass
            conn.commit()
    except Exception: pass

    # Voice settings columns
    try:
        with engine.connect() as conn:
            for col in ("xf_appid", "xf_api_key", "xf_api_secret"):
                try: conn.execute(text(f"ALTER TABLE display_settings ADD COLUMN {col} TEXT"))
                except Exception: pass
            conn.commit()
    except Exception: pass

    # api_keys model column (added later)
    try:
        with engine.connect() as conn:
            try: conn.execute(text("ALTER TABLE api_keys ADD COLUMN model TEXT DEFAULT ''"))
            except Exception: pass
            conn.commit()
    except Exception:
        pass

    # LLM settings columns
    try:
        with engine.connect() as conn:
            for col in ("llm_provider", "llm_api_key", "llm_model"):
                try:
                    conn.execute(text(f"ALTER TABLE display_settings ADD COLUMN {col} TEXT"))
                except Exception:
                    pass
            conn.commit()
    except Exception:
        pass

    # JobContext name column (added for multi-JD management)
    try:
        with engine.connect() as conn:
            try: conn.execute(text("ALTER TABLE job_contexts ADD COLUMN name TEXT DEFAULT ''"))
            except Exception: pass
            conn.commit()
    except Exception: pass

    # Ensure template_defaults table exists (may need manual creation for existing DBs)
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS template_defaults ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, "
                "scope VARCHAR(30) NOT NULL, template_id VARCHAR(100) NOT NULL, "
                "updated_at DATETIME)"
            ))
            conn.commit()
    except Exception:
        pass

    # clear_existing column for profile_update_proposals (overwrite vs append)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE profile_update_proposals ADD COLUMN clear_existing BOOLEAN DEFAULT 0"))
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass


def get_session():
    """获取一个新的数据库会话（FastAPI 依赖注入，自动关闭）。"""
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
