import os
import time

import bcrypt
import jwt
from fastapi import Cookie, HTTPException

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _secret_key() -> str:
    secret = os.getenv("AUTH_SECRET_KEY")
    if not secret:
        raise RuntimeError("AUTH_SECRET_KEY environment variable is not set")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


class CurrentUser:
    def __init__(self, id: int, username: str):
        self.id = id
        self.username = username


def get_current_user(session: str | None = Cookie(default=None)) -> CurrentUser:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_session_token(session)
    return CurrentUser(id=payload["user_id"], username=payload["username"])


def is_production() -> bool:
    return os.getenv("ENV", "development").lower() == "production"


def cookie_settings() -> dict:
    """
    In production the frontend (Vercel) and backend (Render) are on different
    top-level domains, i.e. cross-site, not just cross-origin. Cross-site
    cookies are only sent by browsers when SameSite=None, which in turn
    requires Secure=True. Locally, frontend and backend are both on
    localhost (same-site, different ports), so Lax works and Secure is not
    required (no HTTPS in dev).
    """
    production = is_production()
    return {"secure": production, "samesite": "none" if production else "lax"}
