import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import db, today, owner_ctx
from engine import D, r2, dim
from services import sync_obligations, load_ledger

router = APIRouter()

KINDS = {
    "attendance": "Monthly Attendance Report", "salary_sheet": "Monthly Salary Sheet",
    "employee": "Employee Salary History", "paid": "Paid Payments Report", "pending": "Pending Payments Report",
    "overdue": "Overdue Payments Report", "advances": "Advance & Deduction Report", "settlement": "Former Staff Settlement Report",
}
M = True


def col(key, label, money=False):
    return {"key": key, "label": label, "money": money}


OB_COLS = [col("staff_name", "Staff"), col("period", "Salary Period"), col("due_date", "Due Date"),
           col("gross", "Gross", M), col("attendance_deduction", "Attendance Ded.", M), col("earned", "Earned", M),
           col("late_fines", "Late Fines", M), col("manual_fines", "Manual Fines", M),
           col("fines_deducted", "Fines Deducted", M), col("advance_recovery", "Advance Rec.", M),
           col("other_deductions", "Other Ded.", M), col("total_deductions", "Total Ded.", M),
           col("net_payable", "Net Payable", M), col("paid", "Paid", M), col("balance", "Balance", M), col("status", "Status")]


def ob_row(v):
    b = v["breakdown"]
    return {"staff_name": v["staff_name"], "period": f"{v['period_start']} to {v['period_end']}", "due_date": v["due_date"],
            "gross": b["gross"], "attendance_deduction": b["attendance_deduction"], "earned": b["earned"],
            "late_fines": b["late_fines"], "manual_fines": v["manual_fines"], "fines_deducted": v["fines_deducted"],
            "advance_recovery": v["advance_recovery"], "other_deductions": v["other_deductions"],
            "total_deductions": v["total_deductions"], "net_payable": v["net_payable"], "paid": v["paid"],
            "balance": v["balance"], "status": v["status"].replace("_", " ")}


def totals(cols, rows):
    return {c["key"]: r2(sum(r.get(c["key"]) or 0 for r in rows)) for c in cols if c["money"]}


async def build(kind, ctx, month: Optional[str], staff_id: Optional[str]):
    if kind not in KINDS:
        raise HTTPException(404, "Unknown report")
    month = month or today().strftime("%Y-%m")
    await sync_obligations(ctx.bid)
    L = await load_ledger(ctx.bid)
    views = L.views()
    y, m = int(month[:4]), int(month[5:7])
    ms, me = f"{month}-01", f"{month}-{dim(y, m):02d}"
    subtitle = f"Month: {month}"
    if kind == "attendance":
        cols = [col("name", "Staff"), col("designation", "Designation"), col("eligible_days", "Eligible Days"),
                col("present", "Present (eq.)"), col("absent_days", "Absent"), col("half_days", "Half Day"),
                col("paid_leave_days", "Paid Leave"), col("unpaid_leave_days", "Unpaid Leave"), col("late_hours", "Late (hrs)"),
                col("late_fines", "Late Fines", M)]
        rows = []
        for s in L.staff.values():
            if s["joining_date"] > me or (s.get("leaving_date") and s["leaving_date"] < ms):
                continue
            cut = min(D(me), today())
            b = L.salary(s["id"], ms, cut)
            present = b["eligible_days"] - b["absent_days"] - b["paid_leave_days"] - b["unpaid_leave_days"] - b["half_days"] * 0.5
            rows.append({"name": s["name"], "designation": s.get("designation"), **b, "present": max(present, 0)})
    elif kind in ("salary_sheet", "employee", "pending", "overdue"):
        cols = OB_COLS
        if kind == "salary_sheet":
            sel = [v for v in views if v["period_start"] <= me and v["period_end"] >= ms]
        elif kind == "employee":
            if not staff_id or staff_id not in L.staff:
                raise HTTPException(422, "Select a staff member")
            sel = [v for v in views if v["staff_id"] == staff_id]
            subtitle = f"Staff: {L.staff[staff_id]['name']}"
        elif kind == "pending":
            sel = [v for v in views if v["balance"] > 0 and v["status"] != "overdue"]
            subtitle = f"As of {today().isoformat()}"
        else:
            sel = [v for v in views if v["status"] == "overdue"]
            subtitle = f"As of {today().isoformat()}"
        rows = [ob_row(v) for v in sorted(sel, key=lambda v: (v["due_date"], v["staff_name"] or ""))]
    elif kind == "paid":
        cols = [col("date", "Paid On"), col("staff_name", "Staff"), col("period", "Salary Period"), col("method", "Method"),
                col("note", "Note"), col("amount", "Amount", M)]
        rows = [{"date": x["date"], "staff_name": L.staff.get(x["staff_id"], {}).get("name"),
                 "period": f"{x['period_start']} to {x['period_end']}", "method": x["method"].upper(), "note": x.get("note"),
                 "amount": x["amount"]} for x in L.all_txns if x["date"].startswith(month)]
    elif kind == "advances":
        cols = [col("name", "Staff"), col("advances_total", "Total Advances", M), col("recovered_total", "Recovered / Scheduled", M),
                col("outstanding", "Outstanding", M), col("advance_month", "Advanced This Month", M),
                col("recovered_month", "Recovered This Month", M), col("manual_fines", "Manual Fines (month)", M),
                col("late_fines", "Late Fines (month)", M)]
        rows = []
        for s in L.staff.values():
            sid = s["id"]
            a = L.advance_summary(sid)
            adv_m = r2(sum(x["amount"] for x in L.advances.get(sid, []) if x["date"].startswith(month)))
            rec_m = L.adv_recovered_in_month(sid, month)
            fines_m = r2(sum(f["amount"] for f in L.fines.get(sid, []) if f["date"].startswith(month)))
            late_m = r2(sum(x.get("fine_amount") or 0 for x in L.att.get(sid, []) if x["date"].startswith(month)))
            if not (a["total"] or fines_m or late_m):
                continue
            rows.append({"name": s["name"], "advances_total": a["total"], "recovered_total": a["recovered"],
                         "outstanding": a["outstanding"], "advance_month": adv_m, "recovered_month": rec_m,
                         "manual_fines": fines_m, "late_fines": late_m})
    else:
        cols = [col("name", "Staff"), col("designation", "Designation"), col("joining_date", "Joined"),
                col("leaving_date", "Left"), col("net_total", "Total Net Salary", M), col("paid_total", "Total Paid", M),
                col("balance", "Final Balance Due", M), col("advance_outstanding", "Advance Outstanding", M)]
        rows = []
        for s in L.staff.values():
            if s["status"] != "former":
                continue
            vs = [v for v in views if v["staff_id"] == s["id"]]
            rows.append({"name": s["name"], "designation": s.get("designation"), "joining_date": s["joining_date"],
                         "leaving_date": s.get("leaving_date"), "net_total": r2(sum(v["net_payable"] for v in vs)),
                         "paid_total": r2(sum(v["paid"] for v in vs)), "balance": r2(sum(v["balance"] for v in vs)),
                         "advance_outstanding": L.advance_summary(s["id"])["outstanding"]})
        subtitle = f"As of {today().isoformat()}"
    return {"kind": kind, "title": KINDS[kind], "subtitle": subtitle, "business": L.biz["name"],
            "columns": cols, "rows": rows, "totals": totals(cols, rows), "generated_on": today().isoformat()}


@router.get("/reports/{kind}")
async def report(kind: str, month: Optional[str] = None, staff_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    return await build(kind, ctx, month, staff_id)


@router.get("/reports/{kind}/csv")
async def report_csv(kind: str, month: Optional[str] = None, staff_id: Optional[str] = None, ctx=Depends(owner_ctx)):
    rep = await build(kind, ctx, month, staff_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([rep["business"], rep["title"], rep["subtitle"]])
    w.writerow([c["label"] for c in rep["columns"]])
    for r in rep["rows"]:
        w.writerow([f"{r.get(c['key']):.2f}" if c["money"] and r.get(c["key"]) is not None else r.get(c["key"], "") for c in rep["columns"]])
    if rep["totals"]:
        w.writerow(["TOTAL" if i == 0 else (f"{rep['totals'][c['key']]:.2f}" if c["money"] else "") for i, c in enumerate(rep["columns"])])
    fname = f"staffbook_{kind}_{month or today().strftime('%Y-%m')}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
