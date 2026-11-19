"""Pick the LLM client named by `LLM_PROVIDER` (decisions 0004 and 0016)."""

from app.core.config import Settings
from app.llm.anthropic import AnthropicClient
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.ollama import OllamaClient
from app.llm.openai_compat import OpenAICompatClient


def make_client(settings: Settings) -> LLMClient:
    """`fake` (demo mode, the default), `ollama` (local), `anthropic` or `dahl` (cloud)."""
    if settings.llm_provider == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        return AnthropicClient(key, settings.anthropic_model)
    if settings.llm_provider == "dahl":
        key = settings.dahl_api_key.get_secret_value() if settings.dahl_api_key else ""
        return OpenAICompatClient(key, settings.dahl_model, base_url=settings.dahl_base_url)
    return FakeClient()
