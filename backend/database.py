import os
import sys
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

# --- Chiến lược chọn DB URL ---
# 1. Nếu người dùng đã chỉ định DATABASE_URL thì dùng luôn.
# 2. Nếu đang chạy trong phiên pytest (dò qua biến môi trường hoặc module 'pytest') -> dùng SQLite file.
#    Lý do: tránh phải cài psycopg2 (chưa có wheel Python 3.13 trên Windows) và không cần Postgres thật để unit test.
# 3. Nếu TESTING=1 cũng dùng SQLite.
# 4. Ngược lại: fallback Postgres (dành cho môi trường docker-compose).
if not DATABASE_URL:
    running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ('pytest' in sys.modules)  # type: ignore[name-defined]
    if running_pytest or os.getenv("TESTING") == "1":
        DATABASE_URL = "sqlite:///./test.db"
    else:
        DB_USER = os.getenv("POSTGRES_USER", "affiliate_user")
        DB_PASS = os.getenv("POSTGRES_PASSWORD", "affiliate_pass")
        DB_NAME = os.getenv("POSTGRES_DB", "affiliate_db")
        DB_HOST = os.getenv("POSTGRES_HOST", "db")   # trong Docker: service name "db"
        DB_PORT = os.getenv("POSTGRES_PORT", "5432")
        DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Nếu vì lý do gì đó vẫn rơi vào Postgres nhưng chưa cài psycopg2, fallback mềm sang SQLite để test không hỏng.
if DATABASE_URL.startswith("postgresql"):
    try:
        import psycopg2  # type: ignore
    except Exception:
        # Ghi log nhẹ (dùng print tránh logger chưa init)
        print("[database] psycopg2 không khả dụng -> fallback SQLite test.db cho môi trường test.")
        DATABASE_URL = "sqlite:///./test.db"

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

        # Ensure shortlinks table exists (very small table) -- create minimal if metadata.create_all missed
        try:
            if 'shortlinks' not in inspector.get_table_names():
                if engine.dialect.name == 'postgresql':
                    conn.execute(text(
                        """
                        CREATE TABLE IF NOT EXISTS shortlinks (
                          token VARCHAR PRIMARY KEY,
                          affiliate_url TEXT NOT NULL,
                          created_at TIMESTAMPTZ DEFAULT NOW(),
                          last_click_at TIMESTAMPTZ NULL,
                          click_count INTEGER DEFAULT 0
                        )
                        """
                    ))
                else:
                    conn.execute(text(
                        """
                        CREATE TABLE IF NOT EXISTS shortlinks (
                          token TEXT PRIMARY KEY,
                          affiliate_url TEXT NOT NULL,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          last_click_at TIMESTAMP NULL,
                          click_count INTEGER DEFAULT 0
                        )
                        """
                    ))
        except Exception:
            pass

        # Create simple index for web_vitals (name + timestamp) if table exists and index missing
        try:
            if 'web_vitals' in inspector.get_table_names():
                # crude check for existing index name
                ix_rows = []
                if engine.dialect.name == 'postgresql':
                    ix_rows = conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename='web_vitals'"))
                # For SQLite we skip (auto fast enough) unless manual create
                names = {r[0] for r in ix_rows} if ix_rows else set()
                if engine.dialect.name == 'postgresql' and 'ix_web_vitals_name_ts' not in names:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_vitals_name_ts ON web_vitals (name, timestamp DESC)"))
        except Exception:
            pass

        # --- LEGACY CLEANUP: Drop old unique constraint (merchant, network) if it still exists ---
        # Hệ thống mới dùng unique (network, platform). Constraint cũ có thể gây lỗi UniqueViolation khi
        # auto-generate template mặc dù đã chuyển qua platform-first.
        try:
            if engine.dialect.name == "postgresql":
                # Kiểm tra tồn tại constraint uq_merchant_network
                chk = conn.execute(text(
                    """
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'affiliate_templates' AND c.conname = 'uq_merchant_network'
                    """
                )).fetchone()
                if chk:
                    conn.execute(text("ALTER TABLE affiliate_templates DROP CONSTRAINT IF EXISTS uq_merchant_network"))
            # SQLite không hỗ trợ drop constraint dễ dàng → bỏ qua an toàn.
        except Exception:
            # Không dừng startup nếu drop constraint thất bại
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
