import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import inspect, text

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


def apply_simple_migrations(engine) -> None:
    """
    Simple, idempotent migrations to backfill missing columns when the DB was created
    from an older schema (e.g., existing Postgres DB).

    Currently handled (table: product_offers):
      - campaign_id (VARCHAR)
      - approval_status (VARCHAR)
      - eligible_commission (BOOLEAN DEFAULT FALSE)
      - source_type (VARCHAR)
      - affiliate_link_available (BOOLEAN DEFAULT FALSE)
      - product_id (VARCHAR)
      - extra (TEXT)
      - updated_at (TIMESTAMP WITH TIME ZONE)

    Notes:
    - CREATE TABLE IF NOT EXISTS is covered by Base.metadata.create_all elsewhere.
    - This function only adds the column if it does not exist.
    - It is intentionally minimal to avoid heavy migration dependencies.
    """
    inspector = inspect(engine)
    try:
        cols = {c["name"] for c in inspector.get_columns("product_offers")}
    except Exception:
        # Table may not exist yet; skip product_offers patching but continue other tables.
        cols = set()

    statements: list[str] = []
    if "campaign_id" not in cols:
        statements.append("ALTER TABLE product_offers ADD COLUMN campaign_id VARCHAR")
    if "approval_status" not in cols:
        statements.append("ALTER TABLE product_offers ADD COLUMN approval_status VARCHAR")
    if "eligible_commission" not in cols:
        # DEFAULT FALSE is safe; existing rows get FALSE
        statements.append("ALTER TABLE product_offers ADD COLUMN eligible_commission BOOLEAN DEFAULT FALSE")
    if "source_type" not in cols:
        statements.append("ALTER TABLE product_offers ADD COLUMN source_type VARCHAR")
    if "affiliate_link_available" not in cols:
        statements.append("ALTER TABLE product_offers ADD COLUMN affiliate_link_available BOOLEAN DEFAULT FALSE")
    if "product_id" not in cols:
        statements.append("ALTER TABLE product_offers ADD COLUMN product_id VARCHAR")
    if "extra" not in cols:
        # TEXT is widely compatible across SQLite/Postgres
        statements.append("ALTER TABLE product_offers ADD COLUMN extra TEXT")
    if "updated_at" not in cols:
        # Keep it nullable to avoid heavy locks; app code sets it on update
        if engine.dialect.name == "postgresql":
            statements.append("ALTER TABLE product_offers ADD COLUMN updated_at TIMESTAMPTZ")
        else:
            statements.append("ALTER TABLE product_offers ADD COLUMN updated_at TIMESTAMP")

    # Migrate affiliate_templates: add platform column if missing
    try:
        cols_tpl = {c["name"] for c in inspector.get_columns("affiliate_templates")}
    except Exception:
        cols_tpl = set()

    statements_tpl: list[str] = []
    if "platform" not in cols_tpl:
        # Add nullable platform column; keep it generic VARCHAR/TEXT
        if engine.dialect.name == "postgresql":
            statements_tpl.append("ALTER TABLE affiliate_templates ADD COLUMN platform VARCHAR")
        else:
            statements_tpl.append("ALTER TABLE affiliate_templates ADD COLUMN platform TEXT")

    with engine.begin() as conn:
        # Apply column additions first (if any)
        for sql in statements + statements_tpl:
            try:
                conn.execute(text(sql))
            except Exception:
                # Ignore if another process already applied it.
                pass

        # Cleanup migration: null-out placeholder strings previously persisted
        try:
            # Works for both Postgres and SQLite (CASE/NULLIF expressions)
            conn.execute(text(
                """
                UPDATE campaigns SET
                  start_time = CASE WHEN start_time IN ('API_MISSING','NO_DATA','') THEN NULL ELSE start_time END,
                  end_time = CASE WHEN end_time IN ('API_MISSING','NO_DATA','') THEN NULL ELSE end_time END,
                  merchant = CASE WHEN merchant IN ('API_MISSING','NO_DATA','') THEN NULL ELSE merchant END,
                  name = CASE WHEN name IN ('API_MISSING','NO_DATA','') THEN NULL ELSE name END,
                  status = CASE WHEN status IN ('API_MISSING','NO_DATA','') THEN NULL ELSE status END,
                  approval = CASE WHEN approval IN ('API_MISSING','NO_DATA','') THEN NULL ELSE approval END,
                  user_registration_status = CASE WHEN user_registration_status IN ('API_MISSING','NO_DATA','') THEN NULL ELSE user_registration_status END
                """
            ))
        except Exception:
            # Non-fatal: cleanup may run on non-existent table or fail safely
            pass
