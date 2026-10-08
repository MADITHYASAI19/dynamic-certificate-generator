"""
Database session management.
Synchronous sessions are used here for simplicity and reliability during
bulk certificate generation loops, avoiding async overhead.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Ensure we use the correct driver for PostgreSQL
db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(db_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to provide a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
