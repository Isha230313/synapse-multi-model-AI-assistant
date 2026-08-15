"""
Base LLM Provider Interface
All LLM providers must implement this interface
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Represents a chat message."""
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Standardized LLM response."""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class BaseLLMProvider(ABC):
    """Base class for all LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            api_key: API key for the provider
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
        self._client = None
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the provider client.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and configured.
        
        Returns:
            True if provider is ready to use
        """
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a chat completion.
        
        Args:
            messages: List of chat messages
            model: Model name (uses default if not provided)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def chat_completion_json(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a chat completion with JSON response format.
        
        Args:
            messages: List of chat messages
            model: Model name (uses default if not provided)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Parsed JSON dictionary
        """
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model name for this provider."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass






