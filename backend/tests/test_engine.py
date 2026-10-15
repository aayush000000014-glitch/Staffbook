import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import generate_periods, compute_salary, unpaid_leave_dates, clamp_day  # noqa: E402


def staff(**kw):
    base = {"joining_date": "2026-10-13", "schedule_type": "fixed_date", "pay_day": 10, "leaving_date": None}
    base.update(kw)
    return base


def test_fixed_date_first_due():
    p = generate_periods(staff(), None, date(2026, 11, 5))
    assert p[0] == (date(2026, 10, 13), date(2026, 10, 31), date(2026, 11, 10))
    assert p[1][0] == date(2026, 11, 1)


def test_fixed_date_month_end_clamp_and_leap():
    assert clamp_day(2027, 2, 31) == date(2027, 2, 28)
    assert clamp_day(2028, 2, 31) == date(2028, 2, 29)
    p = generate_periods(staff(joining_date="2028-01-05", pay_day=31), None, date(2028, 1, 6))
    assert p[0][2] == date(2028, 2, 29)


def test_cycles():
    p30 = generate_periods(staff(schedule_type="cycle30", joining_date="2026-01-15"), None, date(2026, 3, 1))
    assert p30[0] == (date(2026, 1, 15), date(2026, 2, 13), date(2026, 2, 13))
    p40 = generate_periods(staff(schedule_type="cycle40", joining_date="2026-01-01"), None, date(2026, 2, 15))
    assert p40[0][2] == date(2026, 2, 9) and p40[1][0] == date(2026, 2, 10)


def test_40_day_example_and_no_double_count():
    s = staff(schedule_type="cycle40", joining_date="2026-09-07")
    p = generate_periods(s, None, date(2026, 11, 30))
    assert p[0] == (date(2026, 9, 7), date(2026, 10, 16), date(2026, 10, 16))
    assert p[1][0] == date(2026, 10, 17)
    a = compute_salary(15000, "fixed30", p[0][0], p[0][1], "2026-09-07", None, [], set())
    assert a["gross"] == 20000.0  # 24 Sep days + 16 Oct days at 500/day
    b = compute_salary(15000, "fixed30", "2026-10-17", "2026-10-31", "2026-09-07", None, [], set())
    assert b["gross"] == 7000.0  # October total capped at monthly salary 15000
    c = compute_salary(15000, "calendar", "2026-10-01", "2026-10-16", "2026-09-07", None, [], set())
    d = compute_salary(15000, "calendar", "2026-10-17", "2026-10-31", "2026-09-07", None, [], set())
    assert round(c["gross"] + d["gross"], 2) == 15000.0


def test_leaving_stops_periods():
    p = generate_periods(staff(joining_date="2026-01-01", leaving_date="2026-02-10"), None, date(2026, 6, 1))
    assert len(p) == 2 and p[-1][1] == date(2026, 2, 10)


def test_salary_methods():
    full = compute_salary(30000, "fixed30", "2026-02-01", "2026-02-28", "2026-01-01", None, [], set())
    assert full["gross"] == 30000
    partial = compute_salary(30000, "fixed30", "2026-10-01", "2026-10-31", "2026-10-13", None, [], set())
    assert partial["gross"] == 19000.0
    cal = compute_salary(31000, "calendar", "2026-10-01", "2026-10-31", "2026-10-13", None, [], set())
    assert cal["gross"] == 19000.0
    leap = compute_salary(29000, "calendar", "2028-02-01", "2028-02-10", "2028-01-01", None, [], set())
    assert leap["gross"] == 10000.0


def test_mid_month_leaving():
    r = compute_salary(30000, "calendar", "2026-09-01", "2026-09-30", "2026-01-01", "2026-09-15", [], set())
    assert r["gross"] == 15000.0 and r["eligible_days"] == 15


def test_exceptions_and_leave_quota():
    ex = [{"date": "2026-09-02", "status": "absent"}, {"date": "2026-09-03", "status": "half_day"},
          {"date": "2026-09-04", "status": "late", "hours_late": 2, "fine_amount": 100},
          {"date": "2026-09-05", "status": "paid_leave"}, {"date": "2026-09-06", "status": "paid_leave"}]
    unpaid = unpaid_leave_dates([date(2026, 9, 5), date(2026, 9, 6)], 1, "monthly")
    assert unpaid == {date(2026, 9, 6)}
    r = compute_salary(30000, "fixed30", "2026-09-01", "2026-09-30", "2026-01-01", None, ex, unpaid)
    assert r["attendance_deduction"] == 2500.0
    assert r["earned"] == 27500.0 and r["late_fines"] == 100.0 and r["paid_leave_days"] == 1


def test_yearly_quota():
    ds = [date(2026, m, 1) for m in range(1, 8)]
    assert unpaid_leave_dates(ds, 5, "yearly") == {date(2026, 6, 1), date(2026, 7, 1)}
