"""FastAPI dependencies — DB session + auth (stub for Day 1, full JWT Day 4)."""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from core.config import settings
from core.database import async_session_maker

logger = logging.getLogger(__name__) 
security = HTTPBearer(auto_error=False)#HTTPBearer will look for Authorization header and extract token, but won't raise 403 if missing/invalid — we'll handle that in get_current_user
#http bearear is a class and implements __call__ so we can use it as a dependency using object security = HTTPBearer(auto_error=False) --- IGNORE ---

from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate JWT and return the current user.
    For Day 1 walking skeleton: if no token provided, returns a
    default dev user so we can test without auth.
    """
    from sqlalchemy import select
    from core.database import User

    # If no token is provided, raise 401 immediately to trigger frontend refresh
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Validate JWT token
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],#hs256 hash function
        )#.decode returns a dict with the payload data, if token is valid and signature matches. If not, it raises JWTError which we catch below
        user_id: str = payload.get("sub") #sub is a standard claim in JWT for "subject", which we use to store user ID. We get it from the payload dict
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))#change into uuid obj
    user = result.scalar_one_or_none()#scalar is for single column result, one_or_none means it will return the user object if found, or None if not found. If multiple users somehow match (shouldn't happen with ID), it would raise an error.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
