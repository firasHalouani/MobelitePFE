import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Allow overriding the database via environment variable for Docker/Postgres support
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./invisithreat.db")

# When using SQLite, pass connect_args to avoid thread check errors
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Tables are created on app startup in `app.main` after models are imported
