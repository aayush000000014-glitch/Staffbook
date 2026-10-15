import os
import random
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _rand_phone():
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


def _login_session(phone, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"phone": phone, "password": password})
    assert r.status_code == 200, r.text
    assert "sb_session" in s.cookies, "sb_session cookie not set"
    return s


@pytest.fixture(scope="session")
def super_admin_session():
    return _login_session("8950771876", "@Aayush_0512")


def _signup_session(biz_name_prefix="TEST_SB"):
    s = requests.Session()
    phone = _rand_phone()
    body = {
        "name": "Owner " + phone[-4:],
        "phone": phone,
        "password": "Password123!",
        "business_name": f"{biz_name_prefix}_{phone[-5:]}",
        "security_question": "Favourite colour?",
        "security_answer": "blue",
    }
    r = s.post(f"{BASE_URL}/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    assert "sb_session" in s.cookies
    user = r.json()["user"]
    return {
        "session": s,
        "user": user,
        "phone": phone,
        "password": body["password"],
        "answer": body["security_answer"],
        "business_name": body["business_name"],
    }


@pytest.fixture(scope="session")
def owner_a():
    return _signup_session()


@pytest.fixture(scope="session")
def owner_b():
    return _signup_session()


def _onboard(info, pay_day=10, late_fine=150.0, schedule="fixed_date",
             salary_method="fixed30"):
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
    return info


@pytest.fixture(scope="session")
def owner_a_onboarded(owner_a):
    return _onboard(owner_a, pay_day=10, late_fine=150.0)


@pytest.fixture(scope="session")
def owner_b_onboarded(owner_b):
    return _onboard(owner_b, pay_day=1, late_fine=0.0)


# Back-compat shims for old tests still relying on headers
@pytest.fixture
def auth_a(owner_a):
    return owner_a["session"]


@pytest.fixture
def auth_b(owner_b):
    return owner_b["session"]


@pytest.fixture
def admin_session(super_admin_session):
    return super_admin_session
