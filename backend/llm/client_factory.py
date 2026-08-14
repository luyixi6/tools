from typing import Optional, Dict, Any
from .base_client import BaseLLMClient


SUPPORTED_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic Claude",
        "default_model": "claude-sonnet-4-20250514",
        "client_cls": "backend.llm.anthropic_client.AnthropicClient",
    },
    "openai": {
        "name": "OpenAI",
        "default_model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
    "deepseek": {
        "name": "DeepSeek",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
    "zhipu": {
        "name": "ZhipuAI (GLM)",
        "default_model": "glm-4-plus",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
    "qwen": {
        "name": "Tongyi Qwen",
        "default_model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
    "openai_compatible": {
        "name": "OpenAI Compatible",
        "default_model": "gpt-4o",
        "client_cls": "backend.llm.openai_client.OpenAIClient",
    },
}


def create_client(
    provider: str,
    api_key: str,
    model: Optional[str] = None,
    max_tokens: int = 8192,
    base_url: Optional[str] = None,
    rate_limit_rpm: int = 50,
    extra_headers: Optional[Dict[str, str]] = None,
    **kwargs,
) -> BaseLLMClient:
    provider = provider.lower().strip()
    provider_info = SUPPORTED_PROVIDERS.get(provider)
    if not provider_info:
        available = ", ".join(SUPPORTED_PROVIDERS.keys())
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Available providers: {available}"
        )

    model = model or provider_info.get("default_model", "gpt-4o")
    base_url = base_url or provider_info.get("base_url", "")

    if "anthropic" == provider:
        from .anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            rate_limit_rpm=rate_limit_rpm,
        )
    else:
        from .openai_client import OpenAIClient
        return OpenAIClient(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            base_url=base_url,
            rate_limit_rpm=rate_limit_rpm,
            extra_headers=extra_headers,
        )


def get_provider_list() -> list:
    return [
        {"id": k, "name": v["name"], "default_model": v["default_model"]}
        for k, v in SUPPORTED_PROVIDERS.items()
    ]


def get_provider_info(provider: str) -> Optional[Dict[str, Any]]:
    return SUPPORTED_PROVIDERS.get(provider.lower().strip())
