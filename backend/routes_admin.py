from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, admin_user, audit

router = APIRouter(prefix="/admin")


class StatusIn(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=300)


@router.get("/stats")
async def stats(user=Depends(admin_user)):
    total = await db.businesses.count_documents({})
    active = await db.businesses.count_documents({"status": "active"})
    staff = await db.staff.count_documents({"status": "active"})
    return {"total_businesses": total, "active_businesses": active, "inactive_businesses": total - active,
            "total_staff": staff, "total_staff_all": await db.staff.count_documents({})}


@router.get("/businesses")
async def businesses(user=Depends(admin_user)):
    bs = await db.businesses.find({}, {"_id": 0, "logo": 0, "settings": 0}).sort("created_at", -1).to_list(None)
    owners = {u["id"]: u for u in await db.users.find({"role": "owner"}, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(None)}
    counts = {c["_id"]: c["n"] for c in await db.staff.aggregate(
        [{"$match": {"status": "active"}}, {"$group": {"_id": "$business_id", "n": {"$sum": 1}}}]).to_list(None)}
    return [{**b, "owner_name": owners.get(b["owner_user_id"], {}).get("name"),
             "owner_phone": owners.get(b["owner_user_id"], {}).get("phone"), "active_staff": counts.get(b["id"], 0)} for b in bs]


@router.post("/businesses/{bid}/status")
async def set_status(bid: str, body: StatusIn, user=Depends(admin_user)):
    new = "active" if body.active else "inactive"
    res = await db.businesses.update_one({"id": bid}, {"$set": {"status": new}})
    if res.matched_count != 1:
        raise HTTPException(404, "Business not found")
    await audit(None, user, f"admin.business_{new}", "business", bid, {"reason": body.reason})
    return {"ok": True, "status": new}


@router.get("/audit")
async def admin_audit(user=Depends(admin_user)):
    return await db.audit_logs.find({"action": {"$regex": "^admin\\."}}, {"_id": 0}).sort("created_at", -1).to_list(200)
