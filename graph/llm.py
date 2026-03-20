import logging

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("discord_bot")


def create_llm(
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseChatModel:
    """プロバイダー名からLLMインスタンスを生成するファクトリ関数。

    Args:
        provider: LLMプロバイダー（``"openai"`` / ``"anthropic"`` / ``"custom"``）。
        model: モデル名。未指定時はプロバイダーのデフォルト。
        api_key: APIキー。
        base_url: カスタムAPIのベースURL（``custom`` プロバイダー時は必須）。

    Returns:
        LangChainの :class:`BaseChatModel` インスタンス。

    Raises:
        ValueError: 不明なプロバイダー、または ``custom`` で ``base_url`` 未指定。
        ImportError: ``anthropic`` プロバイダーで ``langchain-anthropic`` 未導入。
    """
    match provider:
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model or "gpt-4o",
                api_key=api_key,
                base_url=base_url,
            )
        case "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=model or "claude-sonnet-4-20250514",
                    api_key=api_key,
                )
            except ImportError:
                raise ImportError(
                    "langchain-anthropic is required for Anthropic provider. "
                    "Install it with: uv add langchain-anthropic"
                )
        case "custom":
            from langchain_openai import ChatOpenAI
            if not base_url:
                raise ValueError("base_url is required for custom provider")
            return ChatOpenAI(
                model=model or "default",
                api_key=api_key or "not-needed",
                base_url=base_url,
            )
        case _:
            raise ValueError(f"Unknown provider: {provider}. Use openai, anthropic, or custom.")
