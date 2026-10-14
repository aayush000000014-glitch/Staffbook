"""StaffBook end-to-end backend tests. Prefixes test business with TEST_."""
import os
import random
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://staffbook-preview.preview.emergentagent.com").rstrip("/")


def _rand_phone():
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


# ---------- AUTH ----------
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

    def test_signup_login_me(self):
        phone = _rand_phone()
        body = {"name": "TT", "phone": phone, "password": "Password123!",
                "business_name": f"TEST_auth_{phone[-5:]}",
                "security_question": "colour?", "security_answer": "red"}
        r = requests.post(f"{BASE_URL}/api/auth/signup", json=body)
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        assert r.json()["user"]["role"] == "owner"
        # duplicate
        r2 = requests.post(f"{BASE_URL}/api/auth/signup", json=body)
        assert r2.status_code == 409
        # login
        r3 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": phone, "password": "Password123!"})
        assert r3.status_code == 200
        # me
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user"]["phone"] == f"+91{phone}"

    def test_login_bad_creds(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"phone": "9000000001", "password": "wrongpass123"})
        assert r.status_code in (401, 429)

    def test_bruteforce_lockout(self):
        phone = _rand_phone()
        requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "LL", "phone": phone, "password": "GoodPass123!",
            "business_name": f"TEST_bf_{phone[-5:]}",
            "security_question": "q question?", "security_answer": "aa"})
        statuses = []
        for _ in range(10):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"phone": phone, "password": "wrongpass123"})
            statuses.append(r.status_code)
        assert 429 in statuses, f"Expected 429 lockout but got {statuses}"

    def test_recovery(self):
        phone = _rand_phone()
        requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "RR", "phone": phone, "password": "GoodPass123!",
            "business_name": f"TEST_rec_{phone[-5:]}",
            "security_question": "pet name?", "security_answer": "Fluffy"})
        q = requests.post(f"{BASE_URL}/api/auth/recovery/question", json={"phone": phone})
        assert q.status_code == 200
        assert "pet" in q.json()["question"].lower()
        # wrong
        bad = requests.post(f"{BASE_URL}/api/auth/recovery/reset",
                            json={"phone": phone, "answer": "wrong", "new_password": "NewPass123!"})
        assert bad.status_code == 401
        # right
        ok = requests.post(f"{BASE_URL}/api/auth/recovery/reset",
                           json={"phone": phone, "answer": "fluffy", "new_password": "NewPass123!"})
        assert ok.status_code == 200
        # new password works
        lr = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": phone, "password": "NewPass123!"})
        assert lr.status_code == 200


# ---------- CROSS TENANT ----------
class TestCrossTenant:
    def _create_staff(self, auth):
        body = {"name": "StaffX", "phone": "", "designation": "worker",
                "monthly_salary": 30000, "joining_date": "2026-08-13"}
        r = requests.post(f"{BASE_URL}/api/staff", json=body, headers=auth)
        assert r.status_code == 200, r.text
        return r.json()

    def test_cross_tenant_blocked(self, owner_a_onboarded, owner_b_onboarded, auth_a, auth_b):
        s = self._create_staff(auth_a)
        sid = s["id"]
        # B tries to GET A's staff
        r = requests.get(f"{BASE_URL}/api/staff/{sid}", headers=auth_b)
        assert r.status_code in (403, 404)
        # B tries to update A's staff
        r = requests.put(f"{BASE_URL}/api/staff/{sid}",
                         json={"name": "Hack", "phone": "", "designation": "",
                               "monthly_salary": 1, "joining_date": "2026-08-13"},
                         headers=auth_b)
        assert r.status_code in (403, 404)
        # B tries PUT attendance for A's staff
        r = requests.put(f"{BASE_URL}/api/attendance",
                         json={"staff_id": sid, "date": "2026-10-01", "status": "absent"},
                         headers=auth_b)
        assert r.status_code in (403, 404)

    def test_admin_forbidden_for_owner(self, auth_a, owner_a_onboarded):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers=auth_a)
        assert r.status_code == 403


# ---------- STAFF LIMIT ----------
class TestStaffLimit:
    def test_mark_as_left_frees_slot(self, owner_a_onboarded, auth_a):
        # Create one staff
        body = {"name": "Leaver", "phone": "", "designation": "",
                "monthly_salary": 20000, "joining_date": "2026-08-13"}
        r = requests.post(f"{BASE_URL}/api/staff", json=body, headers=auth_a)
        assert r.status_code == 200
        sid = r.json()["id"]
        # Mark left
        r2 = requests.post(f"{BASE_URL}/api/staff/{sid}/leave",
                           json={"leaving_date": "2026-10-14", "reason": "test"},
                           headers=auth_a)
        assert r2.status_code == 200
        # second leave should 409
        r3 = requests.post(f"{BASE_URL}/api/staff/{sid}/leave",
                           json={"leaving_date": "2026-10-14"}, headers=auth_a)
        assert r3.status_code == 409

    @pytest.mark.slow
    def test_100_cap(self, auth_a, owner_a_onboarded):
        # fetch current count
        r = requests.get(f"{BASE_URL}/api/staff?status=active", headers=auth_a)
        current = len(r.json())
        remaining = 100 - current
        created = []
        for i in range(remaining):
            body = {"name": f"Cap{i}", "phone": "", "designation": "",
                    "monthly_salary": 15000, "joining_date": "2026-10-01"}
            rr = requests.post(f"{BASE_URL}/api/staff", json=body, headers=auth_a)
            assert rr.status_code == 200, (i, rr.status_code, rr.text)
            created.append(rr.json()["id"])
        # 101st
        rr = requests.post(f"{BASE_URL}/api/staff",
                           json={"name": "Over", "phone": "", "designation": "",
                                 "monthly_salary": 15000, "joining_date": "2026-10-01"},
                           headers=auth_a)
        assert rr.status_code == 409, rr.text
        # mark one left frees slot
        requests.post(f"{BASE_URL}/api/staff/{created[0]}/leave",
                      json={"leaving_date": "2026-10-14"}, headers=auth_a)
        rr = requests.post(f"{BASE_URL}/api/staff",
                           json={"name": "AfterLeave", "phone": "", "designation": "",
                                 "monthly_salary": 15000, "joining_date": "2026-10-01"},
                           headers=auth_a)
        assert rr.status_code == 200
        # cleanup created staff
        requests.post(f"{BASE_URL}/api/staff/{rr.json()['id']}/leave",
                      json={"leaving_date": "2026-10-14"}, headers=auth_a)
        for sid in created[1:]:
            requests.post(f"{BASE_URL}/api/staff/{sid}/leave",
                          json={"leaving_date": "2026-10-14"}, headers=auth_a)


# ---------- PAYMENT / OBLIGATIONS ----------
class TestPaymentsFlow:
    @pytest.fixture(scope="class")
    def staff_payflow(self, owner_a_onboarded):
        hdr = {"Authorization": f"Bearer {owner_a_onboarded['token']}"}
        body = {"name": "PayStaff", "phone": "", "designation": "",
                "monthly_salary": 30000, "joining_date": "2026-08-13"}
        r = requests.post(f"{BASE_URL}/api/staff", json=body, headers=hdr)
        assert r.status_code == 200
        return r.json(), hdr

    def test_obligations_lazy_created(self, staff_payflow):
        s, hdr = staff_payflow
        r = requests.get(f"{BASE_URL}/api/obligations?staff_id=" + s["id"], headers=hdr)
        assert r.status_code == 200
        obs = r.json()
        assert len(obs) >= 1
        assert obs[0]["period_start"] == "2026-08-13"

    def test_partial_payment_then_full(self, staff_payflow):
        s, hdr = staff_payflow
        r = requests.get(f"{BASE_URL}/api/obligations?staff_id=" + s["id"], headers=hdr)
        obs = r.json()
        # find an overdue one (due in past)
        target = next((o for o in obs if o["balance"] > 0), None)
        assert target, "No open obligation"
        oid = target["id"]
        balance = target["balance"]
        ref1 = f"ref{int(time.time()*1000)}_a"
        p1 = requests.post(f"{BASE_URL}/api/obligations/{oid}/pay",
                           json={"amount": round(balance / 2, 2), "method": "cash",
                                 "date": "2026-10-14", "client_ref": ref1},
                           headers=hdr)
        assert p1.status_code == 200, p1.text
        v = p1.json()
        assert v["paid"] > 0
        # overdue is valid: period in past & balance > 0; or partially_paid if due future
        assert v["status"] in ("partially_paid", "paid", "overdue")
        # duplicate client_ref
        dup = requests.post(f"{BASE_URL}/api/obligations/{oid}/pay",
                            json={"amount": 1.0, "method": "cash",
                                  "date": "2026-10-14", "client_ref": ref1},
                            headers=hdr)
        assert dup.status_code == 409
        # amount > balance
        over = requests.post(f"{BASE_URL}/api/obligations/{oid}/pay",
                             json={"amount": 999999, "method": "cash",
                                   "date": "2026-10-14",
                                   "client_ref": f"ref{int(time.time()*1000)}_b"},
                             headers=hdr)
        assert over.status_code == 422

        # pay remaining
        remaining = v["balance"]
        ref2 = f"ref{int(time.time()*1000)}_c"
        p2 = requests.post(f"{BASE_URL}/api/obligations/{oid}/pay",
                           json={"amount": remaining, "method": "upi",
                                 "date": "2026-10-14", "client_ref": ref2},
                           headers=hdr)
        assert p2.status_code == 200
        assert p2.json()["status"] == "paid"
        # reverse one
        tid = p2.json()["transactions"][0]["id"]
        rev = requests.post(f"{BASE_URL}/api/transactions/{tid}/reverse",
                            json={"reason": "test reverse"}, headers=hdr)
        assert rev.status_code == 200
        after = requests.get(f"{BASE_URL}/api/obligations/{oid}", headers=hdr)
        assert after.json()["balance"] > 0


# ---------- ATTENDANCE ----------
class TestAttendance:
    def test_upsert_and_delete(self, owner_a_onboarded, auth_a):
        body = {"name": "AttStaff", "phone": "", "designation": "",
                "monthly_salary": 30000, "joining_date": "2026-08-13"}
        s = requests.post(f"{BASE_URL}/api/staff", json=body, headers=auth_a).json()
        # late with hours
        r = requests.put(f"{BASE_URL}/api/attendance",
                         json={"staff_id": s["id"], "date": "2026-09-15",
                               "status": "late", "hours_late": 2},
                         headers=auth_a)
        assert r.status_code == 200
        assert r.json()["fine_amount"] == 100.0  # 2 * 50
        # upsert same -> no duplicates
        r2 = requests.put(f"{BASE_URL}/api/attendance",
                          json={"staff_id": s["id"], "date": "2026-09-15",
                                "status": "absent"},
                          headers=auth_a)
        assert r2.status_code == 200
        assert r2.json()["status"] == "absent"
        # delete
        d = requests.delete(f"{BASE_URL}/api/attendance/{s['id']}/2026-09-15",
                            headers=auth_a)
        assert d.status_code == 200


# ---------- ADVANCES / FINES ----------
class TestAdvancesFines:
    def test_advance_and_fine(self, owner_a_onboarded, auth_a):
        s = requests.post(f"{BASE_URL}/api/staff",
                          json={"name": "AdvStaff", "phone": "", "designation": "",
                                "monthly_salary": 30000, "joining_date": "2026-08-13"},
                          headers=auth_a).json()
        a = requests.post(f"{BASE_URL}/api/advances",
                          json={"staff_id": s["id"], "amount": 5000,
                                "date": "2026-09-01", "description": "test"},
                          headers=auth_a)
        assert a.status_code == 200
        aid = a.json()["id"]
        f = requests.post(f"{BASE_URL}/api/fines",
                          json={"staff_id": s["id"], "amount": 500,
                                "date": "2026-09-05", "reason": "late repeat"},
                          headers=auth_a)
        assert f.status_code == 200
        fid = f.json()["id"]
        # Reverse advance
        rv = requests.post(f"{BASE_URL}/api/advances/{aid}/reverse",
                           json={"reason": "cancel"}, headers=auth_a)
        assert rv.status_code == 200
        # Reverse fine
        rf = requests.post(f"{BASE_URL}/api/fines/{fid}/reverse",
                           json={"reason": "waived"}, headers=auth_a)
        assert rf.status_code == 200


# ---------- DASHBOARD / REPORTS ----------
class TestDashboardReports:
    def test_dashboard_structure(self, owner_a_onboarded, auth_a):
        r = requests.get(f"{BASE_URL}/api/dashboard", headers=auth_a)
        assert r.status_code == 200
        d = r.json()
        for k in ("active_staff", "capacity", "present_today", "absent_today",
                  "earned_till_date", "payable_this_month", "paid_this_month",
                  "pending", "overdue", "due_soon", "recent_transactions", "alerts"):
            assert k in d

    @pytest.mark.parametrize("kind", ["attendance", "salary_sheet", "paid",
                                      "pending", "overdue", "advances", "settlement"])
    def test_report_kinds(self, owner_a_onboarded, auth_a, kind):
        r = requests.get(f"{BASE_URL}/api/reports/{kind}?month=2026-10",
                         headers=auth_a)
        assert r.status_code == 200
        rep = r.json()
        assert rep["kind"] == kind
        assert "rows" in rep
        # CSV
        c = requests.get(f"{BASE_URL}/api/reports/{kind}/csv?month=2026-10",
                         headers=auth_a)
        assert c.status_code == 200
        assert "text/csv" in c.headers.get("content-type", "")


# ---------- SUPER ADMIN ----------
class TestSuperAdmin:
    def test_admin_stats_and_toggle(self, admin_auth, owner_a_onboarded, auth_a):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers=admin_auth)
        assert r.status_code == 200
        assert r.json()["total_businesses"] >= 1
        bl = requests.get(f"{BASE_URL}/api/admin/businesses", headers=admin_auth)
        assert bl.status_code == 200
        a_biz = next((b for b in bl.json()
                      if b["name"] == owner_a_onboarded["business_name"]), None)
        assert a_biz, "Test biz not found in admin list"
        # Deactivate
        d = requests.post(
            f"{BASE_URL}/api/admin/businesses/{a_biz['id']}/status",
            json={"active": False, "reason": "test deactivation"}, headers=admin_auth)
        assert d.status_code == 200
        # Owner now blocked
        blk = requests.get(f"{BASE_URL}/api/dashboard", headers=auth_a)
        assert blk.status_code == 403
        # Reactivate
        rr = requests.post(
            f"{BASE_URL}/api/admin/businesses/{a_biz['id']}/status",
            json={"active": True, "reason": "restore"}, headers=admin_auth)
        assert rr.status_code == 200
        # Owner works again
        ok = requests.get(f"{BASE_URL}/api/dashboard", headers=auth_a)
        assert ok.status_code == 200
        # Audit
        au = requests.get(f"{BASE_URL}/api/admin/audit", headers=admin_auth)
        assert au.status_code == 200
        assert any(x["entity_id"] == a_biz["id"] for x in au.json())


# ---------- STAFF LOGIN ----------
class TestStaffLogin:
    def test_create_staff_login_and_me(self, owner_a_onboarded, auth_a):
        s = requests.post(f"{BASE_URL}/api/staff",
                          json={"name": "LoginStaff", "phone": "", "designation": "",
                                "monthly_salary": 20000, "joining_date": "2026-09-01"},
                          headers=auth_a).json()
        phone = _rand_phone()
        r = requests.post(f"{BASE_URL}/api/staff/{s['id']}/login",
                          json={"phone": phone, "password": "StaffPass123!"},
                          headers=auth_a)
        assert r.status_code == 200
        lg = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": phone, "password": "StaffPass123!"})
        assert lg.status_code == 200
        assert lg.json()["user"]["role"] == "staff"
        tok = lg.json()["token"]
        # Staff cannot access owner endpoints
        no = requests.get(f"{BASE_URL}/api/dashboard",
                          headers={"Authorization": f"Bearer {tok}"})
        assert no.status_code == 403
        # /me/staff works
        ms = requests.get(f"{BASE_URL}/api/me/staff",
                          headers={"Authorization": f"Bearer {tok}"})
        assert ms.status_code == 200
        assert ms.json()["staff"]["id"] == s["id"]
