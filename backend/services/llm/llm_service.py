"""
LLM Service Manager
Manages multiple LLM providers and provides a unified interface
"""
import os
import json
import logging
from enum import Enum
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from .base import BaseLLMProvider, ChatMessage, LLMResponse
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Lazy import for Gemini to avoid errors if package not installed
GeminiProvider = None
try:
    from .gemini_provider import GeminiProvider
except ImportError:
    logger.debug("Gemini provider not available (google-generativeai not installed)")

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)


class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    GEMINI = "gemini"


_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'settings.json')

def _load_saved_provider() -> Optional[str]:
    """Load the user's last chosen provider from settings file."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, 'r') as f:
                return json.load(f).get('llm_provider')
    except Exception:
        pass
    return None

def _save_provider(provider: str):
    """Persist the user's provider choice to settings file."""
    os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
    try:
        settings = {}
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        settings['llm_provider'] = provider
        with open(_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save provider preference: {e}")


class LLMService:
    """Unified LLM service that can switch between providers."""

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._current_provider: Optional[BaseLLMProvider] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers."""
        # Initialize OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            openai_provider = OpenAIProvider(
                api_key=openai_key,
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            )
            if openai_provider.initialize():
                self._providers[LLMProviderType.OPENAI] = openai_provider
                logger.info("✅ OpenAI provider registered")
        
        # Initialize Gemini (only if available)
        try:
            from .gemini_provider import GEMINI_AVAILABLE
            if GEMINI_AVAILABLE:
                gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if gemini_key:
                    try:
                        gemini_provider = GeminiProvider(
                            api_key=gemini_key,
                            model=os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
                        )
                        if gemini_provider.initialize():
                            self._providers[LLMProviderType.GEMINI] = gemini_provider
                            logger.info("✅ Gemini provider registered")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to initialize Gemini provider: {e}")
            else:
                logger.debug("Gemini provider not available (google-generativeai package not installed)")
        except ImportError:
            logger.debug("Gemini provider not available (package not installed)")
        
        # Priority: user's saved choice > .env > first available
        valid = [p.value for p in LLMProviderType]
        saved = _load_saved_provider()
        default_provider_str = (saved or os.getenv("LLM_PROVIDER", "")).lower().strip()

        if default_provider_str in valid and default_provider_str in self._providers:
            self._current_provider = self._providers[LLMProviderType(default_provider_str)]
            logger.info(f"✅ Using provider: {default_provider_str} ({'user saved' if saved else '.env'})")
        elif self._providers:
            first_provider = list(self._providers.values())[0]
            self._current_provider = first_provider
            logger.info(f"✅ Using default provider: {first_provider.provider_name}")
        else:
            logger.warning("⚠️  No LLM providers available. Please configure OPENAI_API_KEY or GEMINI_API_KEY")
    
    def set_provider(self, provider_type: LLMProviderType) -> bool:
        """
        Switch to a different LLM provider.
        
        Args:
            provider_type: The provider type to switch to
            
        Returns:
            True if switch successful, False otherwise
        """
        if provider_type not in self._providers:
            logger.error(f"❌ Provider {provider_type.value} not available")
            return False
        
        self._current_provider = self._providers[provider_type]
        _save_provider(provider_type.value)
        logger.info(f"✅ Switched to provider: {provider_type.value}")
        return True
    
    def get_current_provider(self) -> Optional[BaseLLMProvider]:
        """Get the currently active provider."""
        return self._current_provider
    
    def get_current_provider_name(self) -> Optional[str]:
        """Get the name of the currently active provider."""
        return self._current_provider.provider_name if self._current_provider else None
    
    def is_available(self) -> bool:
        """Check if any provider is available."""
        return self._current_provider is not None and self._current_provider.is_available()
    
    def get_available_providers(self) -> list:
        """Get list of available provider names."""
        return [provider.provider_name for provider in self._providers.values()]
    
    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a chat completion using the current provider.
        
        Args:
            messages: List of chat messages (can be dict or ChatMessage objects)
            model: Model name (uses provider default if not provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        if not self.is_available():
            raise RuntimeError("No LLM provider available. Please configure OPENAI_API_KEY or GEMINI_API_KEY")
        
        # Convert messages to ChatMessage objects if needed
        chat_messages = [
            msg if isinstance(msg, ChatMessage) else ChatMessage(**msg)
            for msg in messages
        ]
        
        return await self._current_provider.chat_completion(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    async def chat_completion_json(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a JSON completion using the current provider.
        
        Args:
            messages: List of chat messages (can be dict or ChatMessage objects)
            model: Model name (uses provider default if not provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Parsed JSON dictionary
        """
        if not self.is_available():
            raise RuntimeError("No LLM provider available. Please configure OPENAI_API_KEY or GEMINI_API_KEY")
        
        # Convert messages to ChatMessage objects if needed
        chat_messages = [
            msg if isinstance(msg, ChatMessage) else ChatMessage(**msg)
            for msg in messages
        ]
        
        return await self._current_provider.chat_completion_json(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

