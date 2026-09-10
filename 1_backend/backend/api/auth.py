"""Router de autenticación: login (argon2 + JWT) y datos del usuario actual."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from db.session import get_db
from services.security import authenticate, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserInfo(BaseModel):
    id: int
    email: str
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


@router.post("/login", response_model=LoginResponse, summary="Iniciar sesión")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = await authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas"
        )
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "username": user.username, "role": user.role}
    )
    return LoginResponse(
        access_token=token,
        user=UserInfo(id=user.id, email=user.email, username=user.username, role=user.role),
    )


@router.get("/me", response_model=UserInfo, summary="Usuario autenticado")
async def me(user: User = Depends(get_current_user)) -> UserInfo:
    return UserInfo(id=user.id, email=user.email, username=user.username, role=user.role)
