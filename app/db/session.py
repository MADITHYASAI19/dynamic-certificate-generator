from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Use aiteqlite for testing or postgres+asyncpg for prod
# For now, we'll use a synchronous session for simplicity if requested,
# but the prompt mentioned SQLAlchemy 2.0 and FastAPI, so async is the modern choice.
# HOWEVER, the user asked for "one transaction" and "one failure never affects others",
# so I will use standard sync sessions for the job processing to avoid async overhead in the loops.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker as SyncSessionMaker

engine = create_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))
AsyncSessionLocal = SyncSessionMaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
