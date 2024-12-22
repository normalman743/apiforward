# app/providers/anthropic.py
from app.providers.base import BaseProvider
import anthropic
import base64
import httpx
from typing import Dict, Optional

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        
    async def completion(self, request: Dict) -> Dict:
        messages = request.pop("messages", [])
        
        # Handle image inputs
        for message in messages:
            if isinstance(message.get("content"), list):
                new_content = []
                for content in message["content"]:
                    if content.get("type") == "image":
                        image_data = await self._get_image_data(content["source"]["data"])
                        new_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        })
                message["content"] = new_content
        
        response = await self.client.messages.create(
            messages=messages,
            **request
        )
        return response.model_dump()

    async def embedding(self, request: Dict) -> Optional[Dict]:
        """
        Anthropic doesn't currently support embeddings
        Returns None to indicate no embedding support
        """
        return None

    async def _get_image_data(self, url: str) -> str:
        if url.startswith("data:"):
            return url.split(",")[1]
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                return base64.b64encode(response.content).decode("utf-8")