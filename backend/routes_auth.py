from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import (db, new_id, now_iso, hash_pw, verify_pw, norm_phone, public_user, current_user, NOPID,
                  create_session, session_token, set_session_cookie, clear_session_cookie, revoke_sessions,
                  _hash_token, SESSION_DAYS)
from services import DEFAULT_SETTINGS

router = APIRouter(prefix="/auth")
LOCK_AFTER, LOCK_MIN = 5, 15


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str
    password: str = Field(min_length=8, max_length=128)
    business_name: str = Field(min_length=2, max_length=120)
    security_question: str = Field(min_length=5, max_length=200)
    security_answer: str = Field(min_length=2, max_length=100)


class LoginIn(BaseModel):
    phone: str
    password: str


class RecoveryIn(BaseModel):
    phone: str
    answer: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SecurityIn(BaseModel):
    current_password: str
    security_question: str = Field(min_length=5, max_length=200)
    security_answer: str = Field(min_length=2, max_length=100)


async def _check_lock(ident):
    rec = await db.login_attempts.find_one({"identifier": ident})
    if rec and rec.get("locked_until") and rec["locked_until"] > datetime.now(timezone.utc).isoformat():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")


async def _fail(ident):
    rec = await db.login_attempts.find_one_and_update({"identifier": ident}, {"$inc": {"count": 1}},
                                                      upsert=True, return_document=True)
    if rec and rec.get("count", 0) >= LOCK_AFTER:
        until = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MIN)).isoformat()
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {"locked_until": until, "count": 0}})


def _norm_answer(a):
    return " ".join(a.lower().split())


@router.post("/signup")
async def signup(body: SignupIn, request: Request, response: Response):
    phone = norm_phone(body.phone)
    if await db.users.find_one({"phone": phone}):
        raise HTTPException(409, "An account with this mobile number already exists")
    uid, bid = new_id(), new_id()
    user = {"id": uid, "name": body.name.strip(), "phone": phone, "email": None, "role": "owner",
            "business_id": bid, "staff_id": None, "password_hash": hash_pw(body.password),
            "security_question": body.security_question.strip(),
            "security_answer_hash": hash_pw(_norm_answer(body.security_answer)), "created_at": now_iso()}
    await db.users.insert_one(user)
    await db.businesses.insert_one({
        "id": bid, "name": body.business_name.strip(), "logo": None, "type": "", "location": "",
        "owner_user_id": uid, "status": "active", "onboarded": False, "active_staff_count": 0,
        "settings": dict(DEFAULT_SETTINGS), "created_at": now_iso()})
    await db.memberships.insert_one({"id": new_id(), "user_id": uid, "business_id": bid, "role": "owner",
                                     "created_at": now_iso()})
    await create_session(user, request, response)
    return {"user": public_user(user)}


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    phone = norm_phone(body.phone)
    ident = f"{request.client.host if request.client else 'x'}:{phone}"
    await _check_lock(ident)
    user = await db.users.find_one({"phone": phone}, NOPID)
    if not user or not verify_pw(body.password, user["password_hash"]):
        await _fail(ident)
        raise HTTPException(401, "Incorrect mobile number or password")
    if user.get("disabled"):
        raise HTTPException(403, "This login has been disabled")
    await db.login_attempts.delete_one({"identifier": ident})
    await create_session(user, request, response)
    return {"user": public_user(user)}


@router.get("/me")
async def me(request: Request, response: Response, user=Depends(current_user)):
    sess = request.state.session
    exp = sess["expires_at_dt"].replace(tzinfo=timezone.utc) if sess["expires_at_dt"].tzinfo is None else sess["expires_at_dt"]
    if exp - datetime.now(timezone.utc) < timedelta(days=SESSION_DAYS - 1):
        await db.sessions.update_one({"token_hash": sess["token_hash"]},
                                     {"$set": {"expires_at_dt": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)}})
        set_session_cookie(response, session_token(request))
    biz = None
    if user.get("business_id"):
        b = await db.businesses.find_one({"id": user["business_id"]}, NOPID)
        if b:
            biz = {k: b.get(k) for k in ("id", "name", "logo", "type", "location", "status", "onboarded")}
    return {"user": public_user(user), "business": biz}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = session_token(request)
    if token:
        await db.sessions.delete_one({"token_hash": _hash_token(token)})
    clear_session_cookie(response)
    return {"ok": True}


@router.post("/recovery/question")
async def recovery_question(body: RecoveryIn):
    user = await db.users.find_one({"phone": norm_phone(body.phone)}, NOPID)
    if not user or not user.get("security_question"):
        raise HTTPException(404, "No recoverable account found for this number. Staff should ask their employer.")
    return {"question": user["security_question"]}


@router.post("/recovery/reset")
async def recovery_reset(body: RecoveryIn, request: Request):
    phone = norm_phone(body.phone)
    ident = f"recovery:{phone}"
    await _check_lock(ident)
    if not body.answer or not body.new_password:
        raise HTTPException(422, "Answer and new password (min 8 characters) are required")
    user = await db.users.find_one({"phone": phone}, NOPID)
    if not user or not user.get("security_answer_hash") or not verify_pw(_norm_answer(body.answer), user["security_answer_hash"]):
        await _fail(ident)
        raise HTTPException(401, "Security answer is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    await db.login_attempts.delete_one({"identifier": ident})
    await revoke_sessions(user["id"])
    return {"ok": True}


@router.post("/change-password")
async def change_password(body: ChangePwIn, request: Request, user=Depends(current_user)):
    full = await db.users.find_one({"id": user["id"]}, NOPID)
    if not verify_pw(body.current_password, full["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    await revoke_sessions(user["id"], keep_hash=request.state.session["token_hash"])
    return {"ok": True}


@router.post("/security-question")
async def set_security(body: SecurityIn, user=Depends(current_user)):
    full = await db.users.find_one({"id": user["id"]}, NOPID)
    if not verify_pw(body.current_password, full["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "security_question": body.security_question.strip(),
        "security_answer_hash": hash_pw(_norm_answer(body.security_answer))}})
    return {"ok": True}
