import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

"""
Database configuration
Priority:
1) DATABASE_URL env (e.g., sqlite:///:memory:)
2) Compose default Postgres (POSTGRES_* env)
"""

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Lấy DSN từ biến môi trường (docker-compose đã đặt sẵn)
    DB_USER = os.getenv("POSTGRES_USER", "affiliate_user")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "affiliate_pass")
    DB_NAME = os.getenv("POSTGRES_DB", "affiliate_db")
    DB_HOST = os.getenv("POSTGRES_HOST", "db")   # trong Docker: service name "db"
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLite needs special connect_args for thread check
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
