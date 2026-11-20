"""Pick the LLM client named by `LLM_PROVIDER` (decisions 0004, 0016, 0017, 0018 and 0019)."""

from collections.abc import Callable

from app.core.config import Settings
from app.llm.anthropic import AnthropicClient
from app.llm.base import LLMClient, LLMError
from app.llm.fake import FakeClient
from app.llm.fallback import FallbackClient, ollama_available, switched_to
from app.llm.ollama import OllamaClient
from app.llm.openai_compat import GROQ_URL, OpenAICompatClient
from app.llm.ratelimit import MINUTE_WAIT_S

# The free tier allows 8000 tokens per minute, counting `max_tokens` before the answer; a
# 429 says how long to wait (`retry-after`), often tens of seconds: waited out up to a minute.
GROQ_MAX_TOKENS = 2048
GROQ_RETRIES = 4
GROQ_MAX_RETRY_WAIT_S = MINUTE_WAIT_S


CLOUD = ("anthropic", "dahl", "groq")


def make_client(settings: Settings) -> LLMClient:
    """The configured provider. `auto` is the startup check's choice without questions
    (decision 0019), made once per process. A cloud provider gets the `LLM_FALLBACK` chain
    (decision 0018): without its key the first available fallback is used instead, and a
    turn that hits its daily limit moves to it, for the rest of the process."""
    if settings.llm_provider == "auto":
        from app.llm.check import resolve_auto

        settings = settings.model_copy(update={"llm_provider": resolve_auto(settings)})
    fallbacks = _fallbacks(settings) if settings.llm_provider in CLOUD else []
    if not fallbacks:
        return _primary(settings)
    if (switched := switched_to()) is not None:
        # The recorded fallback, or a later one if it went away (Ollama stopped).
        names = [name for name, _ in fallbacks]
        start = names.index(switched) if switched in names else 0
        for _, factory in fallbacks[start:]:
            client = factory()
            if client is not None:
                return client
    try:
        primary = _primary(settings)
    except LLMError:
        for _, factory in fallbacks:
            client = factory()
            if client is not None:
                return client
        raise
    return FallbackClient(primary, fallbacks)


def effective_provider(settings: Settings) -> str:
    """The provider the next chat turn uses: `auto` resolved, and the fallback after a
    daily limit (what the health check reports)."""
    name = settings.llm_provider
    if name == "auto":
        from app.llm.check import resolve_auto

        name = resolve_auto(settings)
    return (switched_to() or name) if name in CLOUD else name


def _fallbacks(settings: Settings) -> list[tuple[str, Callable[[], LLMClient | None]]]:
    def ollama() -> LLMClient | None:
        if not ollama_available(settings.ollama_base_url, settings.ollama_model):
            return None
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)

    known: dict[str, Callable[[], LLMClient | None]] = {"ollama": ollama, "fake": FakeClient}
    names = [n.strip().lower() for n in settings.llm_fallback.split(",") if n.strip()]
    return [(name, known[name]) for name in names if name in known]


def _primary(settings: Settings) -> LLMClient:
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
