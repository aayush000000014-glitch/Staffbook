import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

MAX_ACTIVE_STAFF = 100
IMG_MAX_CHARS = 1_400_000
IST = timezone(timedelta(hours=5, minutes=30))
NOPID = {"_id": 0}


def new_id():
    return uuid.uuid4().hex


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def today():
    return datetime.now(IST).date()


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(422, "Enter a valid 10-digit Indian mobile number")
    return "+91" + digits


def check_img(v):
    if v and (not v.startswith("data:image/") or len(v) > IMG_MAX_CHARS):
        raise HTTPException(422, "Image must be a PNG/JPG under 1MB")


SESSION_COOKIE = "sb_session"
SESSION_DAYS = 30


def _hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def set_session_cookie(response: Response, token: str):
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, secure=True,
                        samesite="lax", path="/")


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


async def create_session(user: dict, request: Request, response: Response) -> str:
    """Opaque random token in an HttpOnly cookie; only its SHA-256 hash is stored (revocable)."""
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    await db.sessions.insert_one({
        "id": new_id(), "token_hash": _hash_token(token), "user_id": user["id"], "created_at": now_iso(),
        "expires_at_dt": exp, "user_agent": (request.headers.get("user-agent") or "")[:200]})
    set_session_cookie(response, token)
    return token


def session_token(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
    return token


async def revoke_sessions(user_id: str, keep_hash: str = None):
    q = {"user_id": user_id}
    if keep_hash:
        q["token_hash"] = {"$ne": keep_hash}
    await db.sessions.delete_many(q)


def public_user(u: dict) -> dict:
    return {k: u.get(k) for k in ("id", "name", "phone", "email", "role", "business_id", "staff_id")}


async def current_user(request: Request) -> dict:
    token = session_token(request)
    if not token:
        raise HTTPException(401, "Not authenticated")
    sess = await db.sessions.find_one({"token_hash": _hash_token(token)}, {"_id": 0})
    if not sess:
        raise HTTPException(401, "Session expired or logged out. Please log in again.")
    exp = sess["expires_at_dt"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        await db.sessions.delete_one({"token_hash": sess["token_hash"]})
        raise HTTPException(401, "Session expired, please log in again")
    user = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0, "password_hash": 0, "security_answer_hash": 0})
    if not user or user.get("disabled"):
        raise HTTPException(401, "User not found or disabled")
    request.state.session = sess
    return user


class Ctx:
    def __init__(self, user, business):
        self.user = user
        self.business = business
        self.bid = business["id"]
        self.settings = business.get("settings", {})


async def _business_for(user: dict) -> dict:
    if not user.get("business_id"):
        raise HTTPException(403, "No business linked to this account")
    m = await db.memberships.find_one({"user_id": user["id"], "business_id": user["business_id"]}, NOPID)
    if not m:
        raise HTTPException(403, "Not a member of this business")
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "logo": 0})
    if not biz:
        raise HTTPException(404, "Business not found")
    if biz.get("status") != "active":
        raise HTTPException(403, "This business has been deactivated. Contact StaffBook support.")
    return biz


async def owner_ctx(user=Depends(current_user)) -> Ctx:
    if user["role"] != "owner":
        raise HTTPException(403, "Only the business owner can do this")
    return Ctx(user, await _business_for(user))


async def member_ctx(user=Depends(current_user)) -> Ctx:
    if user["role"] not in ("owner", "staff"):
        raise HTTPException(403, "Not allowed")
    return Ctx(user, await _business_for(user))


async def admin_user(user=Depends(current_user)) -> dict:
    if user["role"] != "super_admin":
        raise HTTPException(403, "Super Admin only")
    return user


async def audit(business_id, user, action, entity, entity_id=None, details=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "business_id": business_id, "user_id": user["id"], "user_name": user.get("name"),
        "action": action, "entity": entity, "entity_id": entity_id, "details": details or {},
        "created_at": now_iso(),
    })
