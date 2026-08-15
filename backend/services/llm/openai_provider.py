"""
OpenAI LLM Provider Implementation
"""
import os
import json
import re
import asyncio
import logging
from typing import Dict, List, Optional, Any
from openai import OpenAI
from openai.types.chat import ChatCompletion

from .base import BaseLLMProvider, ChatMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.default_model_name = kwargs.get("model", "gpt-3.5-turbo")
        self._client: Optional[OpenAI] = None
    
    def initialize(self) -> bool:
        """Initialize OpenAI client."""
        try:
            if not self.api_key:
                logger.warning("OpenAI API key not provided")
                return False
            
            self._client = OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI provider initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI provider: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return self._client is not None and self.api_key is not None
    
    @property
    def default_model(self) -> str:
        """Get default OpenAI model."""
        return self.default_model_name
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "openai"
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using OpenAI."""
        if not self.is_available():
            raise RuntimeError("OpenAI provider not initialized")
        
        model = model or self.default_model
        
        # Convert ChatMessage to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        try:
            # Create completion in thread pool to avoid blocking
            def _create_completion():
                return self._client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            
            response: ChatCompletion = await asyncio.to_thread(_create_completion)
            
            # Extract response
            content = response.choices[0].message.content.strip()
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                "completion_tokens": response.usage.completion_tokens if response.usage else None,
                "total_tokens": response.usage.total_tokens if response.usage else None,
            } if response.usage else None
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def chat_completion_json(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON completion using OpenAI."""
        model = model or self.default_model
        
        # Try with JSON mode first (for newer models)
        try:
            kwargs_json = kwargs.copy()
            kwargs_json["response_format"] = {"type": "json_object"}
            
            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs_json
            )
            
            # Parse JSON from response
            content = response.content.strip()
            
            # Try to extract JSON from code blocks or plain JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return json.loads(content)
        except Exception:
            # Fallback: try without JSON mode and parse manually
            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            content = response.content.strip()
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return json.loads(content)






