from enum import Enum


class ProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    GROQ = "groq"


class EvaluationDepth(str, Enum):
    ACADEMIC_PROFESSIONAL = "academic_professional"
    ACADEMIC_APPLIED = "academic_applied"
    ACADEMIC_STANDARD = "academic_standard"
    GENERAL_RESEARCH = "general_research"


class SubmissionStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIALLY_PROCESSED = "partially_processed"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadBatchStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ProviderUsageStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED_LIMIT = "blocked_limit"


class ProviderRequestType(str, Enum):
    EVALUATION = "evaluation"
    RETRY = "retry"
    TEST_CONNECTION = "test_connection"


class AppLanguage(str, Enum):
    AR = "ar"
    EN = "en"


class ThemeMode(str, Enum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


class ParserStatus(str, Enum):
    NOT_STARTED = "not_started"
    SUCCESS = "success"
    FAILED = "failed"
