from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from core import db, new_id, now_iso, today, NOPID, owner_ctx, audit
from engine import D, r2
from services import sync_obligations, load_ledger

router = APIRouter()


class PayIn(BaseModel):
    amount: float = Field(gt=0, le=10000000)
    method: str = Field(pattern="^(cash|upi|bank)$")
    date: str
    note: Optional[str] = Field(default="", max_length=300)
    client_ref: str = Field(min_length=8, max_length=64)
    advance_recovery: Optional[float] = Field(default=None, ge=0)
    renew: bool = True


class DueDateIn(BaseModel):
    due_date: str
    reason: str = Field(min_length=3, max_length=300)


class AdjustIn(BaseModel):
    advance_recovery: float = Field(ge=0)
    other_deductions: float = Field(ge=0)
    reason: str = Field(min_length=3, max_length=300)


class ReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


async def get_ob(bid, oid):
    ob = await db.obligations.find_one({"id": oid, "business_id": bid, "cancelled": {"$ne": True}}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Payment record not found")
    return ob


async def set_recovery(ctx, ob, amount: float, on_date: str):
    """Store (freeze) the advance recovery for this salary period."""
    L = await load_ledger(ctx.bid, ob["staff_id"])
    v = L.ob_view(ob)
    existing = L.recov_by_ob.get(ob["id"])
    cur = v["advance_recovery"]
    amount = r2(amount)
    if existing and abs(existing["amount"] - amount) < 0.005:
        return
    if amount > v["advance_available"] + 0.005:
        raise HTTPException(422, f"Advance recovery cannot exceed outstanding advance (₹{v['advance_available']:,.2f})")
    if amount > v["advance_max"] + 0.005:
        raise HTTPException(422, f"Advance recovery cannot exceed earned salary after fines and deductions (₹{v['advance_max']:,.2f})")
    await db.advance_recoveries.update_one(
        {"obligation_id": ob["id"]},
        {"$set": {"amount": amount, "date": on_date, "business_id": ctx.bid, "staff_id": ob["staff_id"],
                  "period_start": ob["period_start"], "period_end": ob["period_end"], "updated_at": now_iso()},
         "$setOnInsert": {"id": new_id()}}, upsert=True)
    if abs(cur - amount) >= 0.005:
        await audit(ctx.bid, ctx.user, "advance.recovery_set", "obligation", ob["id"], {"from": cur, "to": amount})


@router.get("/obligations")
async def list_obligations(status: Optional[str] = None, month: Optional[str] = None, staff_id: Optional[str] = None,
                           ctx=Depends(owner_ctx)):
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid)
    out = L.views(staff_id)
    if month:
        out = [v for v in out if v["due_date"].startswith(month)]
    if status == "open":
        out = [v for v in out if v["balance"] > 0]
    elif status:
        out = [v for v in out if v["status"] == status]
    return sorted(out, key=lambda v: v["due_date"])


@router.get("/calendar")
async def payment_calendar(month: str, ctx=Depends(owner_ctx)):
    return await list_obligations(None, month, None, ctx)


@router.get("/obligations/{oid}")
async def obligation_detail(oid: str, ctx=Depends(owner_ctx)):
    ob = await get_ob(ctx.bid, oid)
    L = await load_ledger(ctx.bid, ob["staff_id"])
    v = L.ob_view(ob)
    txns = await db.transactions.find({"obligation_id": oid, "business_id": ctx.bid}, {"_id": 0}).sort("created_at", -1).to_list(None)
    history = await db.audit_logs.find({"business_id": ctx.bid, "entity_id": {"$in": [oid] + [t["id"] for t in txns]}},
                                       {"_id": 0}).sort("created_at", -1).to_list(100)
    return {**v, "transactions": txns, "history": history,
            "advance_outstanding": L.advance_summary(ob["staff_id"])["outstanding"],
            "cycle_paused": L.staff[ob["staff_id"]].get("cycle_paused", False)}


@router.post("/obligations/{oid}/pay")
async def pay(oid: str, body: PayIn, ctx=Depends(owner_ctx)):
    ob = await get_ob(ctx.bid, oid)
    if D(body.date) > today():
        raise HTTPException(422, "Payment date cannot be in the future")
    if await db.transactions.find_one({"client_ref": body.client_ref}):
        raise HTTPException(409, "This payment was already recorded")
    if body.advance_recovery is None:
        pre = (await load_ledger(ctx.bid, ob["staff_id"])).ob_view(ob)
        body.advance_recovery = pre["advance_recovery"]
    await set_recovery(ctx, ob, body.advance_recovery, body.date)
    L = await load_ledger(ctx.bid, ob["staff_id"])
    v = L.ob_view(ob)
    if body.amount > v["balance"] + 0.005:
        raise HTTPException(422, f"Amount exceeds outstanding balance (₹{v['balance']:,.2f})")
    locked = await db.obligations.find_one_and_update({"id": oid, "version": ob.get("version", 0)}, {"$inc": {"version": 1}})
    if not locked:
        raise HTTPException(409, "This record was just updated. Please refresh and try again.")
    txn = {"id": new_id(), "business_id": ctx.bid, "staff_id": ob["staff_id"], "obligation_id": oid,
           "amount": r2(body.amount), "method": body.method, "date": body.date, "note": body.note or "",
           "period_start": ob["period_start"], "period_end": ob["period_end"], "status": "valid",
           "client_ref": body.client_ref, "created_by": ctx.user["id"], "created_at": now_iso()}
    try:
        await db.transactions.insert_one(txn)
    except DuplicateKeyError:
        raise HTTPException(409, "This payment was already recorded")
    if not body.renew:
        await db.staff.update_one({"id": ob["staff_id"], "business_id": ctx.bid}, {"$set": {"cycle_paused": True}})
    await audit(ctx.bid, ctx.user, "payment.create", "transaction", txn["id"],
                {"obligation_id": oid, "amount": txn["amount"], "method": body.method, "renew": body.renew})
    return await obligation_detail(oid, ctx)


@router.post("/obligations/{oid}/adjust")
async def adjust(oid: str, body: AdjustIn, ctx=Depends(owner_ctx)):
    ob = await get_ob(ctx.bid, oid)
    old = ob.get("other_deductions", 0)
    if abs(old - body.other_deductions) >= 0.005:
        await db.obligations.update_one({"id": oid}, {"$set": {"other_deductions": r2(body.other_deductions)}, "$inc": {"version": 1}})
        await audit(ctx.bid, ctx.user, "obligation.other_deductions", "obligation", oid,
                    {"from": old, "to": r2(body.other_deductions), "reason": body.reason})
        ob["other_deductions"] = r2(body.other_deductions)
    await set_recovery(ctx, ob, body.advance_recovery, today().isoformat())
    return await obligation_detail(oid, ctx)


@router.post("/obligations/{oid}/due-date")
async def change_due(oid: str, body: DueDateIn, ctx=Depends(owner_ctx)):
    ob = await get_ob(ctx.bid, oid)
    nd = D(body.due_date)
    if nd < D(ob["period_start"]):
        raise HTTPException(422, "Due date cannot be before the salary period starts")
    await db.obligations.update_one({"id": oid}, {"$set": {"due_date": nd.isoformat()}, "$inc": {"version": 1}})
    await audit(ctx.bid, ctx.user, "obligation.due_date", "obligation", oid,
                {"from": ob["due_date"], "to": nd.isoformat(), "reason": body.reason})
    return await obligation_detail(oid, ctx)


@router.post("/transactions/{tid}/reverse")
async def reverse_txn(tid: str, body: ReverseIn, ctx=Depends(owner_ctx)):
    res = await db.transactions.find_one_and_update(
        {"id": tid, "business_id": ctx.bid, "status": "valid"},
        {"$set": {"status": "reversed", "reversal_reason": body.reason, "reversed_by": ctx.user["id"], "reversed_at": now_iso()}})
    if not res:
        raise HTTPException(404, "Valid transaction not found")
    await db.obligations.update_one({"id": res["obligation_id"]}, {"$inc": {"version": 1}})
    await audit(ctx.bid, ctx.user, "payment.reverse", "transaction", tid,
                {"obligation_id": res["obligation_id"], "amount": res["amount"], "reason": body.reason})
    return {"ok": True}


@router.get("/transactions")
async def list_txns(month: Optional[str] = None, ctx=Depends(owner_ctx)):
    q = {"business_id": ctx.bid}
    if month:
        q["date"] = {"$regex": f"^{month}"}
    txns = await db.transactions.find(q, {"_id": 0}).sort("date", -1).to_list(500)
    names = {s["id"]: s["name"] for s in await db.staff.find({"business_id": ctx.bid}, {"_id": 0, "id": 1, "name": 1}).to_list(None)}
    return [{**t, "staff_name": names.get(t["staff_id"])} for t in txns]
