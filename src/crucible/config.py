"""
Configuration management for the AI Crucible.

Loads configuration from YAML files, environment variables, and CLI flags,
following the schema defined in config-schema.md.
"""

import os
from pathlib import Path
from typing import Any, Optional, Literal

import yaml
from pydantic import BaseModel, Field


class SimilarityConfig(BaseModel):
    """Configuration for semantic similarity detection."""
    
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    model: str = "all-MiniLM-L6-v2"
    fallback_to_exact: bool = True


class ConfidenceConfig(BaseModel):
    """Configuration for confidence thresholds."""
    
    blocking_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    degradation_rate: float = Field(default=0.8, ge=0.0, le=1.0)


class TimeoutConfig(BaseModel):
    """Configuration for timeout policies."""
    
    architect_seconds: int = 60
    red_team_seconds: int = 45
    defender_seconds: int = 45
    global_seconds: int = 300


class VerificationConfig(BaseModel):
    """Configuration for verification thresholds."""
    
    min_diff_chars: int = 10
    min_diff_lines: int = 1


class DefenderConfig(BaseModel):
    """Configuration for the Defender agent."""
    
    max_patches_per_iteration: int = 3


class RedTeamConfig(BaseModel):
    """Configuration for Red Team agents."""
    
    retry_on_schema_failure: int = 1


class AgentsConfig(BaseModel):
    """Configuration for all agents."""
    
    defender: DefenderConfig = Field(default_factory=DefenderConfig)
    red_team: RedTeamConfig = Field(default_factory=RedTeamConfig)


class ScenariosConfig(BaseModel):
    """Configuration for scenario packs and benchmark mode."""
    
    enabled: bool = False


class AttackChainsConfig(BaseModel):
    """Configuration for attack chain reasoning."""
    
    enabled: bool = False


class DefenderStrategySemConfig(BaseModel):
    """Configuration for defender strategy simulation."""
    
    enabled: bool = False
    default_strategy: Literal[
        "tactical-first",
        "balanced",
        "architecture-first",
    ] = "tactical-first"


class BenchmarksConfig(BaseModel):
    """Configuration for benchmark execution and gating."""
    
    enabled: bool = False
    fail_on_regression: bool = False

class JudgeConfig(BaseModel):
    """Configuration for the Judge's chain-aware decision logic."""
    
    chain_risk_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    chain_effectiveness_strategy: str = "min"  # mean, min, max
    enable_chain_awareness: bool = True


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    
    provider: str = "google"
    model: str = "gemini-2.5-flash"  # Latest model
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    api_key_env: str = "GOOGLE_API_KEY"


class OutputConfig(BaseModel):
    """Configuration for output modes."""
    
    mode: str = "war_room"  # war_room, debug, json
    state_dump_on_failure: bool = True
    state_dump_path: str = "/tmp/crucible_states"


class CrucibleConfig(BaseModel):
    """Main configuration for the AI Crucible."""
    
    max_iterations: int = Field(default=3, ge=1, le=10)
    sequential_mode: bool = True  # Run agents one-by-one to avoid rate limits
    similarity: SimilarityConfig = Field(default_factory=SimilarityConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    scenarios: ScenariosConfig = Field(default_factory=ScenariosConfig)
    attack_chains: AttackChainsConfig = Field(default_factory=AttackChainsConfig)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    defender_strategy_sim: DefenderStrategySemConfig = Field(default_factory=DefenderStrategySemConfig)
    benchmarks: BenchmarksConfig = Field(default_factory=BenchmarksConfig)
    
    @classmethod
    def load(
        cls,
        config_path: Optional[Path] = None,
        overrides: Optional[dict[str, Any]] = None
    ) -> "CrucibleConfig":
        """
        Load configuration from file and environment.
        
        Priority (highest to lowest):
        1. Explicit overrides (from CLI flags)
        2. Config file
        3. Environment variables
        4. Built-in defaults
        """
        config_data: dict[str, Any] = {}
        
        # Try to load from file
        if config_path is None:
            # Check default locations
            default_paths = [
                Path("crucible.yaml"),
                Path("crucible.yml"),
                Path.home() / ".crucible" / "config.yaml",
            ]
            for p in default_paths:
                if p.exists():
                    config_path = p
                    break
        
        if config_path and config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
        
        # Apply environment variable overrides
        env_config = os.environ.get("CRUCIBLE_CONFIG")
        if env_config and Path(env_config).exists():
            with open(env_config) as f:
                env_data = yaml.safe_load(f) or {}
                config_data = _deep_merge(config_data, env_data)
        
        # Apply explicit overrides
        if overrides:
            config_data = _deep_merge(config_data, overrides)
        
        return cls(**config_data)
    
    def get_api_key(self) -> str:
        """Get the API key from environment or .env file."""
        # First try environment
        key = os.environ.get(self.llm.api_key_env)
        
        # If not in env, try loading from .env file
        if not key:
            key = _load_from_dotenv(self.llm.api_key_env)
        
        if not key:
            raise ValueError(
                f"API key not found. Set the {self.llm.api_key_env} environment variable "
                f"or add it to a .env file in the project directory."
            )
        return key

def _load_from_dotenv(key_name: str) -> Optional[str]:
    """Load a key from .env file if it exists."""
    # Check multiple locations for .env
    env_paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",  # Project root
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == key_name:
                                return v.strip()
            except Exception:
                continue
    
    return None


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Global config instance (set during CLI initialization)
_config: Optional[CrucibleConfig] = None


def get_config() -> CrucibleConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = CrucibleConfig.load()
    return _config


def set_config(config: CrucibleConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
