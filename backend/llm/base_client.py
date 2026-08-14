from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLMClient(ABC):
    def __init__(self, api_key: str, model: str, max_tokens: int, **kwargs):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @abstractmethod
    async def analyze_code(
        self,
        system_prompt: str,
        code_content: str,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send code to the LLM and return structured analysis result."""
        ...

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        import json
        try:
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            return {
                "issues": [],
                "parse_error": str(e),
                "raw_response": text[:1000],
            }
