"""LLMインスタンスの生成。"""

from langchain_core.language_models import BaseChatModel

_PROVIDERS = {
    "openai":    ("langchain_openai",    "ChatOpenAI",    {"stream_usage": True}),
    "anthropic": ("langchain_anthropic", "ChatAnthropic", {}),
}


def create_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    backend: str = "openai",
) -> BaseChatModel:
    """LangChain ChatModelを生成する。

    Args:
        provider: ``"openai"`` / ``"anthropic"`` / ``"custom"``。
        model:    モデル名。
        api_key:  APIキー。
        base_url: ベースURL（``custom`` 時は必須）。
        backend:  ``custom`` 時のSDK。``"openai"`` or ``"anthropic"``。
    """
    if provider == "custom":
        if not base_url:
            raise ValueError("base_url is required for custom provider")
        provider = backend
        if provider not in _PROVIDERS:
            raise ValueError(f"Unknown backend: {provider}. Use openai or anthropic.")

    entry = _PROVIDERS.get(provider)
    if not entry:
        raise ValueError(f"Unknown provider: {provider}. Use {', '.join(_PROVIDERS)} or custom.")

    module, cls, extra = entry
    import importlib
    kwargs = {**extra, "model": model, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return getattr(importlib.import_module(module), cls)(**kwargs)
