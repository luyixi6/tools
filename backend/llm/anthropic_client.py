from typing import Optional, Dict, Any
from .base_client import BaseLLMClient
from .rate_limiter import RateLimiter


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int,
                 rate_limit_rpm: int = 50, **kwargs):
        super().__init__(api_key, model, max_tokens)
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.rate_limiter = RateLimiter(rate_limit_rpm)

    async def analyze_code(
        self,
        system_prompt: str,
        code_content: str,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        await self.rate_limiter.acquire()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": code_content}
            ],
        )

        text = response.content[0].text
        return self._parse_json_response(text)
