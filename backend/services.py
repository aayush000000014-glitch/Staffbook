from datetime import timedelta

from fastapi import HTTPException
from pymongo.errors import BulkWriteError, DuplicateKeyError

from core import db, new_id, now_iso, today, NOPID, MAX_ACTIVE_STAFF, audit, check_img
from engine import D, r2, generate_periods, unpaid_leave_dates, compute_salary

DEFAULT_SETTINGS = {
    "salary_method": "fixed30", "schedule_type": "fixed_date", "pay_day": 1, "late_fine_per_hour": 0.0,
    "paid_leave_quota": 0, "leave_quota_period": "monthly", "allow_future_attendance_days": 31,
    "carry_forward_fines": False,
}


def group(items, key):
    out = {}
    for i in items:
        out.setdefault(i[key], []).append(i)
    return out


async def sync_obligations(bid: str):
    """Create payment obligations for every salary period that has started (idempotent)."""
    t = today()
    staff_list = await db.staff.find({"business_id": bid}, {"_id": 0, "photo": 0}).to_list(None)
    for s in staff_list:
        if s.get("cycle_paused"):
            continue
        last = await db.obligations.find_one({"staff_id": s["id"], "cancelled": {"$ne": True}},
                                             {"_id": 0, "period_end": 1}, sort=[("period_end", -1)])
        periods = generate_periods(s, last["period_end"] if last else None, t)
        docs = [{
            "id": new_id(), "business_id": bid, "staff_id": s["id"], "period_start": a.isoformat(),
            "period_end": b.isoformat(), "due_date": c.isoformat(), "original_due_date": c.isoformat(),
            "monthly_salary": s["monthly_salary"], "salary_method": s["salary_method"],
            "schedule_type": s["schedule_type"], "other_deductions": 0.0, "version": 0,
            "cancelled": False, "created_at": now_iso(),
        } for a, b, c in periods]
        if docs:
            try:
                await db.obligations.insert_many(docs, ordered=False)
            except BulkWriteError:
                pass


class Ledger:
    def __init__(self, biz, staff, att, fines, advances, recov, obligations, txns):
        self.biz = biz
        self.settings = {**DEFAULT_SETTINGS, **biz.get("settings", {})}
        self.staff = staff
        self.att = group(att, "staff_id")
        self.fines = group(fines, "staff_id")
        self.advances = group(advances, "staff_id")
        self.recov_by_ob = {r["obligation_id"]: r for r in recov}
        self.recov = group(recov, "staff_id")
        self.obligations = obligations
        self.txns = group(txns, "obligation_id")
        self.all_txns = txns
        self._unpaid = {}
        self._alloc = {}

    def unpaid(self, sid):
        if sid not in self._unpaid:
            dates = [D(a["date"]) for a in self.att.get(sid, []) if a["status"] == "paid_leave"]
            self._unpaid[sid] = unpaid_leave_dates(dates, int(self.settings["paid_leave_quota"]),
                                                   self.settings["leave_quota_period"])
        return self._unpaid[sid]

    def salary(self, sid, start, end, salary=None, method=None):
        s = self.staff[sid]
        return compute_salary(salary or s["monthly_salary"], method or s["salary_method"], start, end,
                              s["joining_date"], s.get("leaving_date"), self.att.get(sid, []), self.unpaid(sid))

    def alloc(self, sid):
        """Walk a staff member's salary periods in order, applying fines, other deductions and
        advance recoveries without ever exceeding earned salary; carries excess advances forward."""
        if sid in self._alloc:
            return self._alloc[sid]
        t = today()
        obs = sorted([o for o in self.obligations if o["staff_id"] == sid and not o.get("cancelled")],
                     key=lambda o: o["period_start"])
        advs = self.advances.get(sid, [])
        carry_ok = bool(self.settings.get("carry_forward_fines"))
        out, allocated, fixed, carry = {}, 0.0, 0.0, 0.0
        for ob in obs:
            ps, pe = ob["period_start"], ob["period_end"]
            accruing = D(pe) >= t
            cutoff = min(D(pe), t)
            if D(ps) > t:
                cutoff = D(ps) - timedelta(days=1)
            br = self.salary(sid, ps, cutoff, ob["monthly_salary"], ob["salary_method"])
            earned = br["earned"]
            manual = r2(sum(f["amount"] for f in self.fines.get(sid, []) if ps <= f["date"] <= pe))
            carry_in = carry
            fine_due = r2(br["late_fines"] + manual + carry_in)
            fines_applied = r2(min(fine_due, earned))
            excess = r2(fine_due - fines_applied)
            room = r2(earned - fines_applied)
            other = r2(min(ob.get("other_deductions") or 0, room))
            room = r2(room - other)
            adv_avail = r2(max(sum(a["amount"] for a in advs if a["date"] <= pe) - allocated, 0))
            rec = self.recov_by_ob.get(ob["id"])
            if rec:
                adv, mode = r2(min(rec["amount"], room, adv_avail)), "fixed"
                fixed = r2(fixed + adv)
            elif self.txns.get(ob["id"]):
                adv, mode = 0.0, "legacy"
            else:
                adv, mode = r2(min(adv_avail, room)), "auto"
            allocated = r2(allocated + adv)
            carry = excess if (carry_ok and not accruing) else 0.0
            out[ob["id"]] = {"br": br, "manual": manual, "carry_in": carry_in, "fine_due": fine_due,
                             "fines_applied": fines_applied, "fines_carried_out": carry,
                             "fines_not_deducted": r2(excess - carry), "other": other, "adv": adv,
                             "adv_avail": adv_avail, "adv_room": room, "adv_mode": mode, "accruing": accruing,
                             "period_start": ps, "period_end": pe}
        total_adv = r2(sum(a["amount"] for a in advs))
        self._alloc[sid] = {"by_ob": out, "allocated": allocated, "fixed": fixed, "total_adv": total_adv}
        return self._alloc[sid]

    def ob_view(self, ob):
        t = today()
        sid = ob["staff_id"]
        s = self.staff.get(sid, {})
        a = self.alloc(sid)["by_ob"][ob["id"]]
        br, accruing, manual, adv, other = a["br"], a["accruing"], a["manual"], a["adv"], a["other"]
        total_ded = r2(a["fines_applied"] + other + adv)
        net = r2(max(br["earned"] - total_ded, 0))
        txns = self.txns.get(ob["id"], [])
        paid = r2(sum(x["amount"] for x in txns))
        balance = r2(net - paid)
        due = D(ob["due_date"])
        if (paid > 0 and balance <= 0) or (not accruing and net == 0):
            status = "paid"
        elif due < t:
            status = "overdue"
        elif paid > 0:
            status = "partially_paid"
        else:
            status = "pending"
        return {**{k: ob.get(k) for k in ("id", "staff_id", "period_start", "period_end", "due_date",
                                          "original_due_date", "monthly_salary", "salary_method",
                                          "schedule_type", "cancelled")},
                "staff_name": s.get("name"), "designation": s.get("designation"), "staff_status": s.get("status"),
                "breakdown": br, "manual_fines": manual, "late_fines": br["late_fines"],
                "fines_carried_in": a["carry_in"], "fines_deducted": a["fines_applied"],
                "fines_carried_out": a["fines_carried_out"], "fines_not_deducted": a["fines_not_deducted"],
                "advance_recovery": adv, "advance_mode": a["adv_mode"], "advance_available": a["adv_avail"],
                "advance_max": r2(min(a["adv_avail"], a["adv_room"])), "other_deductions": other,
                "total_deductions": total_ded, "net_payable": net, "paid": paid, "balance": max(balance, 0.0), "overpaid": max(-balance, 0.0),
                "status": status, "accruing": accruing, "partially_paid": paid > 0 and balance > 0,
                "transactions_count": len(txns)}

    def views(self, staff_id=None):
        return [self.ob_view(o) for o in self.obligations
                if not o.get("cancelled") and (staff_id is None or o["staff_id"] == staff_id)]

    def adv_recovered_in_month(self, sid, month):
        return r2(sum(a["adv"] for a in self.alloc(sid)["by_ob"].values() if a["period_end"][:7] == month))

    def allocations(self, sid):
        return [{"obligation_id": oid, "period_start": a["period_start"], "period_end": a["period_end"],
                 "amount": a["adv"], "mode": a["adv_mode"]}
                for oid, a in sorted(self.alloc(sid)["by_ob"].items(), key=lambda x: x[1]["period_start"], reverse=True)
                if a["adv"] > 0]

    def advance_summary(self, sid):
        al = self.alloc(sid)
        month = today().strftime("%Y-%m")
        cur = [a["adv"] for a in al["by_ob"].values() if a["accruing"] or a["period_end"][:7] == month]
        return {"total": al["total_adv"], "recovered": al["allocated"], "recovered_paid": al["fixed"],
                "outstanding": r2(max(al["total_adv"] - al["allocated"], 0)), "recovered_this_month": r2(sum(cur))}

    def leave_summary(self, sid):
        t = today()
        quota = int(self.settings["paid_leave_quota"])
        per = self.settings["leave_quota_period"]
        key = t.strftime("%Y-%m") if per == "monthly" else str(t.year)
        taken = [a for a in self.att.get(sid, []) if a["status"] == "paid_leave" and a["date"].startswith(key)]
        unpaid = self.unpaid(sid)
        unpaid_n = sum(1 for a in taken if D(a["date"]) in unpaid)
        return {"quota": quota, "period": per, "taken": len(taken), "paid": len(taken) - unpaid_n,
                "unpaid": unpaid_n, "remaining": max(quota - (len(taken) - unpaid_n), 0)}


async def load_ledger(bid: str, staff_id: str = None) -> Ledger:
    q = {"business_id": bid}
    sq = {"business_id": bid}
    if staff_id:
        q["staff_id"] = staff_id
        sq["id"] = staff_id
    biz = await db.businesses.find_one({"id": bid}, {"_id": 0, "logo": 0})
    staff = {s["id"]: s for s in await db.staff.find(sq, {"_id": 0, "photo": 0}).to_list(None)}
    att = await db.attendance.find(q, NOPID).to_list(None)
    fines = await db.fines.find({**q, "status": "active"}, NOPID).to_list(None)
    advances = await db.advances.find({**q, "status": "active"}, NOPID).to_list(None)
    recov = await db.advance_recoveries.find(q, NOPID).to_list(None)
    obs = await db.obligations.find(q, NOPID).sort("period_start", 1).to_list(None)
    txns = await db.transactions.find({**q, "status": "valid"}, NOPID).sort("date", -1).to_list(None)
    return Ledger(biz, staff, att, fines, advances, recov, obs, txns)


async def ensure_period_open(bid, staff_id, d: str):
    """Block edits that would change a fully paid salary period."""
    ob = await db.obligations.find_one({"business_id": bid, "staff_id": staff_id, "cancelled": {"$ne": True},
                                        "period_start": {"$lte": d}, "period_end": {"$gte": d}}, NOPID)
    if not ob:
        return
    L = await load_ledger(bid, staff_id)
    v = L.ob_view(ob)
    if v["status"] == "paid" and v["paid"] > 0:
        raise HTTPException(409, "This salary period is already fully paid. Reverse the payment first to make changes.")


def staff_doc_from(data: dict, settings: dict) -> dict:
    s = {**DEFAULT_SETTINGS, **settings}
    check_img(data.get("photo"))
    doc = {
        "name": data["name"].strip(), "phone": data.get("phone") or "", "designation": data.get("designation") or "",
        "monthly_salary": r2(data["monthly_salary"]), "joining_date": data["joining_date"],
        "salary_method": data.get("salary_method") or s["salary_method"],
        "schedule_type": data.get("schedule_type") or s["schedule_type"],
        "pay_day": int(data.get("pay_day") or s["pay_day"]), "cycle_start": data.get("cycle_start") or None,
        "photo": data.get("photo") or None,
    }
    if doc["salary_method"] not in ("fixed30", "calendar"):
        raise HTTPException(422, "Invalid salary method")
    if doc["schedule_type"] not in ("fixed_date", "cycle30", "cycle40"):
        raise HTTPException(422, "Invalid payment schedule")
    if not 1 <= doc["pay_day"] <= 31:
        raise HTTPException(422, "Payment date must be between 1 and 31")
    if doc["monthly_salary"] <= 0:
        raise HTTPException(422, "Monthly salary must be greater than 0")
    D(doc["joining_date"])
    if doc["cycle_start"] and D(doc["cycle_start"]) < D(doc["joining_date"]):
        raise HTTPException(422, "Cycle start cannot be before joining date")
    return doc


async def create_staff(ctx_bid: str, user: dict, data: dict, settings: dict) -> dict:
    doc = staff_doc_from(data, settings)
    biz = await db.businesses.find_one_and_update(
        {"id": ctx_bid, "active_staff_count": {"$lt": MAX_ACTIVE_STAFF}}, {"$inc": {"active_staff_count": 1}})
    if not biz:
        raise HTTPException(409, f"Active staff limit reached ({MAX_ACTIVE_STAFF}). Mark former staff as left first.")
    doc.update({"id": new_id(), "business_id": ctx_bid, "status": "active", "leaving_date": None,
                "cycle_paused": False, "user_id": None, "created_at": now_iso()})
    try:
        await db.staff.insert_one(doc)
    except DuplicateKeyError:
        await db.businesses.update_one({"id": ctx_bid}, {"$inc": {"active_staff_count": -1}})
        raise HTTPException(409, "Duplicate staff record")
    doc.pop("_id", None)
    await audit(ctx_bid, user, "staff.create", "staff", doc["id"], {"name": doc["name"]})
    return doc


async def refresh_alerts(bid: str, views: list):
    t = today()
    for v in views:
        if v["balance"] <= 0:
            continue
        due = D(v["due_date"])
        if due < t:
            kind, msg = "overdue", f"Salary of ₹{v['balance']:,.2f} for {v['staff_name']} is overdue since {due.strftime('%d %b')}"
        elif (due - t).days <= 3:
            kind, msg = "due_soon", f"Salary of ₹{v['balance']:,.2f} for {v['staff_name']} is due on {due.strftime('%d %b')}"
        else:
            continue
        await db.notifications.update_one(
            {"key": f"{v['id']}:{kind}:{v['due_date']}"},
            {"$setOnInsert": {"id": new_id(), "business_id": bid, "kind": kind, "message": msg,
                              "obligation_id": v["id"], "read": False, "created_at": now_iso()}},
            upsert=True)
