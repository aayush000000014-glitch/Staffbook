"""Pure salary & schedule calculations (no DB)."""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def r2(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def D(s):
    if s is None or s == "" or isinstance(s, date):
        return s or None
    return date.fromisoformat(s)


def dim(y, m):
    return calendar.monthrange(y, m)[1]


def add_months(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def clamp_day(y, m, d):
    return date(y, m, min(int(d), dim(y, m)))


def next_period(staff: dict, start: date):
    st = staff["schedule_type"]
    if st == "fixed_date":
        end = date(start.year, start.month, dim(start.year, start.month))
        y, m = add_months(start.year, start.month, 1)
        due = clamp_day(y, m, staff.get("pay_day") or 1)
    else:
        n = 30 if st == "cycle30" else 40
        end = start + timedelta(days=n - 1)
        due = end
    leave = D(staff.get("leaving_date"))
    if leave and leave < end:
        end = leave
    return start, end, due


def generate_periods(staff: dict, last_end, upto: date):
    """Salary periods (start, end, due) starting after last_end up to `upto`."""
    join = D(staff["joining_date"])
    leave = D(staff.get("leaving_date"))
    out = []
    if last_end:
        s = D(last_end) + timedelta(days=1)
    else:
        s = join
        cs = D(staff.get("cycle_start"))
        if staff["schedule_type"] != "fixed_date" and cs and cs > join:
            stub_end = min(cs - timedelta(days=1), leave) if leave else cs - timedelta(days=1)
            if s <= upto:
                out.append((s, stub_end, stub_end))
            s = cs
    while s <= upto and (not leave or s <= leave):
        p = next_period(staff, s)
        out.append(p)
        s = p[1] + timedelta(days=1)
    return out


def unpaid_leave_dates(leave_dates, quota: int, period: str) -> set:
    cnt, unpaid = {}, set()
    for d in sorted(leave_dates):
        k = (d.year, d.month) if period == "monthly" else d.year
        cnt[k] = cnt.get(k, 0) + 1
        if cnt[k] > quota:
            unpaid.add(d)
    return unpaid


def compute_salary(salary, method, start, end, join, leave, exceptions, unpaid_leaves):
    """Earned salary for [start,end] clipped to employment. exceptions: [{date,status,hours_late,fine_amount}]"""
    s = max(D(start), D(join))
    e = min(D(end), D(leave)) if leave else D(end)
    res = {"gross": 0.0, "eligible_days": 0, "absent_days": 0, "half_days": 0, "paid_leave_days": 0,
           "unpaid_leave_days": 0, "late_hours": 0.0, "late_fines": 0.0, "attendance_deduction": 0.0,
           "earned": 0.0, "daily_rate": 0.0, "from": s.isoformat(), "to": e.isoformat()}
    if e < s:
        return res
    sal = Decimal(str(salary))
    jd, ld = D(join), D(leave) if leave else None
    rates, gross, cur, elig = {}, Decimal(0), s, 0
    while cur <= e:
        mdays = dim(cur.year, cur.month)
        mfirst, mend = date(cur.year, cur.month, 1), date(cur.year, cur.month, mdays)
        b = min(mend, e)
        rate = sal / 30 if method == "fixed30" else sal / mdays
        rates[(cur.year, cur.month)] = rate
        emp_start = max(mfirst, jd)
        emp_full = emp_start == mfirst and (ld is None or ld >= mend)

        def cum(d):
            # month-to-date earnings, capped so a calendar month never exceeds the monthly salary
            if d < emp_start:
                return Decimal(0)
            if emp_full and d == mend:
                return sal
            return min(rate * ((d - emp_start).days + 1), sal)

        gross += cum(b) - cum(cur - timedelta(days=1))
        elig += (b - cur).days + 1
        cur = b + timedelta(days=1)
    ded, late_f, late_h = Decimal(0), Decimal(0), Decimal(0)
    for ex in exceptions:
        d = D(ex["date"])
        if not (s <= d <= e):
            continue
        rate = rates[(d.year, d.month)]
        st = ex["status"]
        if st == "absent":
            ded += rate
            res["absent_days"] += 1
        elif st == "half_day":
            ded += rate / 2
            res["half_days"] += 1
        elif st == "paid_leave":
            if d in unpaid_leaves:
                ded += rate
                res["unpaid_leave_days"] += 1
            else:
                res["paid_leave_days"] += 1
        elif st == "late":
            late_h += Decimal(str(ex.get("hours_late") or 0))
            late_f += Decimal(str(ex.get("fine_amount") or 0))
    res["gross"] = r2(gross)
    res["attendance_deduction"] = r2(min(ded, gross))
    res["earned"] = r2(res["gross"] - res["attendance_deduction"])
    res["eligible_days"] = elig
    res["late_hours"] = float(late_h)
    res["late_fines"] = r2(late_f)
    res["daily_rate"] = r2(rates[(e.year, e.month)])
    return res
