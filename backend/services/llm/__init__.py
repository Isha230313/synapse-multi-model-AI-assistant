"""
LLM Service Module
Provides a unified interface for multiple LLM providers (OpenAI, Gemini, etc.)
"""

from .base import BaseLLMProvider, ChatMessage, LLMResponse
from .openai_provider import OpenAIProvider
from .llm_service import LLMService, LLMProviderType

# Lazy import for Gemini (optional)
try:
    from .gemini_provider import GeminiProvider
except ImportError:
    GeminiProvider = None

__all__ = [
    "BaseLLMProvider",
    "ChatMessage",
    "LLMResponse",
    "OpenAIProvider",
    "LLMService",
    "LLMProviderType",
]

# Add GeminiProvider to exports if available
if GeminiProvider is not None:
    __all__.append("GeminiProvider")

