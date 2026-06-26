from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instructor import AuthSession, Instructor


class InstructorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> Instructor | None:
        result = await self.session.execute(select(Instructor).where(Instructor.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, instructor_id: str) -> Instructor | None:
        result = await self.session.execute(select(Instructor).where(Instructor.id == instructor_id))
        return result.scalar_one_or_none()

    async def create(self, *, username: str, email: str, password_hash: str) -> Instructor:
        instructor = Instructor(username=username, email=email, password_hash=password_hash)
        self.session.add(instructor)
        await self.session.flush()
        return instructor

    async def create_session(
        self,
        *,
        instructor_id: str,
        refresh_token_hash: str,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> AuthSession:
        auth_session = AuthSession(
            instructor_id=instructor_id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def get_session(self, session_id: str) -> AuthSession | None:
        result = await self.session.execute(select(AuthSession).where(AuthSession.id == session_id))
        return result.scalar_one_or_none()

    async def revoke_session(self, auth_session: AuthSession) -> None:
        auth_session.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
