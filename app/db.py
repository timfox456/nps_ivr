from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

class Base(DeclarativeBase):
    pass

# Determine which database to use based on configuration
def get_database_url():
    if settings.use_postgres and settings.postgres_url:
        return settings.postgres_url
    return settings.database_url

db_url = get_database_url()

# Create engine with appropriate connection args
engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    pool_pre_ping=True,  # Verify connections before using them
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Log which database is being used
import logging
logger = logging.getLogger(__name__)
logger.info(f"Using database: {'PostgreSQL' if settings.use_postgres else 'SQLite'} - {db_url}")

def init_db():
    from . import models  # ensure models are imported
    Base.metadata.create_all(bind=engine)
