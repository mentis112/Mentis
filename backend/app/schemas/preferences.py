from app.models.enums import AppLanguage, ThemeMode
from pydantic import BaseModel

from app.schemas.common import ORMModel


class PreferenceResponse(ORMModel):
    id: str
    instructor_id: str
    language: AppLanguage
    theme: ThemeMode


class PreferenceUpdateRequest(BaseModel):
    language: AppLanguage
    theme: ThemeMode
