# src/app/api/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.infra.db import get_db
from app.infra.users_repo import MongoUsersRepo
from app.domain.models.UserModel import User, Role

# --- Config (tune via env if you like) ---
JWT_SECRET = "change-me-in-env"
JWT_ALG    = "HS256"
JWT_EXPIRE_MINUTES = 60

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(*, sub: str, roles: list[str], expires_minutes: int = JWT_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(token: str = Depends(oauth2)) -> User:
    # Parse token
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        sub = payload.get("sub")
        if not sub:
            raise JWTError("Missing subject")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Load user from DB (by user_id)
    db = get_db()
    repo = MongoUsersRepo(db)
    try:
        user = await repo.get(sub)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if Role.ADMIN not in user.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
