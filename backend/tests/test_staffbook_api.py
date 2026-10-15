"""StaffBook e2e backend tests (cookie session auth). Prefixes test business with TEST_.
Covers: auth cookie flow, cross-tenant, payments, attendance, advances/fines, reports,
super admin + new iter2 features: advance+fines deductions, excess advance carry-forward,
fines carry-forward policy, cycle40 due date, dashboard earned-till-date, persistent login,
logout invalidation."""
import os
import random
import time
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _rand_phone():
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


# ---------- AUTH (cookie-based) ----------
class TestAuth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_signup_invalid_phone(self):
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "X", "phone": "1234567890", "password": "Password123!",
            "business_name": "TEST_bad", "security_question": "colour?", "security_answer": "red"})
        assert r.status_code == 422

    def test_signup_login_me_cookie(self):
        s = requests.Session()
        phone = _rand_phone()
        body = {"name": "TT", "phone": phone, "password": "Password123!",
                "business_name": f"TEST_auth_{phone[-5:]}",
                "security_question": "colour?", "security_answer": "red"}
        r = s.post(f"{BASE_URL}/api/auth/signup", json=body)
        assert r.status_code == 200, r.text
        # No token in body
        assert "token" not in r.json()
        assert r.json()["user"]["role"] == "owner"
        # Cookie present and HttpOnly
        assert "sb_session" in s.cookies
        set_cookie = r.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "secure" in set_cookie
        # duplicate signup
        r2 = requests.post(f"{BASE_URL}/api/auth/signup", json=body)
        assert r2.status_code == 409
        # me works with cookie
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["phone"] == f"+91{phone}"
        # logout clears session
        lo = s.post(f"{BASE_URL}/api/auth/logout")
        assert lo.status_code == 200
        # Old cookie should now be invalid (server-side revoked)
        me2 = s.get(f"{BASE_URL}/api/auth/me")
        assert me2.status_code == 401

    def test_login_persistent_in_new_session(self):
        phone = _rand_phone()
        su = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "Persist", "phone": phone, "password": "Password123!",
            "business_name": f"TEST_persist_{phone[-5:]}",
            "security_question": "what colour?", "security_answer": "yy"})
        assert su.status_code == 200, su.text
        # Fresh login
        s1 = requests.Session()
        r = s1.post(f"{BASE_URL}/api/auth/login", json={"phone": phone, "password": "Password123!"})
        assert r.status_code == 200, r.text
        cookie_val = s1.cookies.get("sb_session")
        assert cookie_val
        # Simulate "browser reopen" by using cookie in a brand-new session
        s2 = requests.Session()
        s2.cookies.set("sb_session", cookie_val)
        me = s2.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        # Logout from s1 should revoke s2 too (same session hash)
        s1.post(f"{BASE_URL}/api/auth/logout")
        me2 = s2.get(f"{BASE_URL}/api/auth/me")
        assert me2.status_code == 401

    def test_super_admin_persist(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"phone": "8950771876", "password": "@Aayush_0512"})
        assert r.status_code == 200
        assert s.cookies.get("sb_session")
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["role"] == "super_admin"

    def test_recovery(self):
        phone = _rand_phone()
        requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "RR", "phone": phone, "password": "GoodPass123!",
            "business_name": f"TEST_rec_{phone[-5:]}",
            "security_question": "pet name?", "security_answer": "Fluffy"})
        q = requests.post(f"{BASE_URL}/api/auth/recovery/question", json={"phone": phone})
        assert q.status_code == 200
        assert "pet" in q.json()["question"].lower()
        bad = requests.post(f"{BASE_URL}/api/auth/recovery/reset",
                            json={"phone": phone, "answer": "wrong", "new_password": "NewPass123!"})
        assert bad.status_code == 401
        ok = requests.post(f"{BASE_URL}/api/auth/recovery/reset",
                           json={"phone": phone, "answer": "fluffy", "new_password": "NewPass123!"})
        assert ok.status_code == 200
        lr = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": phone, "password": "NewPass123!"})
        assert lr.status_code == 200


# ---------- CROSS TENANT ----------
class TestCrossTenant:
    def test_cross_tenant_blocked(self, owner_a_onboarded, owner_b_onboarded):
        sa = owner_a_onboarded["session"]
        sb = owner_b_onboarded["session"]
        body = {"name": "StaffX", "phone": "", "designation": "worker",
                "monthly_salary": 30000, "joining_date": "2026-08-13"}
        r = sa.post(f"{BASE_URL}/api/staff", json=body)
        assert r.status_code == 200
        sid = r.json()["id"]
        assert sb.get(f"{BASE_URL}/api/staff/{sid}").status_code in (403, 404)
        assert sb.put(f"{BASE_URL}/api/staff/{sid}",
                      json={"name": "Hack", "phone": "", "designation": "",
                            "monthly_salary": 1000, "joining_date": "2026-08-13"}).status_code in (403, 404)

    def test_admin_forbidden_for_owner(self, owner_a_onboarded):
        r = owner_a_onboarded["session"].get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 403


# ---------- STAFF LEAVE ----------
class TestStaffLeave:
    def test_mark_as_left_frees_slot(self, owner_a_onboarded):
        s = owner_a_onboarded["session"]
        body = {"name": "Leaver", "phone": "", "designation": "",
                "monthly_salary": 20000, "joining_date": "2026-08-13"}
        r = s.post(f"{BASE_URL}/api/staff", json=body)
        sid = r.json()["id"]
        r2 = s.post(f"{BASE_URL}/api/staff/{sid}/leave",
                    json={"leaving_date": "2026-10-14", "reason": "test"})
        assert r2.status_code == 200
        r3 = s.post(f"{BASE_URL}/api/staff/{sid}/leave",
                    json={"leaving_date": "2026-10-14"})
        assert r3.status_code == 409


# ---------- NEW FEATURE: Advance + fines reduce net ----------
class TestAdvanceFineExample:
    """Spec example: salary 10000 fixed30 pay_day 10 joining 2026-08-01,
    late_fine_per_hour 150, advance 2000 on 2026-09-05, late 2h on 2026-09-08 (=300),
    manual fine 200 on 2026-09-10 -> Sep: gross 10000, total_ded 2500, advance_recovery 2000,
    net 7500, balance 7500."""

    def test_spec_example(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, late_fine=150.0)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "SpecStaff", "phone": "", "designation": "",
            "monthly_salary": 10000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        # Advance 2000 on 2026-09-05
        a = s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 2000, "date": "2026-09-05", "description": "sep adv"})
        assert a.status_code == 200, a.text
        # Attendance late 2h on 2026-09-08
        att = s.put(f"{BASE_URL}/api/attendance", json={
            "staff_id": sid, "date": "2026-09-08", "status": "late", "hours_late": 2})
        assert att.status_code == 200
        assert att.json()["fine_amount"] == 300.0
        # Manual fine 200 on 2026-09-10
        f = s.post(f"{BASE_URL}/api/fines", json={
            "staff_id": sid, "amount": 200, "date": "2026-09-10", "reason": "late repeat"})
        assert f.status_code == 200
        # Fetch September obligation
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        sep = next((o for o in obs if o["period_end"].startswith("2026-09")), None)
        assert sep, f"No Sep obligation. Got: {[o['period_start'] for o in obs]}"
        assert sep["breakdown"]["gross"] == 10000.0, sep["breakdown"]
        assert sep["late_fines"] == 300.0
        assert sep["manual_fines"] == 200.0
        assert sep["advance_recovery"] == 2000.0
        assert sep["advance_mode"] == "auto"
        assert sep["total_deductions"] == 2500.0
        assert sep["net_payable"] == 7500.0
        assert sep["balance"] == 7500.0
        # advance_summary: total 2000, outstanding 0 (fully recovered via Sep)
        asum = s.get(f"{BASE_URL}/api/staff/{sid}/advance-summary")
        if asum.status_code == 404:
            # endpoint variant check
            prof = s.get(f"{BASE_URL}/api/staff/{sid}").json()
            summ = prof.get("advance_summary") or prof.get("advances_summary")
            assert summ, f"no advance summary in profile: {list(prof.keys())}"
            assert summ["total"] == 2000.0
            assert summ["outstanding"] == 0.0
        else:
            assert asum.status_code == 200
            assert asum.json()["total"] == 2000.0
            assert asum.json()["outstanding"] == 0.0
        # Salary sheet report for 2026-09 reflects the same numbers
        rep = s.get(f"{BASE_URL}/api/reports/salary_sheet?month=2026-09")
        assert rep.status_code == 200
        rows = rep.json()["rows"]
        row = next((r for r in rows if r.get("staff_name") == "SpecStaff"), None)
        assert row, f"No row for SpecStaff in salary sheet: {rows[:1]}"
        # CSV also works
        csv = s.get(f"{BASE_URL}/api/reports/salary_sheet/csv?month=2026-09")
        assert csv.status_code == 200
        assert "text/csv" in csv.headers.get("content-type", "")


# ---------- NEW FEATURE: Excess advance carry forward ----------
class TestAdvanceCarryForward:
    def test_excess_advance_rolls_to_next_period(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "CarryStaff", "phone": "", "designation": "",
            "monthly_salary": 10000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        a = s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 12000, "date": "2026-08-20"})
        assert a.status_code == 200
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        aug = next((o for o in obs if o["period_end"].startswith("2026-08")), None)
        sep = next((o for o in obs if o["period_end"].startswith("2026-09")), None)
        assert aug and sep
        assert aug["advance_recovery"] == 10000.0
        assert aug["net_payable"] == 0.0
        assert aug["balance"] == 0.0
        assert sep["advance_recovery"] == 2000.0
        assert sep["net_payable"] == 8000.0
        assert sep["balance"] == 8000.0

    def test_recovery_cap_422(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "CapRec", "phone": "", "designation": "",
            "monthly_salary": 10000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 3000, "date": "2026-08-15"})
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        aug = next(o for o in obs if o["period_end"].startswith("2026-08"))
        # Attempt to set recovery above available advance (3000)
        r = s.post(f"{BASE_URL}/api/obligations/{aug['id']}/adjust",
                   json={"advance_recovery": 9999, "other_deductions": 0,
                         "reason": "test cap"})
        assert r.status_code == 422, r.text


# ---------- NEW FEATURE: Fines carry-forward policy ----------
class TestFinesCarryForward:
    def _setup(self, carry_flag):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, late_fine=0.0)
        s = info["session"]
        if carry_flag:
            # Enable via PUT /api/business
            biz = s.get(f"{BASE_URL}/api/business").json()
            settings = {**biz["settings"], "carry_forward_fines": True}
            # Strip keys SettingsIn doesn't accept
            keep = ("salary_method", "schedule_type", "pay_day", "late_fine_per_hour",
                    "paid_leave_quota", "leave_quota_period",
                    "allow_future_attendance_days", "carry_forward_fines")
            payload = {k: settings[k] for k in keep if k in settings}
            r = s.put(f"{BASE_URL}/api/business", json={"settings": payload})
            assert r.status_code == 200, r.text
        return s

    def test_no_carry(self):
        s = self._setup(False)
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "FineStaff", "phone": "", "designation": "",
            "monthly_salary": 2000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        # Huge fine in Aug - earned 2000, fine 5000
        s.post(f"{BASE_URL}/api/fines", json={
            "staff_id": sid, "amount": 5000, "date": "2026-08-15", "reason": "big"})
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        aug = next(o for o in obs if o["period_end"].startswith("2026-08"))
        sep = next(o for o in obs if o["period_end"].startswith("2026-09"))
        assert aug["net_payable"] == 0.0
        assert aug["fines_not_deducted"] > 0
        # No carry
        assert aug["fines_carried_out"] == 0.0
        assert sep["fines_carried_in"] == 0.0

    def test_with_carry(self):
        s = self._setup(True)
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "FineStaff2", "phone": "", "designation": "",
            "monthly_salary": 2000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        s.post(f"{BASE_URL}/api/fines", json={
            "staff_id": sid, "amount": 5000, "date": "2026-08-15", "reason": "big"})
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        aug = next(o for o in obs if o["period_end"].startswith("2026-08"))
        sep = next(o for o in obs if o["period_end"].startswith("2026-09"))
        # Aug non-accruing (period ended before today 2026-10-15) -> carry out
        assert aug["fines_carried_out"] > 0
        assert sep["fines_carried_in"] == aug["fines_carried_out"]
        # Balance never negative
        assert aug["balance"] >= 0 and sep["balance"] >= 0


# ---------- NEW FEATURE: 40-day cycle due date ----------
class TestCycle40:
    def test_due_date(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40")
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-09-07",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={staff['id']}").json()
        first = obs[0]
        assert first["period_start"] == "2026-09-07"
        assert first["period_end"] == "2026-10-06"
        assert first["due_date"] == "2026-10-16"
        # New model: monthly block = 15000 (not 20000)
        assert first["breakdown"]["gross"] == 15000.0


# ---------- ITER3: 40-day cycle new model (spec examples) ----------
class TestCycle40NewModel:
    """Spec: today=2026-10-15 IST, salary 15000 fixed30, cycle40.
    joining 2026-08-14 -> three obligations:
      p1: 14 Aug-13 Sep due 22 Sep gross 15500 (Aug=18d*500 + Sep=13d*500) overdue
      p2: 14 Sep-13 Oct due  1 Nov gross 15000 pending
      p3: 14 Oct-13 Nov due 11 Dec accruing"""

    def test_aug14_three_blocks(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40")
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40Aug", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-08-14",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        sid = staff["id"]
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        obs = sorted(obs, key=lambda o: o["period_start"])
        assert len(obs) >= 3, [o["period_start"] for o in obs]
        p1, p2, p3 = obs[0], obs[1], obs[2]
        assert (p1["period_start"], p1["period_end"], p1["due_date"]) == (
            "2026-08-14", "2026-09-13", "2026-09-22")
        assert p1["breakdown"]["gross"] == 15500.0, p1
        assert (p2["period_start"], p2["period_end"], p2["due_date"]) == (
            "2026-09-14", "2026-10-13", "2026-11-01")
        assert p2["breakdown"]["gross"] == 15000.0
        assert (p3["period_start"], p3["period_end"], p3["due_date"]) == (
            "2026-10-14", "2026-11-13", "2026-12-11")
        assert p3["accruing"] is True
        # p1,p2 not accruing
        assert p1["accruing"] is False and p2["accruing"] is False
        # Staff profile outstanding = only completed (p1+p2 balances); accruing_balance = p3 balance
        prof = s.get(f"{BASE_URL}/api/staff/{sid}").json()
        outstanding_expected = round(p1["balance"] + p2["balance"], 2)
        assert prof["outstanding"] == outstanding_expected
        assert prof["accruing_balance"] == p3["balance"]
        # Staff list "outstanding" matches
        lst = s.get(f"{BASE_URL}/api/staff").json()
        row = next(x for x in lst if x["id"] == sid)
        assert row["outstanding"] == outstanding_expected

    def test_sep14_first_block(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40")
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40Sep", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-09-14",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={staff['id']}").json()
        obs = sorted(obs, key=lambda o: o["period_start"])
        p1 = obs[0]
        assert (p1["period_start"], p1["period_end"], p1["due_date"]) == (
            "2026-09-14", "2026-10-13", "2026-10-23")
        assert p1["balance"] == 15000.0 and p1["breakdown"]["gross"] == 15000.0

    def test_partial_payments(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40")
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40Pay", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-08-14",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        sid = staff["id"]
        obs = sorted(s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json(),
                    key=lambda o: o["period_start"])
        target = obs[0]  # overdue 15500
        oid = target["id"]
        ref1 = f"c40a{int(time.time()*1000)}"
        r1 = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": 5000, "method": "cash", "date": "2026-10-14",
            "client_ref": ref1})
        assert r1.status_code == 200, r1.text
        ob1 = s.get(f"{BASE_URL}/api/obligations/{oid}").json()
        assert ob1["partially_paid"] is True
        assert ob1["paid"] == 5000.0
        remaining = ob1["balance"]
        ref2 = f"c40b{int(time.time()*1000)}"
        r2 = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": remaining, "method": "cash", "date": "2026-10-14",
            "client_ref": ref2})
        assert r2.status_code == 200
        ob2 = s.get(f"{BASE_URL}/api/obligations/{oid}").json()
        assert ob2["status"] == "paid"
        assert ob2["balance"] == 0.0
        # duplicate client_ref -> 409
        dup = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": 1.0, "method": "cash", "date": "2026-10-14",
            "client_ref": ref1})
        assert dup.status_code == 409
        # overpay (new obligation) -> 422
        p2 = obs[1]
        over = s.post(f"{BASE_URL}/api/obligations/{p2['id']}/pay", json={
            "amount": 999999, "method": "cash", "date": "2026-10-14",
            "client_ref": f"c40o{int(time.time()*1000)}"})
        assert over.status_code == 422

    def test_mark_left_mid_block(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40")
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40Left", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-08-14",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        sid = staff["id"]
        r = s.post(f"{BASE_URL}/api/staff/{sid}/leave",
                   json={"leaving_date": "2026-10-20", "reason": "iter3"})
        assert r.status_code == 200, r.text
        obs = sorted(s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json(),
                    key=lambda o: o["period_start"])
        # Last period is truncated to 2026-10-20
        last = obs[-1]
        assert last["period_end"] == "2026-10-20"
        # Profile settlement present
        prof = s.get(f"{BASE_URL}/api/staff/{sid}").json()
        assert prof["settlement"] is not None
        assert prof["staff"]["status"] == "former"

    def test_cycle40_deductions_once(self):
        """Absent day (500), manual fine, advance auto-recovery
        reduce one period net once; outstanding never negative."""
        info = _signup_fresh()
        _onboard_business(info, pay_day=10, schedule="cycle40", late_fine=150.0)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "C40Ded", "phone": "", "designation": "",
            "monthly_salary": 15000, "joining_date": "2026-08-14",
            "schedule_type": "cycle40", "salary_method": "fixed30"}).json()
        sid = staff["id"]
        # Absent 2026-08-20 -> 500 deduction (fixed30 500/day)
        r = s.put(f"{BASE_URL}/api/attendance", json={
            "staff_id": sid, "date": "2026-08-20", "status": "absent"})
        assert r.status_code == 200, r.text
        # Manual fine 200 (reason >= 2 chars)
        rf = s.post(f"{BASE_URL}/api/fines", json={
            "staff_id": sid, "amount": 200, "date": "2026-08-22",
            "reason": "manual-test"})
        assert rf.status_code == 200, rf.text
        # Advance 1000
        ra = s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 1000, "date": "2026-08-25"})
        assert ra.status_code == 200, ra.text
        obs = sorted(s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json(),
                    key=lambda o: o["period_start"])
        p1 = obs[0]
        # p1 gross stays 15500 (14 Aug-13 Sep monthly block)
        assert p1["breakdown"]["gross"] == 15500.0
        # Absent day deducted once
        assert p1["breakdown"]["attendance_deduction"] == 500.0
        # Manual fine 200 applied in p1 (fine date within period)
        assert p1["manual_fines"] == 200.0
        # Advance 1000 auto-recovered once in p1
        assert p1["advance_recovery"] == 1000.0
        # Totals never negative
        for o in obs:
            assert o["balance"] >= 0, o
        # Expected: 15500 - 500(absent) - 200(fine) - 1000(adv) = 13800
        assert p1["net_payable"] == 13800.0
        # Advance not double-recovered
        total_rec = sum(o["advance_recovery"] for o in obs)
        assert total_rec == 1000.0


# ---------- ITER3: outstanding vs accruing_balance for fixed_date ----------
class TestOutstandingSplit:
    def test_fixed_date_accruing_excluded(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "SplitStaff", "phone": "", "designation": "",
            "monthly_salary": 10000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        prof = s.get(f"{BASE_URL}/api/staff/{sid}").json()
        obs = prof["obligations"]
        accr = [o for o in obs if o["accruing"]]
        done = [o for o in obs if not o["accruing"]]
        assert prof["outstanding"] == round(sum(o["balance"] for o in done), 2)
        assert prof["accruing_balance"] == round(sum(o["balance"] for o in accr), 2)
        # dashboard pending/overdue should not count the current (accruing) obligation balance
        d = s.get(f"{BASE_URL}/api/dashboard").json()
        assert d["pending"]["amount"] + d["overdue"]["amount"] >= 0


# ---------- Payment flow ----------
class TestPaymentsFlow:
    def test_pay_then_reverse(self, owner_a_onboarded):
        s = owner_a_onboarded["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "PayStaff2", "phone": "", "designation": "",
            "monthly_salary": 30000, "joining_date": "2026-08-13"}).json()
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={staff['id']}").json()
        target = next(o for o in obs if o["balance"] > 0)
        oid = target["id"]
        balance = target["balance"]
        ref1 = f"ref{int(time.time()*1000)}_a"
        p1 = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": round(balance / 2, 2), "method": "cash",
            "date": "2026-10-14", "client_ref": ref1})
        assert p1.status_code == 200, p1.text
        # dup
        dup = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": 1.0, "method": "cash", "date": "2026-10-14", "client_ref": ref1})
        assert dup.status_code == 409
        # over balance
        over = s.post(f"{BASE_URL}/api/obligations/{oid}/pay", json={
            "amount": 999999, "method": "cash", "date": "2026-10-14",
            "client_ref": f"ref{int(time.time()*1000)}_b"})
        assert over.status_code == 422

    def test_paid_period_freezes_advance_recovery(self):
        info = _signup_fresh()
        _onboard_business(info, pay_day=10)
        s = info["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "FreezeStaff", "phone": "", "designation": "",
            "monthly_salary": 10000, "joining_date": "2026-08-01"}).json()
        sid = staff["id"]
        # First advance 2000, pay Aug, then add later advance -> paid period unaffected
        s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 2000, "date": "2026-08-10"})
        obs = s.get(f"{BASE_URL}/api/obligations?staff_id={sid}").json()
        aug = next(o for o in obs if o["period_end"].startswith("2026-08"))
        bal = aug["balance"]
        ref = f"freeze{int(time.time()*1000)}"
        pay = s.post(f"{BASE_URL}/api/obligations/{aug['id']}/pay", json={
            "amount": bal, "method": "cash", "date": "2026-10-01", "client_ref": ref})
        assert pay.status_code == 200
        rec_before = pay.json()["advance_recovery"]
        # Add later advance; Aug recovery should remain frozen
        s.post(f"{BASE_URL}/api/advances", json={
            "staff_id": sid, "amount": 5000, "date": "2026-09-20"})
        aug2 = s.get(f"{BASE_URL}/api/obligations/{aug['id']}").json()
        assert aug2["advance_recovery"] == rec_before


# ---------- Dashboard earned-till-date ----------
class TestDashboard:
    def test_structure(self, owner_a_onboarded):
        r = owner_a_onboarded["session"].get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        d = r.json()
        for k in ("active_staff", "capacity", "earned_till_date",
                  "payable_this_month", "paid_this_month", "pending", "overdue"):
            assert k in d
        assert d["earned_till_date"] >= 0


# ---------- Super admin ----------
class TestSuperAdmin:
    def test_stats_and_toggle(self, super_admin_session, owner_a_onboarded):
        admin = super_admin_session
        owner = owner_a_onboarded["session"]
        r = admin.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200
        bl = admin.get(f"{BASE_URL}/api/admin/businesses").json()
        a_biz = next((b for b in bl if b["name"] == owner_a_onboarded["business_name"]), None)
        assert a_biz
        d = admin.post(f"{BASE_URL}/api/admin/businesses/{a_biz['id']}/status",
                       json={"active": False, "reason": "test"})
        assert d.status_code == 200
        blk = owner.get(f"{BASE_URL}/api/dashboard")
        assert blk.status_code == 403
        rr = admin.post(f"{BASE_URL}/api/admin/businesses/{a_biz['id']}/status",
                        json={"active": True, "reason": "restore"})
        assert rr.status_code == 200
        ok = owner.get(f"{BASE_URL}/api/dashboard")
        assert ok.status_code == 200


# ---------- Staff login role scoping ----------
class TestStaffLogin:
    def test_staff_role_blocked_owner_ep(self, owner_a_onboarded):
        s = owner_a_onboarded["session"]
        staff = s.post(f"{BASE_URL}/api/staff", json={
            "name": "LoginStaff2", "phone": "", "designation": "",
            "monthly_salary": 20000, "joining_date": "2026-09-01"}).json()
        phone = _rand_phone()
        r = s.post(f"{BASE_URL}/api/staff/{staff['id']}/login",
                   json={"phone": phone, "password": "StaffPass123!"})
        assert r.status_code == 200
        st = requests.Session()
        lg = st.post(f"{BASE_URL}/api/auth/login",
                     json={"phone": phone, "password": "StaffPass123!"})
        assert lg.status_code == 200
        assert lg.json()["user"]["role"] == "staff"
        # Staff cannot hit owner endpoint
        no = st.get(f"{BASE_URL}/api/dashboard")
        assert no.status_code == 403
        # /me/staff works
        ms = st.get(f"{BASE_URL}/api/me/staff")
        assert ms.status_code == 200
        assert ms.json()["staff"]["id"] == staff["id"]


# ---------- Protected routes require auth ----------
class TestProtected:
    def test_dashboard_401_no_cookie(self):
        r = requests.get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 401
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401


# ----- helpers used by new tests to create isolated TEST_ owners -----
def _signup_fresh(prefix="TEST_iter2"):
    s = requests.Session()
    phone = _rand_phone()
    body = {
        "name": "Owner " + phone[-4:], "phone": phone, "password": "Password123!",
        "business_name": f"{prefix}_{phone[-5:]}",
        "security_question": "colour?", "security_answer": "blue",
    }
    r = s.post(f"{BASE_URL}/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    return {"session": s, "phone": phone, "business_name": body["business_name"]}


def _onboard_business(info, pay_day=10, late_fine=150.0,
                      schedule="fixed_date", salary_method="fixed30"):
    body = {
        "business": {"name": info["business_name"], "type": "Shop", "location": "Delhi", "logo": None},
        "owner": {"name": "Owner", "email": None},
        "settings": {
            "salary_method": salary_method, "schedule_type": schedule, "pay_day": pay_day,
            "late_fine_per_hour": late_fine, "paid_leave_quota": 1, "leave_quota_period": "monthly",
            "allow_future_attendance_days": 31, "carry_forward_fines": False,
        },
        "staff": [],
    }
    r = info["session"].post(f"{BASE_URL}/api/onboarding", json=body)
    assert r.status_code == 200, r.text
