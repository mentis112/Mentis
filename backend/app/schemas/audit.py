from datetime import datetime

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    id: str
    instructor_id: str | None
    action: str
    entity_type: str
    entity_id: str
    metadata_json: dict | None
    created_at: datetime

