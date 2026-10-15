from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os  # noqa: E402
import logging  # noqa: E402
from fastapi import FastAPI, APIRouter  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from core import db, client, new_id, now_iso, hash_pw, verify_pw, norm_phone  # noqa: E402
import routes_auth, routes_business, routes_staff, routes_pay, routes_reports, routes_admin  # noqa: E402

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="StaffBook API")
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"app": "StaffBook", "ok": True}


for r in (routes_auth, routes_business, routes_staff, routes_pay, routes_reports, routes_admin):
    api.include_router(r.router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def ensure_indexes():
    await db.users.create_index("phone", unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index("staff_id")
    await db.businesses.create_index("id", unique=True)
    await db.memberships.create_index([("user_id", 1), ("business_id", 1)], unique=True)
    await db.staff.create_index("id", unique=True)
    await db.staff.create_index([("business_id", 1), ("status", 1)])
    await db.attendance.create_index([("staff_id", 1), ("date", 1)], unique=True)
    await db.attendance.create_index([("business_id", 1), ("date", 1)])
    await db.obligations.create_index("id", unique=True)
    await db.obligations.create_index([("staff_id", 1), ("period_start", 1)], unique=True)
    await db.obligations.create_index([("business_id", 1), ("due_date", 1)])
    await db.transactions.create_index("id", unique=True)
    await db.transactions.create_index("client_ref", unique=True)
    await db.transactions.create_index([("business_id", 1), ("date", 1)])
    await db.transactions.create_index("obligation_id")
    await db.advances.create_index([("business_id", 1), ("staff_id", 1)])
    await db.advance_recoveries.create_index("obligation_id", unique=True)
    await db.advance_recoveries.create_index([("business_id", 1), ("staff_id", 1)])
    await db.fines.create_index([("business_id", 1), ("staff_id", 1), ("date", 1)])
    await db.audit_logs.create_index([("business_id", 1), ("created_at", -1)])
    await db.notifications.create_index("key", unique=True)
    await db.notifications.create_index([("business_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("identifier")
    await db.sessions.create_index("token_hash", unique=True)
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("expires_at_dt", expireAfterSeconds=0)


async def migrate_cycle_due_dates():
    """Cycle due date = last (30th/40th) day of the cycle. Fix records created with the old start+N rule."""
    from datetime import date, timedelta
    async for ob in db.obligations.find({"schedule_type": {"$in": ["cycle30", "cycle40"]}}, {"_id": 0}):
        n = 30 if ob["schedule_type"] == "cycle30" else 40
        old = (date.fromisoformat(ob["period_start"]) + timedelta(days=n)).isoformat()
        if ob["original_due_date"] == old:
            new = (date.fromisoformat(ob["period_start"]) + timedelta(days=n - 1)).isoformat()
            upd = {"original_due_date": new}
            if ob["due_date"] == old:
                upd["due_date"] = new
            await db.obligations.update_one({"id": ob["id"]}, {"$set": upd})


async def seed_super_admin():
    phone = norm_phone(os.environ["SUPER_ADMIN_PHONE"])
    pw = os.environ["SUPER_ADMIN_PASSWORD"]
    email = os.environ.get("SUPER_ADMIN_EMAIL")
    u = await db.users.find_one({"phone": phone})
    if not u:
        await db.users.insert_one({"id": new_id(), "name": "Super Admin", "phone": phone, "email": email,
                                   "role": "super_admin", "business_id": None, "staff_id": None,
                                   "password_hash": hash_pw(pw), "created_at": now_iso()})
    else:
        upd = {"role": "super_admin", "business_id": None}
        if not verify_pw(pw, u["password_hash"]):
            upd["password_hash"] = hash_pw(pw)
        await db.users.update_one({"phone": phone}, {"$set": upd})


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await migrate_cycle_due_dates()
    await seed_super_admin()


@app.on_event("shutdown")
async def shutdown():
    client.close()
