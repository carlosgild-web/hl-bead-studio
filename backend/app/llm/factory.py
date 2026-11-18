"""Pick the LLM client named by `LLM_PROVIDER` (decision 0004)."""

from app.core.config import Settings
from app.llm.anthropic import AnthropicClient
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.ollama import OllamaClient


def make_client(settings: Settings) -> LLMClient:
    """`fake` (demo mode, the default), `ollama` (local) or `anthropic` (cloud)."""
    if settings.llm_provider == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        return AnthropicClient(key, settings.anthropic_model)
    return FakeClient()
