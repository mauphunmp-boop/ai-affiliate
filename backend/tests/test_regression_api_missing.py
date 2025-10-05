import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

fastapi = pytest.importorskip(
    "fastapi", reason="FastAPI not installed in this test environment"
)
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from database import Base
import models, crud, schemas


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as s:
        yield s


def test_upsert_campaign_preserves_existing_when_placeholder(db):
    # Seed with real values
    crud.upsert_campaign(
        db,
        schemas.CampaignCreate(
            campaign_id="CAMPX",
            merchant="tikivn",
            name="Tiki",
            status="running",
            approval="manual",
            start_time="2025-01-01",
            end_time="2025-12-31",
            user_registration_status="APPROVED",
        ),
    )

    # Attempt to overwrite with placeholders
    crud.upsert_campaign(
        db,
        schemas.CampaignCreate(
            campaign_id="CAMPX",
            merchant="API_MISSING",
            name="NO_DATA",
            status="",
            approval=None,
            start_time="API_MISSING",
            end_time="NO_DATA",
            user_registration_status=None,
        ),
    )

    row = crud.get_campaign_by_cid(db, "CAMPX")
    assert row is not None
    assert row.merchant == "tikivn"
    assert row.name == "Tiki"
    assert row.status == "running"
    assert row.start_time == "2025-01-01"
    assert row.end_time == "2025-12-31"
    # user status should remain APPROVED
    assert (row.user_registration_status or "").upper() == "APPROVED"
