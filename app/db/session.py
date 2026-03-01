from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings

# Load DATABASE_URL from Settings so .env is always respected
# (os.getenv alone does NOT read .env files automatically)
_settings = get_settings()

engine = create_engine(_settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()