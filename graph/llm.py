"""LLMインスタンスの生成。"""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI


def create_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> BaseChatModel:
    """LangChain ChatModelを生成する。"""
    match provider:
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, stream_usage=True)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key, base_url=base_url)
        case _:
            raise ValueError(f"Unknown provider: {provider}. Use openai or anthropic.")
