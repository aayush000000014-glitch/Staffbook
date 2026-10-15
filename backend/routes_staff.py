from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from core import db, new_id, now_iso, today, NOPID, owner_ctx, audit, hash_pw, norm_phone
from engine import D, r2
from routes_business import StaffIn
from services import sync_obligations, load_ledger, create_staff, staff_doc_from, ensure_period_open, DEFAULT_SETTINGS

router = APIRouter()


class LeaveIn(BaseModel):
    leaving_date: str
    reason: Optional[str] = Field(default="", max_length=300)


class StaffLoginIn(BaseModel):
    phone: str
    password: str = Field(min_length=8, max_length=128)


class AttendanceIn(BaseModel):
    staff_id: str
    date: str
    status: str = Field(pattern="^(absent|half_day|paid_leave|late)$")
    hours_late: Optional[float] = Field(default=0, ge=0, le=24)
    note: Optional[str] = Field(default="", max_length=200)


class AdvanceIn(BaseModel):
    staff_id: str
    amount: float = Field(gt=0, le=10000000)
    date: str
    description: Optional[str] = Field(default="", max_length=300)


class FineIn(BaseModel):
    staff_id: str
    amount: float = Field(gt=0, le=10000000)
    date: str
    reason: str = Field(min_length=2, max_length=300)


class ReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


async def get_staff(bid, sid, projection=None):
    s = await db.staff.find_one({"id": sid, "business_id": bid}, projection or {"_id": 0})
    if not s:
        raise HTTPException(404, "Staff not found")
    return s


def check_in_employment(s, d: str):
    dd = D(d)
    if dd < D(s["joining_date"]):
        raise HTTPException(422, "Date is before the staff's joining date")
    if s.get("leaving_date") and dd > D(s["leaving_date"]):
        raise HTTPException(422, "Date is after the staff's leaving date")


@router.get("/staff")
async def list_staff(status: str = "active", q: str = "", designation: str = "", ctx=Depends(owner_ctx)):
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid)
    views = L.views()
    due = {}
    for v in views:
        if not v["accruing"]:
            due[v["staff_id"]] = due.get(v["staff_id"], 0) + v["balance"]
    out = []
    for s in sorted(L.staff.values(), key=lambda x: x["name"].lower()):
        if status != "all" and s["status"] != status:
            continue
        if q and q.lower() not in (s["name"] + " " + s.get("designation", "") + " " + s.get("phone", "")).lower():
            continue
        if designation and s.get("designation", "").lower() != designation.lower():
            continue
        out.append({**s, "outstanding": r2(due.get(s["id"], 0)), "advance_outstanding": L.advance_summary(s["id"])["outstanding"]})
    return out


@router.post("/staff")
async def add_staff(body: StaffIn, ctx=Depends(owner_ctx)):
    return await create_staff(ctx.bid, ctx.user, body.model_dump(), ctx.settings)


@router.get("/staff/{sid}")
async def staff_profile(sid: str, ctx=Depends(owner_ctx)):
    await get_staff(ctx.bid, sid)
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid, sid)
    s = await get_staff(ctx.bid, sid)
    t = today()
    views = L.views(sid)
    adv = await db.advances.find({"business_id": ctx.bid, "staff_id": sid}, {"_id": 0}).sort("date", -1).to_list(None)
    fines = await db.fines.find({"business_id": ctx.bid, "staff_id": sid}, {"_id": 0}).sort("date", -1).to_list(None)
    txns = await db.transactions.find({"business_id": ctx.bid, "staff_id": sid}, {"_id": 0}).sort("date", -1).to_list(None)
    recs = L.allocations(sid)
    login = await db.users.find_one({"staff_id": sid, "business_id": ctx.bid}, {"_id": 0, "phone": 1})
    month_end = min(t, D(s["leaving_date"])) if s.get("leaving_date") else t
    settlement = None
    if s["status"] == "former":
        settlement = {"net_total": r2(sum(v["net_payable"] for v in views)), "paid_total": r2(sum(v["paid"] for v in views)),
                      "balance": r2(sum(v["balance"] for v in views)), "advance_outstanding": L.advance_summary(sid)["outstanding"]}
    return {"staff": s, "obligations": views[::-1], "attendance": sorted(L.att.get(sid, []), key=lambda a: a["date"], reverse=True),
            "advances": adv, "advance_summary": L.advance_summary(sid), "recoveries": recs, "fines": fines,
            "transactions": txns, "leave": L.leave_summary(sid), "this_month": L.salary(sid, t.replace(day=1), month_end),
            "login_phone": login["phone"] if login else None, "settlement": settlement,
            "outstanding": r2(sum(v["balance"] for v in views if not v["accruing"])),
            "accruing_balance": r2(sum(v["balance"] for v in views if v["accruing"]))}


@router.put("/staff/{sid}")
async def update_staff(sid: str, body: StaffIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, sid)
    doc = staff_doc_from(body.model_dump(), ctx.settings)
    if doc["joining_date"] != s["joining_date"] and await db.obligations.find_one({"staff_id": sid, "cancelled": {"$ne": True}}):
        raise HTTPException(409, "Joining date cannot change after salary periods have started")
    if body.photo is None:
        doc.pop("photo")
    await db.staff.update_one({"id": sid, "business_id": ctx.bid}, {"$set": doc})
    changes = {k: [s.get(k), doc[k]] for k in doc if k != "photo" and s.get(k) != doc[k]}
    await audit(ctx.bid, ctx.user, "staff.update", "staff", sid, changes)
    return await get_staff(ctx.bid, sid)


@router.post("/staff/{sid}/leave")
async def mark_left(sid: str, body: LeaveIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, sid)
    if s["status"] != "active":
        raise HTTPException(409, "Staff is already marked as left")
    ld = D(body.leaving_date)
    if ld < D(s["joining_date"]):
        raise HTTPException(422, "Leaving date cannot be before joining date")
    later = await db.obligations.find({"staff_id": sid, "business_id": ctx.bid, "period_start": {"$gt": body.leaving_date},
                                       "cancelled": {"$ne": True}}, NOPID).to_list(None)
    for ob in later:
        if await db.transactions.find_one({"obligation_id": ob["id"], "status": "valid"}):
            raise HTTPException(409, "Payments exist for a period after this leaving date. Reverse them first.")
    res = await db.staff.update_one({"id": sid, "business_id": ctx.bid, "status": "active"},
                                    {"$set": {"status": "former", "leaving_date": body.leaving_date}})
    if res.modified_count != 1:
        raise HTTPException(409, "Staff is already marked as left")
    await db.businesses.update_one({"id": ctx.bid}, {"$inc": {"active_staff_count": -1}})
    if later:
        await db.obligations.update_many({"id": {"$in": [o["id"] for o in later]}}, {"$set": {"cancelled": True}})
    await db.obligations.update_many({"staff_id": sid, "business_id": ctx.bid, "period_start": {"$lte": body.leaving_date},
                                      "period_end": {"$gt": body.leaving_date}}, {"$set": {"period_end": body.leaving_date}})
    await db.users.update_many({"staff_id": sid, "business_id": ctx.bid}, {"$set": {"disabled": True}})
    await audit(ctx.bid, ctx.user, "staff.left", "staff", sid, {"leaving_date": body.leaving_date, "reason": body.reason})
    return {"ok": True}


@router.post("/staff/{sid}/resume-cycle")
async def resume_cycle(sid: str, ctx=Depends(owner_ctx)):
    await get_staff(ctx.bid, sid)
    await db.staff.update_one({"id": sid, "business_id": ctx.bid}, {"$set": {"cycle_paused": False}})
    await audit(ctx.bid, ctx.user, "staff.cycle_resumed", "staff", sid)
    return {"ok": True}


@router.post("/staff/{sid}/login")
async def staff_login(sid: str, body: StaffLoginIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, sid)
    if s["status"] != "active":
        raise HTTPException(409, "Former staff cannot get a login")
    phone = norm_phone(body.phone)
    existing = await db.users.find_one({"phone": phone}, NOPID)
    if existing and existing.get("staff_id") != sid:
        raise HTTPException(409, "This mobile number is already registered")
    if existing:
        await db.users.update_one({"id": existing["id"]}, {"$set": {"password_hash": hash_pw(body.password), "disabled": False}})
    else:
        uid = new_id()
        await db.users.insert_one({"id": uid, "name": s["name"], "phone": phone, "email": None, "role": "staff",
                                   "business_id": ctx.bid, "staff_id": sid, "password_hash": hash_pw(body.password),
                                   "created_at": now_iso()})
        await db.memberships.insert_one({"id": new_id(), "user_id": uid, "business_id": ctx.bid, "role": "staff", "created_at": now_iso()})
    await audit(ctx.bid, ctx.user, "staff.login_set", "staff", sid, {"phone": phone})
    return {"ok": True, "phone": phone}


@router.get("/attendance")
async def list_attendance(month: str, staff_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    q = {"business_id": ctx.bid, "date": {"$regex": f"^{month}"}}
    if staff_id:
        q["staff_id"] = staff_id
    return await db.attendance.find(q, {"_id": 0}).to_list(None)


@router.put("/attendance")
async def set_attendance(body: AttendanceIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, body.staff_id)
    check_in_employment(s, body.date)
    limit = int({**DEFAULT_SETTINGS, **ctx.settings}["allow_future_attendance_days"])
    if (D(body.date) - today()).days > limit:
        raise HTTPException(422, f"Attendance can be recorded at most {limit} days ahead")
    if body.status == "late" and not body.hours_late:
        raise HTTPException(422, "Enter hours late")
    await ensure_period_open(ctx.bid, body.staff_id, body.date)
    rate = float({**DEFAULT_SETTINGS, **ctx.settings}["late_fine_per_hour"])
    hours = float(body.hours_late or 0) if body.status == "late" else 0
    prev = await db.attendance.find_one({"staff_id": body.staff_id, "date": body.date}, NOPID)
    doc = {"status": body.status, "hours_late": hours, "fine_rate": rate if hours else 0,
           "fine_amount": r2(hours * rate), "note": body.note or "", "updated_at": now_iso()}
    await db.attendance.update_one({"business_id": ctx.bid, "staff_id": body.staff_id, "date": body.date},
                                   {"$set": doc, "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
    await audit(ctx.bid, ctx.user, "attendance.update" if prev else "attendance.create", "attendance", body.staff_id,
                {"date": body.date, "from": prev and prev["status"], "to": body.status, "hours_late": hours})
    return await db.attendance.find_one({"staff_id": body.staff_id, "date": body.date}, {"_id": 0})


@router.delete("/attendance/{sid}/{d}")
async def clear_attendance(sid: str, d: str, ctx=Depends(owner_ctx)):
    await get_staff(ctx.bid, sid)
    await ensure_period_open(ctx.bid, sid, d)
    prev = await db.attendance.find_one_and_delete({"business_id": ctx.bid, "staff_id": sid, "date": d})
    if not prev:
        raise HTTPException(404, "No exception recorded for this date")
    await audit(ctx.bid, ctx.user, "attendance.cleared", "attendance", sid, {"date": d, "was": prev["status"]})
    return {"ok": True}


@router.get("/advances")
async def list_advances(staff_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    q = {"business_id": ctx.bid}
    if staff_id:
        q["staff_id"] = staff_id
    return await db.advances.find(q, {"_id": 0}).sort("date", -1).to_list(None)


@router.post("/advances")
async def add_advance(body: AdvanceIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, body.staff_id)
    check_in_employment(s, body.date)
    doc = {"id": new_id(), "business_id": ctx.bid, **body.model_dump(), "amount": r2(body.amount),
           "status": "active", "created_by": ctx.user["id"], "created_at": now_iso()}
    await db.advances.insert_one(doc)
    await audit(ctx.bid, ctx.user, "advance.create", "advance", doc["id"], {"staff_id": body.staff_id, "amount": doc["amount"]})
    doc.pop("_id", None)
    return doc


@router.post("/advances/{aid}/reverse")
async def reverse_advance(aid: str, body: ReverseIn, ctx=Depends(owner_ctx)):
    a = await db.advances.find_one({"id": aid, "business_id": ctx.bid, "status": "active"}, NOPID)
    if not a:
        raise HTTPException(404, "Active advance not found")
    L = await load_ledger(ctx.bid, a["staff_id"])
    summ = L.advance_summary(a["staff_id"])
    if summ["total"] - a["amount"] < summ["recovered_paid"] - 0.001:
        raise HTTPException(409, "Part of this advance was already recovered from salary. Adjust those recoveries first.")
    await db.advances.update_one({"id": aid}, {"$set": {"status": "reversed", "reversal_reason": body.reason, "reversed_at": now_iso()}})
    await audit(ctx.bid, ctx.user, "advance.reverse", "advance", aid, {"reason": body.reason, "amount": a["amount"]})
    return {"ok": True}


@router.get("/fines")
async def list_fines(staff_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    q = {"business_id": ctx.bid}
    if staff_id:
        q["staff_id"] = staff_id
    return await db.fines.find(q, {"_id": 0}).sort("date", -1).to_list(None)


@router.post("/fines")
async def add_fine(body: FineIn, ctx=Depends(owner_ctx)):
    s = await get_staff(ctx.bid, body.staff_id)
    check_in_employment(s, body.date)
    await ensure_period_open(ctx.bid, body.staff_id, body.date)
    doc = {"id": new_id(), "business_id": ctx.bid, **body.model_dump(), "amount": r2(body.amount),
           "status": "active", "created_by": ctx.user["id"], "created_at": now_iso()}
    try:
        await db.fines.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Duplicate fine")
    await audit(ctx.bid, ctx.user, "fine.create", "fine", doc["id"], {"staff_id": body.staff_id, "amount": doc["amount"], "reason": body.reason})
    doc.pop("_id", None)
    return doc


@router.post("/fines/{fid}/reverse")
async def reverse_fine(fid: str, body: ReverseIn, ctx=Depends(owner_ctx)):
    f = await db.fines.find_one({"id": fid, "business_id": ctx.bid, "status": "active"}, NOPID)
    if not f:
        raise HTTPException(404, "Active fine not found")
    await ensure_period_open(ctx.bid, f["staff_id"], f["date"])
    await db.fines.update_one({"id": fid}, {"$set": {"status": "reversed", "reversal_reason": body.reason, "reversed_at": now_iso()}})
    await audit(ctx.bid, ctx.user, "fine.reverse", "fine", fid, {"reason": body.reason, "amount": f["amount"]})
    return {"ok": True}
