from typing import Optional, Dict, Any
from .base_client import BaseLLMClient
from .rate_limiter import RateLimiter


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int,
                 base_url: Optional[str] = None,
                 rate_limit_rpm: int = 50,
                 extra_headers: Optional[Dict[str, str]] = None,
                 **kwargs):
        super().__init__(api_key, model, max_tokens)
        from openai import AsyncOpenAI
        client_args = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        if extra_headers:
            client_args["default_headers"] = extra_headers
        self.client = AsyncOpenAI(**client_args)
        self.rate_limiter = RateLimiter(rate_limit_rpm)

    async def analyze_code(
        self,
        system_prompt: str,
        code_content: str,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        await self.rate_limiter.acquire()

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": code_content},
            ],
        )

        text = response.choices[0].message.content or ""
        return self._parse_json_response(text)
