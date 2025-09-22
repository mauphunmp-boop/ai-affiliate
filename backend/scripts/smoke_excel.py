#!/usr/bin/env python3
"""
Smoke script: run export-template and export-excel against the FastAPI app using SQLite in-memory,
so Postgres is not required. Saves output files into ./smoke_out/.

Usage:
  python scripts/smoke_excel.py
"""
import os
import io
import sys
from pathlib import Path

# Force SQLite before importing app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Add backend root to path and import app
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from fastapi.testclient import TestClient
from main import app, get_db
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from database import Base
import crud, schemas


def bootstrap_sqlite():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.TestingSessionLocal = TestingSessionLocal
    return TestClient(app)


def seed_minimal(client: TestClient):
    # seed a running + APPROVED campaign so exports have sensible data
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CAMP_OK",
            merchant="tikivn",
            name="Tiki",
            status="running",
            user_registration_status="APPROVED",
        ))
        # a couple of offers from different sources
        for idx, src in enumerate(["datafeeds", "top_products", "promotions", "manual", "excel"], start=1):
            crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
                source="accesstrade" if src != "excel" else "excel",
                source_id=f"smoke-{src}-{idx}",
                merchant="tikivn",
                title=f"SP {src.upper()} {idx}",
                url=f"https://tiki.vn/{idx}",
                affiliate_url=None,
                image_url=None,
                price=100000*idx,
                currency="VND",
                campaign_id="CAMP_OK",
                source_type=src,
                extra=None,
            ))


def main():
    outdir = BASE_DIR / "smoke_out"
    outdir.mkdir(parents=True, exist_ok=True)

    client = bootstrap_sqlite()
    seed_minimal(client)

    # export template
    r1 = client.get("/offers/export-template")
    r1.raise_for_status()
    (outdir / "offers_template.xlsx").write_bytes(r1.content)
    print("Saved:", outdir / "offers_template.xlsx")

    # export excel
    r2 = client.get("/offers/export-excel")
    r2.raise_for_status()
    (outdir / "offers_export.xlsx").write_bytes(r2.content)
    print("Saved:", outdir / "offers_export.xlsx")


if __name__ == "__main__":
    main()
