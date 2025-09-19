import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Lấy DSN từ biến môi trường (docker-compose đã đặt sẵn)
DB_USER = os.getenv("POSTGRES_USER", "affiliate_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "affiliate_pass")
DB_NAME = os.getenv("POSTGRES_DB", "affiliate_db")
DB_HOST = os.getenv("POSTGRES_HOST", "db")   # trong Docker: service name "db"
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
