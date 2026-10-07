from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    FORBIDDEN = "FORBIDDEN"
    ACCOUNT_REQUIRED = "ACCOUNT_REQUIRED"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    INVALID_PHONE_NUMBER = "INVALID_PHONE_NUMBER"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_TOO_MANY_ATTEMPTS = "OTP_TOO_MANY_ATTEMPTS"
    OTP_RESEND_TOO_SOON = "OTP_RESEND_TOO_SOON"
    OTP_DELIVERY_FAILED = "OTP_DELIVERY_FAILED"
    TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"
    LANGUAGE_NOT_AVAILABLE = "LANGUAGE_NOT_AVAILABLE"

    FILE_MISSING = "FILE_MISSING"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_TYPE_NOT_SUPPORTED = "FILE_TYPE_NOT_SUPPORTED"
    TOO_MANY_PAGES = "TOO_MANY_PAGES"
    IMAGE_TOO_BLURRY = "IMAGE_TOO_BLURRY"
    IMAGE_TOO_DARK = "IMAGE_TOO_DARK"
    IMAGE_UNREADABLE = "IMAGE_UNREADABLE"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"
    AUDIO_UNREADABLE = "AUDIO_UNREADABLE"
    AUDIO_EMPTY = "AUDIO_EMPTY"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    QUESTION_EMPTY = "QUESTION_EMPTY"
    QUESTION_TRANSLATION_FAILED = "QUESTION_TRANSLATION_FAILED"

    WRITING_NOT_COLLECTING = "WRITING_NOT_COLLECTING"
    WRITING_NO_PENDING_ANSWER = "WRITING_NO_PENDING_ANSWER"
    PRACTICE_SESSION_CLOSED = "PRACTICE_SESSION_CLOSED"
    NOT_ENOUGH_WORDS = "NOT_ENOUGH_WORDS"

    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PLAN_REQUIRED = "PLAN_REQUIRED"
    PAYMENT_NOT_PENDING = "PAYMENT_NOT_PENDING"

    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_PROVIDER_AUTH = "AI_PROVIDER_AUTH"
    AI_OUTPUT_INVALID = "AI_OUTPUT_INVALID"
    TRANSLATION_FAILED = "TRANSLATION_FAILED"

    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    status_code: int
    message: str
    retryable: bool = False


ERROR_CATALOG: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.VALIDATION_FAILED: ErrorSpec(422, "Certaines informations ne sont pas valides."),
    ErrorCode.NOT_FOUND: ErrorSpec(404, "Élément introuvable."),
    ErrorCode.UNAUTHENTICATED: ErrorSpec(401, "Connecte-toi pour continuer."),
    ErrorCode.TOKEN_EXPIRED: ErrorSpec(401, "Ta session a expiré.", retryable=True),
    ErrorCode.FORBIDDEN: ErrorSpec(403, "Tu n'as pas accès à cet élément."),
    ErrorCode.ACCOUNT_REQUIRED: ErrorSpec(403, "Crée ton compte pour utiliser cette fonction."),
    ErrorCode.CONFLICT: ErrorSpec(409, "Cette action a déjà été faite."),
    ErrorCode.RATE_LIMITED: ErrorSpec(429, "Trop de demandes. Réessaie dans un instant.", True),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(500, "Un problème est survenu. Réessaie.", True),
    ErrorCode.INVALID_PHONE_NUMBER: ErrorSpec(422, "Ce numéro de téléphone n'est pas valide."),
    ErrorCode.OTP_INVALID: ErrorSpec(422, "Ce code n'est pas le bon."),
    ErrorCode.OTP_EXPIRED: ErrorSpec(422, "Ce code a expiré. Demande un nouveau code."),
    ErrorCode.OTP_TOO_MANY_ATTEMPTS: ErrorSpec(429, "Trop d'essais. Demande un nouveau code."),
    ErrorCode.OTP_RESEND_TOO_SOON: ErrorSpec(
        429, "Attends un peu avant de redemander un code.", True
    ),
    ErrorCode.OTP_DELIVERY_FAILED: ErrorSpec(
        502, "Le code n'a pas pu être envoyé sur WhatsApp.", True
    ),
    ErrorCode.TERMS_NOT_ACCEPTED: ErrorSpec(422, "Accepte les conditions pour continuer."),
    ErrorCode.LANGUAGE_NOT_AVAILABLE: ErrorSpec(422, "Cette langue arrive bientôt."),
    ErrorCode.FILE_MISSING: ErrorSpec(422, "Ajoute au moins une photo ou un fichier."),
    ErrorCode.FILE_TOO_LARGE: ErrorSpec(413, "Ce fichier est trop lourd."),
    ErrorCode.FILE_TYPE_NOT_SUPPORTED: ErrorSpec(
        415, "Ce type de fichier n'est pas pris en charge."
    ),
    ErrorCode.TOO_MANY_PAGES: ErrorSpec(422, "Ce document a trop de pages."),
    ErrorCode.IMAGE_TOO_BLURRY: ErrorSpec(422, "La photo est floue. Reprends-la sans bouger."),
    ErrorCode.IMAGE_TOO_DARK: ErrorSpec(422, "La photo est trop sombre. Mets-toi à la lumière."),
    ErrorCode.IMAGE_UNREADABLE: ErrorSpec(422, "La photo est illisible. Reprends-la de plus près."),
    ErrorCode.DOCUMENT_UNREADABLE: ErrorSpec(422, "Leeral n'arrive pas à lire ce document."),
    ErrorCode.DOCUMENT_NOT_READY: ErrorSpec(409, "Le document est encore en lecture.", True),
    ErrorCode.AUDIO_UNREADABLE: ErrorSpec(422, "Leeral n'a pas compris le message vocal."),
    ErrorCode.AUDIO_EMPTY: ErrorSpec(422, "Le message vocal est vide."),
    ErrorCode.AUDIO_TOO_LONG: ErrorSpec(422, "Ce message vocal est trop long. Fais plus court."),
    ErrorCode.QUESTION_EMPTY: ErrorSpec(422, "Pose ta question à voix haute ou écris-la."),
    ErrorCode.QUESTION_TRANSLATION_FAILED: ErrorSpec(
        502, "Leeral n'a pas compris ta question dans cette langue. Écris-la en français.", True
    ),
    ErrorCode.WRITING_NOT_COLLECTING: ErrorSpec(409, "Ce document est déjà terminé."),
    ErrorCode.WRITING_NO_PENDING_ANSWER: ErrorSpec(409, "Il n'y a pas de réponse à confirmer."),
    ErrorCode.PRACTICE_SESSION_CLOSED: ErrorSpec(409, "Cette séance est terminée."),
    ErrorCode.NOT_ENOUGH_WORDS: ErrorSpec(409, "Il n'y a pas encore assez de mots à réviser."),
    ErrorCode.QUOTA_EXCEEDED: ErrorSpec(402, "Tu as atteint la limite de ta formule."),
    ErrorCode.PLAN_REQUIRED: ErrorSpec(402, "Cette fonction fait partie de Leeral+."),
    ErrorCode.PAYMENT_NOT_PENDING: ErrorSpec(409, "Ce paiement est déjà traité."),
    ErrorCode.AI_PROVIDER_UNAVAILABLE: ErrorSpec(503, "Leeral est très demandé. Réessaie.", True),
    ErrorCode.AI_PROVIDER_AUTH: ErrorSpec(503, "Leeral est momentanément indisponible.", True),
    ErrorCode.AI_OUTPUT_INVALID: ErrorSpec(502, "Leeral n'a pas pu terminer. Réessaie.", True),
    ErrorCode.TRANSLATION_FAILED: ErrorSpec(502, "Leeral n'a pas pu traduire ce document.", True),
    ErrorCode.WEBHOOK_SIGNATURE_INVALID: ErrorSpec(401, "Signature invalide."),
}


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        *,
        detail: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.spec = ERROR_CATALOG[code]
        self.detail = detail
        self.fields = fields or {}
        super().__init__(detail or code.value)

    @property
    def status_code(self) -> int:
        return self.spec.status_code

    @property
    def message_key(self) -> str:
        return f"errors.{self.code.value.lower()}"

    @property
    def audio_key(self) -> str:
        return f"error.{self.code.value.lower()}"


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(ErrorCode.NOT_FOUND, detail=f"{resource} not found")
