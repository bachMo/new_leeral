from fastapi import APIRouter

from app.api.deps import PresenterDep, Uow
from app.core.languages import AVAILABLE_LANGUAGES, LANGUAGE_NAMES, Language
from app.schemas.prompts import PromptOut
from app.schemas.users import LanguageOut
from app.services.ui_prompt_service import UiPromptService

router = APIRouter(tags=["meta"])


@router.get("/languages", response_model=list[LanguageOut])
async def languages() -> list[LanguageOut]:
    return [
        LanguageOut(code=language, name=name, available=language in AVAILABLE_LANGUAGES)
        for language, name in LANGUAGE_NAMES.items()
    ]


@router.get("/prompts", response_model=list[PromptOut])
async def prompts(language: Language, uow: Uow, presenter: PresenterDep) -> list[PromptOut]:
    stored = await UiPromptService(uow.session).for_language(language)
    return [presenter.prompt(prompt) for prompt in stored]
