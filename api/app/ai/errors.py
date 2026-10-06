from app.core.errors import AppError, ErrorCode


class AiError(AppError):
    default_code = ErrorCode.AI_PROVIDER_UNAVAILABLE

    def __init__(self, detail: str, *, code: ErrorCode | None = None) -> None:
        super().__init__(code or self.default_code, detail=detail)


class AiUnavailableError(AiError):
    default_code = ErrorCode.AI_PROVIDER_UNAVAILABLE


class AiAuthError(AiError):
    default_code = ErrorCode.AI_PROVIDER_AUTH


class AiOutputError(AiError):
    default_code = ErrorCode.AI_OUTPUT_INVALID


class AiInputError(AiError):
    default_code = ErrorCode.VALIDATION_FAILED


class TranslationError(AiError):
    default_code = ErrorCode.TRANSLATION_FAILED
