# src/app/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.schemas import LoginIn, TokenOut
from app.api.security import create_access_token
from app.api.deps import get_users_repo
from app.domain.models.UserModel import Role

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, users_repo = Depends(get_users_repo)):
    # DEMO ONLY:
    # - Accept login if user exists and password == "demo"
    # - In real life, validate a password hash
    try:
        user = await users_repo.get(data.user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if data.password != "demo":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    roles = [r.value if hasattr(r, "value") else r for r in user.roles]
    token = create_access_token(sub=user.user_id, roles=roles)
    return TokenOut(access_token=token)
