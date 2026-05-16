# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# It is recommended to load database connection info from an .env file or similar
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_DB = os.environ.get("POSTGRES_DB")

DEFAULT_DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@data-analysis-agent-db:5432/{POSTGRES_DB}"

# If USER_DATABASE_URL is set, use it preferentially
DATABASE_URL = os.getenv("USER_DATABASE_URL", DEFAULT_DB_URL)

# Create an engine shared across the entire application
engine = create_engine(DATABASE_URL)

# Factory for creating sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Function used for FastAPI Dependency Injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()