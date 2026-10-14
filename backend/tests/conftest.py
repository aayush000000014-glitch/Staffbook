import os
import random
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://staffbook-preview.preview.emergentagent.com").rstrip("/")


def _rand_phone():
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def super_admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": "8950771876", "password": "@Aayush_0512"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _signup(biz_name_prefix="TEST_SB"):
    phone = _rand_phone()
    body = {
        "name": "Owner " + phone[-4:],
        "phone": phone,
        "password": "Password123!",
        "business_name": f"{biz_name_prefix}_{phone[-5:]}",
        "security_question": "Favourite colour?",
        "security_answer": "blue",
    }
    r = requests.post(f"{BASE_URL}/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    data["password"] = body["password"]
    data["phone"] = phone
    data["answer"] = body["security_answer"]
    data["business_name"] = body["business_name"]
    return data


@pytest.fixture(scope="session")
def owner_a():
    return _signup()


@pytest.fixture(scope="session")
def owner_b():
    return _signup()


@pytest.fixture
def auth_a(owner_a):
    return {"Authorization": f"Bearer {owner_a['token']}"}


@pytest.fixture
def auth_b(owner_b):
    return {"Authorization": f"Bearer {owner_b['token']}"}


@pytest.fixture
def admin_auth(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest.fixture(scope="session")
def owner_a_onboarded(owner_a):
    hdr = {"Authorization": f"Bearer {owner_a['token']}"}
    body = {
        "business": {"name": owner_a["business_name"], "type": "Shop", "location": "Delhi", "logo": None},
        "owner": {"name": "Owner A", "email": None},
        "settings": {
            "salary_method": "fixed30", "schedule_type": "fixed_date", "pay_day": 10,
            "late_fine_per_hour": 50.0, "paid_leave_quota": 1, "leave_quota_period": "monthly",
            "allow_future_attendance_days": 31,
        },
        "staff": [],
    }
    r = requests.post(f"{BASE_URL}/api/onboarding", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return owner_a


@pytest.fixture(scope="session")
def owner_b_onboarded(owner_b):
    hdr = {"Authorization": f"Bearer {owner_b['token']}"}
    body = {
        "business": {"name": owner_b["business_name"], "type": "Shop", "location": "Mumbai", "logo": None},
        "owner": {"name": "Owner B", "email": None},
        "settings": {
            "salary_method": "fixed30", "schedule_type": "fixed_date", "pay_day": 1,
            "late_fine_per_hour": 0.0, "paid_leave_quota": 0, "leave_quota_period": "monthly",
            "allow_future_attendance_days": 31,
        },
        "staff": [],
    }
    r = requests.post(f"{BASE_URL}/api/onboarding", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return owner_b
