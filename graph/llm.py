"""LLMインスタンスの生成。"""

from langchain_core.language_models import BaseChatModel


def create_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> BaseChatModel:
    """LangChain ChatModelを生成する。"""
    match provider:
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, stream_usage=True)
        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model, api_key=api_key, base_url=base_url)
        case _:
            raise ValueError(f"Unknown provider: {provider}. Use openai or anthropic.")
