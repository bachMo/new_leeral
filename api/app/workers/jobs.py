from enum import StrEnum


class Job(StrEnum):
    PROCESS_DOCUMENT = "process_document"
    LOCALIZE_EXPLANATION = "localize_explanation"
    EXTRACT_WORDS = "extract_words"
    ANSWER_MESSAGE = "answer_message"
    ASK_WRITING_STEP = "ask_writing_step"
    ANALYZE_WRITING_ANSWER = "analyze_writing_answer"
    GENERATE_WRITING = "generate_writing"
    HANDLE_WHATSAPP_MESSAGE = "handle_whatsapp_message"
    PROMOTE_GUEST_FILES = "promote_guest_files"
    DELETE_STORAGE_PREFIX = "delete_storage_prefix"
