"""Pick the LLM client named by `LLM_PROVIDER` (decisions 0004, 0016 and 0017)."""

from app.core.config import Settings
from app.llm.anthropic import AnthropicClient
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.ollama import OllamaClient
from app.llm.openai_compat import GROQ_URL, OpenAICompatClient

# The free tier allows 8000 tokens per minute, counting `max_tokens` before the answer; a
# 429 says how long to wait (`retry-after`), often tens of seconds.
GROQ_MAX_TOKENS = 2048
GROQ_RETRIES = 4
GROQ_MAX_RETRY_WAIT_S = 65.0


def make_client(settings: Settings) -> LLMClient:
    """`fake` (demo mode, the default), `ollama` (local), `anthropic`, `dahl` or `groq` (cloud)."""
    if settings.llm_provider == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        return AnthropicClient(key, settings.anthropic_model)
    if settings.llm_provider == "dahl":
        key = settings.dahl_api_key.get_secret_value() if settings.dahl_api_key else ""
        return OpenAICompatClient(key, settings.dahl_model, base_url=settings.dahl_base_url)
    if settings.llm_provider == "groq":
        key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        return OpenAICompatClient(
            key,
            settings.groq_model,
            provider="groq",
            base_url=GROQ_URL,
            key_env="GROQ_API_KEY",
            model_env="GROQ_MODEL",
            max_tokens=GROQ_MAX_TOKENS,
            tools_when_off=False,
            retries=GROQ_RETRIES,
            max_retry_wait=GROQ_MAX_RETRY_WAIT_S,
        )
    return FakeClient()
