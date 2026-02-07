"""
Base agent class for the AI Crucible.

Provides common functionality for all agents including:
- LLM client initialization
- Prompt loading
- Schema-validated output parsing
- Timeout handling
"""

import json
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from crucible.config import get_config, CrucibleConfig

T = TypeVar("T", bound=BaseModel)


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class AgentTimeoutError(AgentError):
    """Raised when an agent times out."""
    pass


class AgentSchemaError(AgentError):
    """Raised when an agent returns invalid schema."""
    pass


class BaseAgent(ABC, Generic[T]):
    """
    Base class for all Crucible agents.
    
    Type parameter T is the Pydantic model for the agent's output.
    """
    
    name: str = "BaseAgent"
    domain: Optional[str] = None
    prompt_file: Optional[str] = None
    
    def __init__(self, config: Optional[CrucibleConfig] = None):
        self.config = config or get_config()
        self._llm = None
        self._system_prompt: Optional[str] = None
    
    @property
    def llm(self):
        """Lazy initialization of the LLM client using providers module."""
        if self._llm is None:
            from crucible.providers import ProviderConfig, create_llm, LLMProvider
            
            provider_name = self.config.llm.provider.lower()
            config_model = self.config.llm.model
            
            # Check if using default Google model - if so, use provider's default
            is_default_model = config_model in ("gemini-2.5-flash", "gemini-2.0-flash-exp")
            
            # Map provider name to config (use provider default if model wasn't explicitly set)
            if provider_name == "google":
                provider_config = ProviderConfig.for_google(config_model)
            elif provider_name == "ollama":
                model = config_model if not is_default_model else None
                provider_config = ProviderConfig.for_ollama(model or "llama3.1:latest")
            elif provider_name == "groq":
                model = config_model if not is_default_model else None
                provider_config = ProviderConfig.for_groq(model or "llama-3.3-70b-versatile")
            elif provider_name == "perplexity":
                model = config_model if not is_default_model else None
                provider_config = ProviderConfig.for_perplexity(model or "llama-3.1-sonar-small-128k-online")
            elif provider_name == "openai":
                model = config_model if not is_default_model else None
                provider_config = ProviderConfig.for_openai(model or "gpt-4o-mini")
            elif provider_name == "anthropic":
                model = config_model if not is_default_model else None
                provider_config = ProviderConfig.for_anthropic(model or "claude-3-haiku-20240307")
            else:
                # Default to Google
                provider_config = ProviderConfig.for_google(config_model)
            
            provider_config.temperature = self.config.llm.temperature
            self._llm = create_llm(provider_config)
        
        return self._llm
    
    @property
    def system_prompt(self) -> str:
        """Load the system prompt from file or return embedded prompt."""
        if self._system_prompt is None:
            if self.prompt_file:
                prompt_path = Path(__file__).parent / "prompts" / self.prompt_file
                if prompt_path.exists():
                    self._system_prompt = prompt_path.read_text()
                else:
                    self._system_prompt = self.get_default_prompt()
            else:
                self._system_prompt = self.get_default_prompt()
        return self._system_prompt
    
    @abstractmethod
    def get_default_prompt(self) -> str:
        """Return the default system prompt for this agent."""
        pass
    
    @abstractmethod
    def get_output_schema(self) -> type[T]:
        """Return the Pydantic model class for the agent's output."""
        pass
    
    @abstractmethod
    def build_user_message(self, **kwargs: Any) -> str:
        """Build the user message from input parameters."""
        pass
    
    def get_timeout(self) -> int:
        """Get the timeout for this agent in seconds."""
        return self.config.timeouts.architect_seconds
    
    async def invoke_async(self, **kwargs: Any) -> T:
        """
        Invoke the agent asynchronously with timeout.
        
        Returns the parsed output as a Pydantic model.
        Raises AgentTimeoutError if the agent times out.
        Raises AgentSchemaError if the output cannot be parsed.
        """
        timeout = self.get_timeout()
        
        try:
            result = await asyncio.wait_for(
                self._invoke_llm(**kwargs),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            raise AgentTimeoutError(
                f"{self.name} timed out after {timeout} seconds"
            )
    
    def invoke(self, **kwargs: Any) -> T:
        """Synchronous wrapper for invoke_async."""
        return asyncio.run(self.invoke_async(**kwargs))
    
    async def _invoke_llm(self, **kwargs: Any) -> T:
        """Internal method to invoke the LLM and parse output."""
        from crucible.retry import retry_with_backoff, RetryConfig
        
        async def _call_llm():
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=self.build_user_message(**kwargs)),
            ]
            
            # Request JSON output
            response = await self.llm.ainvoke(messages)
            
            # Extract content
            content = response.content
            if isinstance(content, list):
                content = content[0] if content else ""
            
            return str(content)
        
        # Use retry with backoff
        retry_config = RetryConfig(max_retries=3, initial_delay=2.0)
        content = await retry_with_backoff(_call_llm, config=retry_config)
        
        # Parse JSON from response
        return self._parse_response(content)
    
    async def invoke_streaming(self, on_token: Any = None, **kwargs: Any) -> T:
        """
        Invoke the agent with streaming output.
        
        Args:
            on_token: Callback function called for each token (optional)
            **kwargs: Arguments passed to build_user_message
        
        Returns:
            The parsed output as a Pydantic model
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=self.build_user_message(**kwargs)),
        ]
        
        # Collect tokens
        tokens = []
        
        async for chunk in self.llm.astream(messages):
            token = chunk.content
            tokens.append(token)
            
            if on_token and callable(on_token):
                on_token(token)
        
        # Combine and parse
        full_content = "".join(tokens)
        return self._parse_response(full_content)
    
    def _parse_response(self, content: str) -> T:
        """Parse and validate the LLM response."""
        # Try to extract JSON from markdown code blocks
        json_str = self._extract_json(content)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise AgentSchemaError(
                f"{self.name} returned invalid JSON: {e}\nContent: {content[:500]}"
            )
        
        # Validate against schema
        schema_class = self.get_output_schema()
        try:
            return schema_class(**data)
        except ValidationError as e:
            raise AgentSchemaError(
                f"{self.name} returned data that doesn't match schema: {e}"
            )
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from content, handling markdown code blocks."""
        content = content.strip()
        
        # Try to find JSON in markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        
        # Try to find raw JSON object
        if "{" in content:
            start = content.find("{")
            # Find matching closing brace
            depth = 0
            for i, char in enumerate(content[start:], start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return content[start:i+1]
        
        # Return as-is and let JSON parser handle it
        return content

    async def cleanup(self) -> None:
        """Explicitly close the LLM client to prevent async warnings."""
        if self._llm is not None:
            # Close the async HTTP client if it exists
            if hasattr(self._llm, "async_client") and self._llm.async_client:
                try:
                    await self._llm.async_client.aclose()
                except Exception:
                    # Silently ignore cleanup errors
                    pass
            self._llm = None
