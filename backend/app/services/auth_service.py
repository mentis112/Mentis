from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.instructor import AuthSession, Instructor
from app.repositories.instructor_repository import InstructorRepository
from app.repositories.preference_repository import PreferenceRepository
from app.schemas.auth import InstructorProfile, LoginRequest, RegisterRequest, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InstructorRepository(session)
        self.preference_repository = PreferenceRepository(session)
        self.audit_service = AuditService(session)

    async def register(
        self,
        payload: RegisterRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse:
        existing = await self.repository.get_by_email(payload.email.lower())
        if existing:
            raise ConflictError("Email is already registered")

        instructor = await self.repository.create(
            username=payload.username.strip(),
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
        )
        await self.preference_repository.create_default(instructor.id)
        token_response = await self._issue_tokens(
            instructor,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.audit_service.log(
            instructor_id=instructor.id,
            action="auth.register",
            entity_type="instructor",
            entity_id=instructor.id,
            metadata_json={"email": instructor.email},
        )
        await self.session.commit()
        return token_response

    async def login(
        self,
        payload: LoginRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse:
        instructor = await self.repository.get_by_email(payload.email.lower())
        if not instructor or not verify_password(payload.password, instructor.password_hash):
            raise AuthenticationError("Invalid credentials")

        response = await self._issue_tokens(
            instructor,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.audit_service.log(
            instructor_id=instructor.id,
            action="auth.login",
            entity_type="instructor",
            entity_id=instructor.id,
        )
        await self.session.commit()
        return response

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, refresh=True)
        auth_session = await self._validate_refresh_session(payload["sid"], refresh_token)
        instructor = await self.repository.get_by_id(payload["sub"])
        if not instructor:
            raise AuthenticationError("Account no longer exists")

        new_refresh_token = create_refresh_token(instructor.id, auth_session.id)
        auth_session.refresh_token_hash = hash_password(new_refresh_token)
        auth_session.expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days)
        access_token = create_access_token(instructor.id, auth_session.id)
        await self.session.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            instructor=InstructorProfile.model_validate(instructor),
        )

    async def logout(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token, refresh=True)
        auth_session = await self._validate_refresh_session(payload["sid"], refresh_token)
        await self.repository.revoke_session(auth_session)
        await self.audit_service.log(
            instructor_id=payload["sub"],
            action="auth.logout",
            entity_type="auth_session",
            entity_id=auth_session.id,
        )
        await self.session.commit()

    async def change_password(
        self,
        *,
        instructor_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        instructor = await self.repository.get_by_id(instructor_id)
        if not instructor:
            raise AuthenticationError("Account no longer exists")
        if not verify_password(current_password, instructor.password_hash):
            raise AuthenticationError("Current password is incorrect")
        if current_password == new_password:
            raise ValidationError("New password must be different from the current password")

        instructor.password_hash = hash_password(new_password)
        await self.audit_service.log(
            instructor_id=instructor.id,
            action="auth.change_password",
            entity_type="instructor",
            entity_id=instructor.id,
        )
        await self.session.commit()

    async def _issue_tokens(
        self,
        instructor: Instructor,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse:
        expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days)
        auth_session = await self.repository.create_session(
            instructor_id=instructor.id,
            refresh_token_hash="pending",
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        refresh_token = create_refresh_token(instructor.id, auth_session.id)
        auth_session.refresh_token_hash = hash_password(refresh_token)
        access_token = create_access_token(instructor.id, auth_session.id)
        await self.session.flush()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            instructor=InstructorProfile.model_validate(instructor),
        )

    async def _validate_refresh_session(self, session_id: str, refresh_token: str) -> AuthSession:
        auth_session = await self.repository.get_session(session_id)
        if not auth_session:
            raise AuthenticationError("Invalid session")
        if auth_session.revoked_at is not None or auth_session.expires_at <= datetime.now(timezone.utc):
            raise AuthenticationError("Session has expired")
        if not verify_password(refresh_token, auth_session.refresh_token_hash):
            raise AuthenticationError("Invalid refresh token")
        return auth_session
