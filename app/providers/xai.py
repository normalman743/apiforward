# app/providers/xai.py
from app.providers.base import BaseProvider
import json
import base64
import httpx
from openai import AsyncOpenAI  # Changed to AsyncOpenAI
from typing import Dict, Optional

class XAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(  # Changed to AsyncOpenAI
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        
    async def completion(self, request: Dict) -> Dict:
        messages = request.pop("messages", [])
        
        # Handle image inputs
        for message in messages:
            if isinstance(message.get("content"), list):
                new_content = []
                for content in message["content"]:
                    if content.get("type") == "image_url":
                        if content["image_url"]["url"].startswith("data:"):
                            new_content.append(content)
                        else:
                            image_data = await self._get_image_data(content["image_url"]["url"])
                            new_content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": content["image_url"].get("detail", "high")
                                }
                            })
                message["content"] = new_content
        
        # Create completion with async client
        response = await self.client.chat.completions.create(
            messages=messages,
            **request
        )
        return response.model_dump()

    async def embedding(self, request: Dict) -> Optional[Dict]:
        """
        XAI doesn't currently support embeddings
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