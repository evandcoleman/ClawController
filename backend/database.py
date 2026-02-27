from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from models import Base, Agent, AgentRole, AgentStatus
import os
import logging
from pathlib import Path

logger = logging.getLogger("clawcontroller.database")

# Get the directory where this script lives
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR.parent / "data"

# Create data directory if it doesn't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default to local SQLite in the data folder
DEFAULT_DB = f"sqlite:///{DATA_DIR}/mission_control.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create tables and migrate missing columns."""
    Base.metadata.create_all(bind=engine)
    
    # Auto-migrate missing columns for existing databases
    _run_migrations()
    
    logger.info("Database initialized. Add agents via the Agent Management panel.")

def _run_migrations():
    """Add any missing columns to existing tables (SQLite compatible)."""
    with engine.connect() as conn:
        # Get existing columns in tasks table
        result = conn.execute(text("PRAGMA table_info(tasks)"))
        task_columns = [row[1] for row in result.fetchall()]
        
        # Define migrations: (column_name, column_type, default_value)
        task_migrations = [
            ("reviewer_id", "VARCHAR", None),
            ("due_at", "DATETIME", None),
        ]
        
        for col_name, col_type, default in task_migrations:
            if col_name not in task_columns:
                try:
                    sql = f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}"
                    if default is not None:
                        sql += f" DEFAULT {default}"
                    conn.execute(text(sql))
                    logger.info("Migration: Added '%s' column to tasks table", col_name)
                except Exception as e:
                    logger.warning("Migration warning for %s: %s", col_name, e)
        
        # Get existing columns in agents table
        result = conn.execute(text("PRAGMA table_info(agents)"))
        agent_columns = [row[1] for row in result.fetchall()]
        
        agent_migrations = [
            ("token", "VARCHAR", None),
            ("primary_model", "VARCHAR", None),
            ("fallback_model", "VARCHAR", None),
            ("current_model", "VARCHAR", None),
            ("model_failure_count", "INTEGER", "0"),
        ]
        
        for col_name, col_type, default in agent_migrations:
            if col_name not in agent_columns:
                try:
                    sql = f"ALTER TABLE agents ADD COLUMN {col_name} {col_type}"
                    if default is not None:
                        sql += f" DEFAULT {default}"
                    conn.execute(text(sql))
                    logger.info("Migration: Added '%s' column to agents table", col_name)
                except Exception as e:
                    logger.warning("Migration warning for %s: %s", col_name, e)
        
        conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
