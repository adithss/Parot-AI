# Import connection components first
from database.connection import Base, engine, SessionLocal, get_db, test_connection

# Import models (which depend on Base)
from database import models

# Import schemas and crud
from database import schemas, crud

# Function to initialize database
def init_db():
    """
    Initialize database - create all tables
    """
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "test_connection",
    "models",
    "schemas",
    "crud"
]