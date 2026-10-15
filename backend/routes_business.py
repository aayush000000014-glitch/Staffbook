from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, now_iso, today, NOPID, owner_ctx, member_ctx, audit, check_img, MAX_ACTIVE_STAFF
from engine import D, r2
from services import DEFAULT_SETTINGS, sync_obligations, load_ledger, create_staff, refresh_alerts

router = APIRouter()


class SettingsIn(BaseModel):
    salary_method: str = Field(pattern="^(fixed30|calendar)$")
    schedule_type: str = Field(pattern="^(fixed_date|cycle30|cycle40)$")
    pay_day: int = Field(ge=1, le=31)
    late_fine_per_hour: float = Field(ge=0, le=100000)
    paid_leave_quota: int = Field(ge=0, le=5)
    leave_quota_period: str = Field(pattern="^(monthly|yearly)$")
    allow_future_attendance_days: int = Field(default=31, ge=0, le=90)
    carry_forward_fines: bool = False


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    logo: Optional[str] = None
    type: str = Field(default="", max_length=60)
    location: str = Field(default="", max_length=200)


class OwnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: Optional[str] = Field(default=None, max_length=120)


class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: Optional[str] = ""
    designation: Optional[str] = Field(default="", max_length=60)
    monthly_salary: float = Field(gt=0, le=10000000)
    joining_date: str
    salary_method: Optional[str] = None
    schedule_type: Optional[str] = None
    pay_day: Optional[int] = None
    cycle_start: Optional[str] = None
    photo: Optional[str] = None


class OnboardingIn(BaseModel):
    business: ProfileIn
    owner: OwnerIn
    settings: SettingsIn
    staff: List[StaffIn] = []


class BusinessUpdateIn(BaseModel):
    profile: Optional[ProfileIn] = None
    settings: Optional[SettingsIn] = None


@router.post("/onboarding")
async def onboarding(body: OnboardingIn, ctx=Depends(owner_ctx)):
    check_img(body.business.logo)
    if len(body.staff) > MAX_ACTIVE_STAFF:
        raise HTTPException(422, "Too many staff")
    await db.businesses.update_one({"id": ctx.bid}, {"$set": {
        **body.business.model_dump(), "settings": body.settings.model_dump(), "onboarded": True}})
    await db.users.update_one({"id": ctx.user["id"]}, {"$set": body.owner.model_dump()})
    settings = body.settings.model_dump()
    for s in body.staff:
        await create_staff(ctx.bid, ctx.user, s.model_dump(), settings)
    await audit(ctx.bid, ctx.user, "business.onboarded", "business", ctx.bid)
    return {"ok": True}


@router.get("/business")
async def get_business(ctx=Depends(owner_ctx)):
    b = await db.businesses.find_one({"id": ctx.bid}, {"_id": 0})
    b["settings"] = {**DEFAULT_SETTINGS, **b.get("settings", {})}
    return b


@router.put("/business")
async def update_business(body: BusinessUpdateIn, ctx=Depends(owner_ctx)):
    upd = {}
    if body.profile:
        check_img(body.profile.logo)
        upd.update(body.profile.model_dump())
    if body.settings:
        upd["settings"] = body.settings.model_dump()
    if upd:
        await db.businesses.update_one({"id": ctx.bid}, {"$set": upd})
        await audit(ctx.bid, ctx.user, "business.update", "business", ctx.bid,
                    {"fields": [k for k in upd if k != "logo"], "settings": upd.get("settings")})
    return await get_business(ctx)


@router.get("/public/businesses/{bid}")
async def public_business(bid: str):
    b = await db.businesses.find_one({"id": bid, "status": "active"}, {"_id": 0, "name": 1, "logo": 1, "type": 1, "location": 1})
    if not b:
        raise HTTPException(404, "Not found")
    return b


@router.get("/dashboard")
async def dashboard(ctx=Depends(owner_ctx)):
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid)
    t = today()
    ts = t.isoformat()
    month = ts[:7]
    active = [s for s in L.staff.values() if s["status"] == "active"]
    employed_today = [s for s in active if s["joining_date"] <= ts]
    today_ex = {a["staff_id"]: a for sid in L.att for a in L.att[sid] if a["date"] == ts}
    absent = [s for s in employed_today if today_ex.get(s["id"], {}).get("status") in ("absent", "paid_leave")]
    month_start = t.replace(day=1)
    earned = r2(sum(L.salary(s["id"], month_start, t)["earned"] for s in active))
    views = L.views()
    due_month = [v for v in views if v["due_date"][:7] == month]
    payable_month = r2(sum(v["net_payable"] for v in due_month))
    paid_month = r2(sum(x["amount"] for x in L.all_txns if x["date"][:7] == month))
    open_v = [v for v in views if v["balance"] > 0]
    overdue = [v for v in open_v if v["status"] == "overdue"]
    pending = [v for v in open_v if v["status"] != "overdue" and not v["accruing"]]
    soon_end = (t + timedelta(days=3)).isoformat()
    due_soon = [v for v in open_v if ts <= v["due_date"] <= soon_end]
    await refresh_alerts(ctx.bid, views)
    recent = []
    for x in L.all_txns[:8]:
        recent.append({**x, "staff_name": L.staff.get(x["staff_id"], {}).get("name")})
    notes = await db.notifications.find({"business_id": ctx.bid, "read": False}, NOPID).sort("created_at", -1).to_list(20)
    alerts = list(notes)
    if len(active) >= MAX_ACTIVE_STAFF - 5:
        alerts.insert(0, {"id": "capacity", "kind": "capacity", "message": f"You are using {len(active)} of {MAX_ACTIVE_STAFF} active staff slots."})
    lean = lambda vs: [{k: v[k] for k in ("id", "staff_name", "due_date", "balance", "status", "period_start", "period_end")} for v in vs]
    return {
        "active_staff": len(active), "capacity_remaining": MAX_ACTIVE_STAFF - len(active), "capacity": MAX_ACTIVE_STAFF,
        "present_today": len(employed_today) - len(absent), "absent_today": len(absent),
        "earned_till_date": earned, "payable_this_month": payable_month, "paid_this_month": paid_month,
        "pending": {"count": len(pending), "amount": r2(sum(v["balance"] for v in pending))},
        "overdue": {"count": len(overdue), "amount": r2(sum(v["balance"] for v in overdue)), "items": lean(overdue)[:10]},
        "due_soon": {"count": len(due_soon), "amount": r2(sum(v["balance"] for v in due_soon)), "items": lean(due_soon)},
        "recent_transactions": recent, "alerts": alerts, "today": ts,
    }


@router.get("/notifications")
async def notifications(ctx=Depends(owner_ctx)):
    return await db.notifications.find({"business_id": ctx.bid}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.post("/notifications/read-all")
async def read_all(ctx=Depends(owner_ctx)):
    await db.notifications.update_many({"business_id": ctx.bid}, {"$set": {"read": True}})
    return {"ok": True}


@router.get("/audit")
async def audit_list(entity_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    q = {"business_id": ctx.bid}
    if entity_id:
        q["entity_id"] = entity_id
    return await db.audit_logs.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/me/staff")
async def my_staff(ctx=Depends(member_ctx)):
    sid = ctx.user.get("staff_id")
    if ctx.user["role"] != "staff" or not sid:
        raise HTTPException(403, "Staff only")
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid, sid)
    s = L.staff[sid]
    t = today()
    return {"staff": s, "business": {"name": ctx.business["name"], "type": ctx.business.get("type")},
            "obligations": L.views(sid)[::-1], "attendance": sorted(L.att.get(sid, []), key=lambda a: a["date"], reverse=True),
            "advances": L.advance_summary(sid), "leave": L.leave_summary(sid),
            "this_month": L.salary(sid, t.replace(day=1), t),
            "transactions": [x for x in L.all_txns]}
