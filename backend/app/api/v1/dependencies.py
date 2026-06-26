from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db
from app.repositories.instructor_repository import InstructorRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_instructor(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise AuthenticationError("Invalid access token") from exc

    repository = InstructorRepository(db)
    auth_session = await repository.get_session(payload["sid"])
    if not auth_session or auth_session.revoked_at is not None:
        raise AuthenticationError("Session is not active")
    if auth_session.expires_at <= datetime.now(timezone.utc):
        raise AuthenticationError("Session has expired")

    instructor = await repository.get_by_id(payload["sub"])
    if not instructor:
        raise AuthenticationError("Account not found")
    return instructor
