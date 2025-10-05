#!/usr/bin/env python3
"""
Backfill user_registration_status for Campaigns that are currently NULL/empty.

Logic:
- Find campaigns where user_registration_status is NULL or ''
- For each, call fetch_campaign_detail and extract user status from:
  user_registration_status | publisher_status | user_status | approval (successful/pending/unregistered)
- Normalize: strip().upper(); map SUCCESSFUL -> APPROVED
- Upsert back to DB; avoid clobbering with None (crud is already guarded)
- Print before/after summary to verify that NULL bucket goes to 0

Usage:
  AT_MOCK=1 python backend/scripts/fix_null_user_status.py
"""
import os
import sys
import json
from pathlib import Path
from collections import Counter

# Ensure we can import backend modules when running from repo root
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, Base, engine
import models, crud, schemas
from accesstrade_service import fetch_campaign_detail

# Prefer mock if real API not configured
os.environ.setdefault("AT_MOCK", "1")
# Use a local SQLite DB by default to avoid requiring Postgres when running this script
os.environ.setdefault("DATABASE_URL", "sqlite:///backend/dev.sqlite3")


def norm_user_status(val):
    if val is None:
        return None
    s = str(val).strip().upper()
    if not s:
        return None
    if s == "SUCCESSFUL":
        return "APPROVED"
    return s


def current_summary(db):
    rows = db.query(
        models.Campaign.status, models.Campaign.user_registration_status
    ).all()
    total = len(rows)
    by_status = Counter()
    by_user = Counter()
    for st, us in rows:
        by_status[st or "NULL"] += 1
        eff = norm_user_status(us) or "NULL"
        by_user[eff] += 1
    return {
        "total": total,
        "by_status": dict(sorted(by_status.items())),
        "by_user_status": dict(sorted(by_user.items())),
    }


def main():
    # Ensure tables exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    db = SessionLocal()
    try:
        print("Before:")
        print(json.dumps(current_summary(db), ensure_ascii=False, indent=2))

        targets = (
            db.query(models.Campaign)
            .filter(
                (models.Campaign.user_registration_status.is_(None))
                | (models.Campaign.user_registration_status == "")
            )
            .all()
        )
        fixed = 0
        for c in targets:
            # Call async function safely
            import asyncio

            camp = asyncio.run(fetch_campaign_detail(db, c.campaign_id))
            if not camp:
                continue
            # Extract user status
            user_raw = (
                camp.get("user_registration_status")
                or camp.get("publisher_status")
                or camp.get("user_status")
            )
            if not user_raw:
                appr = camp.get("approval")
                if isinstance(appr, str) and appr.lower() in (
                    "successful",
                    "pending",
                    "unregistered",
                ):
                    user_raw = (
                        "APPROVED" if appr.lower() == "successful" else appr.upper()
                    )
            eff = norm_user_status(user_raw)
            if not eff:
                continue
            # Upsert back
            crud.upsert_campaign(
                db,
                schemas.CampaignCreate(
                    campaign_id=c.campaign_id,
                    merchant=c.merchant,
                    name=c.name,
                    status=c.status,
                    approval=c.approval,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    user_registration_status=eff,
                ),
            )
            fixed += 1

        print(f"Updated campaigns: {fixed}")
        print("After:")
        print(json.dumps(current_summary(db), ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
