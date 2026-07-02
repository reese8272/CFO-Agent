"""Single-user authentication: bcrypt password hashing + JWT bearer tokens.

v1 is single-user (see docs/THREAT_MODEL.md §1). `POST /auth/register` creates
the one and only user and returns 409 thereafter. `POST /auth/token` issues a
short-lived JWT (TTL = JWT_EXPIRY_MINUTES, the device-theft mitigation).
`get_current_user` guards protected routes. The OAuth2 password-flow shape is
kept deliberately so the future multi-tenant path builds on it directly.
"""
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from config import get_settings
from db import Base, get_session
from rate_limit import limiter

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
# bcrypt hashes only the first 72 bytes of input and bcrypt>=4 raises on longer
# input, so both hash and verify truncate identically to stay consistent.
_BCRYPT_MAX_BYTES = 72

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
router = APIRouter(prefix="/auth", tags=["auth"])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str


def _hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


# Fixed hash to verify against when the user doesn't exist, so an absent user
# and a wrong password take the same time (no username-enumeration timing oracle).
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"timing-attack-mitigation", bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(pw, password_hash.encode("utf-8"))


def _create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    existing = (await session.execute(select(User.id).limit(1))).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration is closed: a user already exists.",
        )
    password_hash = await run_in_threadpool(_hash_password, body.password)
    user = User(username=body.username, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("user registered (id=%s)", user.id)
    return TokenResponse(access_token=_create_access_token(user.id))


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = (
        await session.execute(select(User).where(User.username == form.username))
    ).scalar_one_or_none()
    # Always run bcrypt (against a dummy hash if the user is absent) so login
    # timing does not reveal whether the username exists.
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = await run_in_threadpool(_verify_password, form.password, password_hash)
    valid = user is not None and password_ok
    if not valid:
        logger.warning("failed login attempt for username=%r", form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("login ok (user_id=%s)", user.id)
    return TokenResponse(access_token=_create_access_token(user.id))


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret_key, algorithms=[JWT_ALGORITHM]
        )
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception
    user = await session.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=current_user.id, username=current_user.username)
