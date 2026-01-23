"""
Multi-LLM Provider support for the AI Crucible.

Supports: Google Gemini, Ollama (local), Groq, Perplexity, and more.
"""

import os
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, AIMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    
    GOOGLE = "google"       # Gemini (default)
    OLLAMA = "ollama"       # Local, unlimited
    GROQ = "groq"           # Fast, free tier
    PERPLEXITY = "perplexity"  # Research-focused
    OPENAI = "openai"       # GPT-4 (paid)
    ANTHROPIC = "anthropic" # Claude (paid)


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    
    provider: LLMProvider = LLMProvider.GOOGLE
    model: str = "gemini-2.5-flash"
    temperature: float = 0.3
    api_key_env: str = "GOOGLE_API_KEY"
    base_url: Optional[str] = None
    
    # Provider-specific defaults
    @classmethod
    def for_google(cls, model: str = "gemini-2.5-flash") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.GOOGLE,
            model=model,
            api_key_env="GOOGLE_API_KEY",
        )
    
    @classmethod
    def for_ollama(cls, model: str = "llama3.1:8b") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.OLLAMA,
            model=model,
            base_url="http://localhost:11434",
            api_key_env="",  # No API key needed
        )
    
    @classmethod
    def for_groq(cls, model: str = "llama-3.3-70b-versatile") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.GROQ,
            model=model,
            api_key_env="GROQ_API_KEY",
        )
    
    @classmethod
    def for_perplexity(cls, model: str = "llama-3.1-sonar-small-128k-online") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.PERPLEXITY,
            model=model,
            api_key_env="PERPLEXITY_API_KEY",
            base_url="https://api.perplexity.ai",
        )
    
    @classmethod
    def for_openai(cls, model: str = "gpt-4o-mini") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.OPENAI,
            model=model,
            api_key_env="OPENAI_API_KEY",
        )
    
    @classmethod
    def for_anthropic(cls, model: str = "claude-3-haiku-20240307") -> "ProviderConfig":
        return cls(
            provider=LLMProvider.ANTHROPIC,
            model=model,
            api_key_env="ANTHROPIC_API_KEY",
        )


def create_llm(config: ProviderConfig):
    """
    Create an LLM client based on the provider configuration.
    
    Returns a LangChain-compatible chat model.
    """
    api_key = os.environ.get(config.api_key_env) if config.api_key_env else None
    
    if config.provider == LLMProvider.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        return ChatGoogleGenerativeAI(
            model=config.model,
            google_api_key=api_key,
            temperature=config.temperature,
        )
    
    elif config.provider == LLMProvider.OLLAMA:
        from langchain_ollama import ChatOllama
        
        return ChatOllama(
            model=config.model,
            base_url=config.base_url or "http://localhost:11434",
            temperature=config.temperature,
        )
    
    elif config.provider == LLMProvider.GROQ:
        from langchain_groq import ChatGroq
        
        return ChatGroq(
            model=config.model,
            groq_api_key=api_key,
            temperature=config.temperature,
        )
    
    elif config.provider == LLMProvider.PERPLEXITY:
        # Perplexity uses OpenAI-compatible API
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=config.model,
            openai_api_key=api_key,
            openai_api_base=config.base_url,
            temperature=config.temperature,
        )
    
    elif config.provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=config.model,
            openai_api_key=api_key,
            temperature=config.temperature,
        )
    
    elif config.provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic
        
        return ChatAnthropic(
            model=config.model,
            anthropic_api_key=api_key,
            temperature=config.temperature,
        )
    
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")


def get_available_providers() -> List[LLMProvider]:
    """Get list of providers that have API keys configured."""
    available = []
    
    # Check each provider
    provider_env_vars = {
        LLMProvider.GOOGLE: "GOOGLE_API_KEY",
        LLMProvider.GROQ: "GROQ_API_KEY",
        LLMProvider.PERPLEXITY: "PERPLEXITY_API_KEY",
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    }
    
    for provider, env_var in provider_env_vars.items():
        if os.environ.get(env_var):
            available.append(provider)
    
    # Ollama is always available if running
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=1)
        available.append(LLMProvider.OLLAMA)
    except Exception:
        pass  # Ollama not running
    
    return available


def get_default_provider() -> ProviderConfig:
    """Get the default provider based on available API keys."""
    available = get_available_providers()
    
    # Priority order
    priority = [
        LLMProvider.GOOGLE,
        LLMProvider.GROQ,
        LLMProvider.OLLAMA,
        LLMProvider.PERPLEXITY,
        LLMProvider.OPENAI,
        LLMProvider.ANTHROPIC,
    ]
    
    for provider in priority:
        if provider in available:
            if provider == LLMProvider.GOOGLE:
                return ProviderConfig.for_google()
            elif provider == LLMProvider.GROQ:
                return ProviderConfig.for_groq()
            elif provider == LLMProvider.OLLAMA:
                return ProviderConfig.for_ollama()
            elif provider == LLMProvider.PERPLEXITY:
                return ProviderConfig.for_perplexity()
            elif provider == LLMProvider.OPENAI:
                return ProviderConfig.for_openai()
            elif provider == LLMProvider.ANTHROPIC:
                return ProviderConfig.for_anthropic()
    
    # Default to Google
    return ProviderConfig.for_google()


# Model recommendations by task
RECOMMENDED_MODELS = {
    "architect": {
        LLMProvider.GOOGLE: "gemini-2.5-flash",
        LLMProvider.OLLAMA: "llama3.1:8b",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.PERPLEXITY: "llama-3.1-sonar-large-128k-online",
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
    },
    "red_team": {
        LLMProvider.GOOGLE: "gemini-2.5-flash",
        LLMProvider.OLLAMA: "llama3.1:8b",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.PERPLEXITY: "llama-3.1-sonar-small-128k-online",
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
    },
    "defender": {
        LLMProvider.GOOGLE: "gemini-2.5-flash",
        LLMProvider.OLLAMA: "llama3.1:8b",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.PERPLEXITY: "llama-3.1-sonar-small-128k-online",
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
    },
}


def get_model_for_task(task: str, provider: LLMProvider) -> str:
    """Get the recommended model for a specific task and provider."""
    return RECOMMENDED_MODELS.get(task, {}).get(provider, "")
