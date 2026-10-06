from app.ai.engine import AiEngine
from app.ai.mock.engine import MockAiEngine
from app.ai.real.engine import RealAiEngine
from app.ai.settings import AiSettings, get_ai_settings


def build_ai_engine(settings: AiSettings | None = None) -> AiEngine:
    resolved = settings or get_ai_settings()
    if resolved.ai_provider == "real":
        return RealAiEngine(resolved)
    return MockAiEngine(resolved)
