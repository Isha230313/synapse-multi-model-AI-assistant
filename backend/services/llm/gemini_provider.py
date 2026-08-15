"""
Google Gemini LLM Provider Implementation
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any

from .base import BaseLLMProvider, ChatMessage, LLMResponse

logger = logging.getLogger(__name__)

# Lazy import - only import if available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    # Don't log warning here - let LLMService handle it


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.default_model_name = kwargs.get("model", "gemini-3-pro-preview")
        self._client = None
    
    def initialize(self) -> bool:
        """Initialize Gemini client."""
        if not GEMINI_AVAILABLE:
            logger.error("❌ google-generativeai package not installed. Install with: pip install google-generativeai")
            return False
        
        try:
            if not self.api_key:
                logger.warning("Gemini API key not provided")
                return False
            
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.default_model_name)
            logger.info("✅ Gemini provider initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini provider: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return GEMINI_AVAILABLE and self._client is not None and self.api_key is not None
    
    @property
    def default_model(self) -> str:
        """Get default Gemini model."""
        return self.default_model_name
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "gemini"
    
    def _convert_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """Convert chat messages to Gemini prompt format."""
        prompt_parts = []
        
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}\n")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}\n")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}\n")
        
        return "".join(prompt_parts)
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using Gemini."""
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-generativeai package not installed. Install with: pip install google-generativeai")
        
        if not self.is_available():
            raise RuntimeError("Gemini provider not initialized")
        
        model_name = model or self.default_model
        
        # Create model instance
        generation_config = {
            "temperature": temperature,
        }
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        # Update with any additional config
        generation_config.update(kwargs)
        
        try:
            gemini_model = genai.GenerativeModel(model_name)
            prompt = self._convert_messages_to_prompt(messages)
            
            # Generate content - use sync method wrapped in asyncio
            import asyncio
            def _generate_content():
                return gemini_model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
            
            response = await asyncio.to_thread(_generate_content)
            
            # Handle response - check if text is available
            if hasattr(response, 'text') and response.text:
                content = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                # Try to get text from candidates
                content = response.candidates[0].content.parts[0].text.strip() if response.candidates[0].content.parts else ""
            else:
                raise ValueError("No text content in Gemini response")
            
            # Extract usage info if available
            usage = None
            if hasattr(response, "usage_metadata"):
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", None),
                    "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", None),
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", None),
                }
            
            return LLMResponse(
                content=content,
                model=model_name,
                usage=usage,
                finish_reason=getattr(response.candidates[0], "finish_reason", None) if response.candidates else None
            )
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    async def chat_completion_json(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON completion using Gemini."""
        # Add JSON instruction to system message
        json_messages = messages.copy()
        if json_messages and json_messages[0].role == "system":
            json_messages[0].content += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no code blocks, just pure JSON."
        else:
            json_messages.insert(0, ChatMessage(
                role="system",
                content="Respond ONLY with valid JSON. No markdown, no code blocks, just pure JSON."
            ))
        
        response = await self.chat_completion(
            messages=json_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # Parse JSON from response
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.error(f"Response content: {content[:200]}")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")

