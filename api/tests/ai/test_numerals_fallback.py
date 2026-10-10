from typing import Any

from app.ai.errors import AiUnavailableError
from app.ai.real import numerals
from app.core.languages import Language


class _UnavailableClient:
    async def complete_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AiUnavailableError("translator down")


async def test_numbers_stay_as_digits_when_the_model_is_down() -> None:
    text = "Il faut payer 1500000 FCFA."

    spoken = await numerals.spell_out_numbers(
        _UnavailableClient(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        text,
        Language.PULAAR,
    )

    assert spoken == text
