from enum import StrEnum


class Platform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class Channel(StrEnum):
    APP = "app"
    WHATSAPP = "whatsapp"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    UNREADABLE = "unreadable"
    FAILED = "failed"


class DocumentCategory(StrEnum):
    HEALTH = "health"
    MONEY = "money"
    SCHOOL = "school"
    ADMIN = "admin"
    OTHER = "other"


class Urgency(StrEnum):
    URGENT = "urgent"
    SOON = "soon"
    NONE = "none"


class ExplanationVariant(StrEnum):
    STANDARD = "standard"
    SIMPLE = "simple"


class KeyPointKind(StrEnum):
    ACTION = "action"
    DATE = "date"
    AMOUNT = "amount"
    INFO = "info"


class LineStatus(StrEnum):
    SURE = "sure"
    TO_CHECK = "to_check"
    UNREADABLE = "unreadable"


class ConversationKind(StrEnum):
    DOCUMENT = "document"
    WRITING = "writing"
    FREE = "free"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ContentType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    FILE = "file"


class MessageStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class WhatsAppDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class WhatsAppMessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    BUTTON = "button"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    UNSUPPORTED = "unsupported"


class WhatsAppMessageStatus(StrEnum):
    RECEIVED = "received"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsAppSessionState(StrEnum):
    CHOOSING_LANGUAGE = "choosing_language"
    IDLE = "idle"
    DOCUMENT_QUESTION = "document_question"
    CONFIRMING_QUESTION = "confirming_question"


class WritingType(StrEnum):
    CV_COVER_LETTER = "cv_cover_letter"
    REQUEST_LETTER = "request_letter"
    BANK_LETTER = "bank_letter"
    OTHER = "other"


class WritingStatus(StrEnum):
    COLLECTING = "collecting"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class WritingOutputKind(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    LETTER = "letter"


class WordCategory(StrEnum):
    HEALTH = "health"
    MONEY = "money"
    SCHOOL = "school"
    ADMIN = "admin"
    COMMON = "common"


class PlanCode(StrEnum):
    FREE = "free"
    LEERAL_PLUS = "leeral_plus"


class PaymentProvider(StrEnum):
    SIMULATED = "simulated"
    PAYDUNYA = "paydunya"
    WAVE = "wave"


class PaymentMethod(StrEnum):
    WAVE = "wave"
    ORANGE_MONEY = "orange_money"
    FREE_MONEY = "free_money"
    CARD = "card"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubscriptionOrigin(StrEnum):
    PAYMENT = "payment"
    GIFT = "gift"


class UsageFeature(StrEnum):
    DOCUMENT = "document"
    WRITING = "writing"
    PRACTICE = "practice"


class AiJobType(StrEnum):
    EXPLAIN_DOCUMENT = "explain_document"
    LOCALIZE_EXPLANATION = "localize_explanation"
    ANSWER_QUESTION = "answer_question"
    ASK_WRITING_STEP = "ask_writing_step"
    ANALYZE_WRITING_ANSWER = "analyze_writing_answer"
    GENERATE_WRITING = "generate_writing"
    EXTRACT_WORDS = "extract_words"


class AiJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
