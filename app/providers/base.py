# app/providers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional

class BaseProvider(ABC):
    @abstractmethod
    async def completion(self, request: Dict) -> Dict:
        """Process a completion request"""
        pass

    @abstractmethod
    async def embedding(self, request: Dict) -> Optional[Dict]:
        """Process an embedding request"""
        pass