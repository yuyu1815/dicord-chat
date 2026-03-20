import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("discord_bot")


def create_llm(
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseChatModel:
    """Factory: create LLM instance from provider name."""
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
