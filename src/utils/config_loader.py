"""
Configuration Loader Module

Loads and manages YAML configuration files for the AIOps Multi-Agent System.
Supports environment variable overrides and provides type-safe access to config values.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file automatically
# Looks for .env in current directory and parent directories
load_dotenv()


class AWSConfig(BaseModel):
    """AWS-specific configuration."""
    region: str = "us-east-1"
    bedrock_endpoint: str | None = None


class SessionConfig(BaseModel):
    """Session/memory storage configuration."""
    bucket: str = "aiops-agent-sessions"
    prefix: str = "sessions/"
    ttl: int = 604800  # 7 days


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    json_format: bool = False


class CronConfig(BaseModel):
    """Cron job configuration."""
    default_time_from: str = "now-1d"
    default_time_to: str = "now"
    schedule: str = "cron(0 6 * * ? *)"


class RateLimitsConfig(BaseModel):
    """Rate limiting and safety configuration."""
    max_agent_iterations: int = 20
    max_handoffs: int = 15
    execution_timeout_seconds: int = 900
    node_timeout_seconds: int = 300


class FeaturesConfig(BaseModel):
    """Feature flags."""
    enable_ticket_creation: bool = True
    enable_notifications: bool = False
    dry_run_mode: bool = False


class SettingsConfig(BaseModel):
    """Main settings configuration model."""
    aws: AWSConfig = Field(default_factory=AWSConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)


class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    name: str
    description: str = ""
    model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    max_tokens: int = 4096
    system_prompt: str = ""


class AgentsConfig(BaseModel):
    """All agents configuration."""
    defaults: dict = Field(default_factory=dict)
    orchestrator: AgentConfig
    datadog: AgentConfig
    coding: AgentConfig
    servicenow: AgentConfig


class DataDogToolConfig(BaseModel):
    """DataDog tool configuration."""
    site: str = "us5"
    endpoints: dict = Field(default_factory=dict)
    query: dict = Field(default_factory=dict)
    request: dict = Field(default_factory=dict)
    formatting: dict = Field(default_factory=dict)


class ServiceNowToolConfig(BaseModel):
    """ServiceNow tool configuration."""
    endpoints: dict = Field(default_factory=dict)
    defaults: dict = Field(default_factory=dict)
    priority_mapping: dict = Field(default_factory=dict)
    request: dict = Field(default_factory=dict)


class CodeAnalysisToolConfig(BaseModel):
    """Code analysis tool configuration."""
    analysis: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    """All tools configuration."""
    datadog: DataDogToolConfig = Field(default_factory=DataDogToolConfig)
    servicenow: ServiceNowToolConfig = Field(default_factory=ServiceNowToolConfig)
    code_analysis: CodeAnalysisToolConfig = Field(default_factory=CodeAnalysisToolConfig)


class ConfigLoader:
    """
    Configuration loader that reads YAML files and provides access to config values.
    
    Supports:
    - Loading multiple config files (settings, agents, tools)
    - Environment variable overrides
    - Type-safe access via Pydantic models
    - Singleton pattern for global access
    
    Usage:
        # Initialize with config directory
        config = ConfigLoader(config_dir="config")
        
        # Access configurations
        settings = config.settings
        agents = config.agents
        tools = config.tools
        
        # Get specific agent config
        orchestrator_config = config.get_agent_config("orchestrator")
    """
    
    _instance: "ConfigLoader | None" = None
    
    def __new__(cls, config_dir: str | None = None) -> "ConfigLoader":
        """Singleton pattern - return existing instance if available."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_dir: str | None = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Path to configuration directory. Defaults to 'config' in project root.
        """
        if self._initialized:
            return
            
        self._config_dir = self._resolve_config_dir(config_dir)
        self._raw_configs: dict[str, dict] = {}
        
        # Load all configuration files
        self._load_all_configs()
        
        # Parse into typed models
        self._settings: SettingsConfig | None = None
        self._agents: AgentsConfig | None = None
        self._tools: ToolsConfig | None = None
        
        self._initialized = True
    
    def _resolve_config_dir(self, config_dir: str | None) -> Path:
        """Resolve the configuration directory path."""
        if config_dir:
            return Path(config_dir)
        
        # Try environment variable
        env_config_dir = os.environ.get("AIOPS_CONFIG_DIR")
        if env_config_dir:
            return Path(env_config_dir)
        
        # Default to 'config' in project root
        # Walk up from current file to find project root
        current = Path(__file__).parent
        while current != current.parent:
            config_path = current / "config"
            if config_path.exists():
                return config_path
            current = current.parent
        
        # Fallback to relative path
        return Path("config")
    
    def _load_yaml_file(self, filename: str) -> dict:
        """Load a single YAML configuration file."""
        filepath = self._config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}
    
    def _load_all_configs(self) -> None:
        """Load all configuration files."""
        config_files = ["settings.yaml", "agents.yaml", "tools.yaml"]
        
        for filename in config_files:
            config_name = filename.replace(".yaml", "")
            try:
                self._raw_configs[config_name] = self._load_yaml_file(filename)
            except FileNotFoundError:
                # Use empty dict for missing configs
                self._raw_configs[config_name] = {}
    
    def _apply_env_overrides(self, config: dict, prefix: str = "AIOPS") -> dict:
        """
        Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: {PREFIX}_{SECTION}_{KEY}
        Example: AIOPS_AWS_REGION=us-west-2
        """
        result = config.copy()
        
        for key, value in os.environ.items():
            if not key.startswith(f"{prefix}_"):
                continue
            
            # Parse the environment variable name
            parts = key[len(prefix) + 1:].lower().split("_")
            
            # Navigate to the correct nested dict
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value (try to parse as appropriate type)
            final_key = parts[-1]
            current[final_key] = self._parse_env_value(value)
        
        return result
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        
        # String
        return value
    
    @property
    def settings(self) -> SettingsConfig:
        """Get the settings configuration."""
        if self._settings is None:
            raw = self._apply_env_overrides(self._raw_configs.get("settings", {}))
            self._settings = SettingsConfig(**raw)
        return self._settings
    
    @property
    def agents(self) -> AgentsConfig:
        """Get the agents configuration."""
        if self._agents is None:
            raw = self._raw_configs.get("agents", {})
            self._agents = AgentsConfig(**raw)
        return self._agents
    
    @property
    def tools(self) -> ToolsConfig:
        """Get the tools configuration."""
        if self._tools is None:
            raw = self._raw_configs.get("tools", {})
            self._tools = ToolsConfig(**raw)
        return self._tools
    
    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """
        Get configuration for a specific agent.
        
        Args:
            agent_name: Name of the agent (orchestrator, datadog, coding, servicenow)
            
        Returns:
            AgentConfig for the specified agent
            
        Raises:
            ValueError: If agent_name is not found
        """
        agents = self.agents
        
        if hasattr(agents, agent_name):
            return getattr(agents, agent_name)
        
        raise ValueError(f"Unknown agent: {agent_name}")
    
    def get_raw_config(self, config_name: str) -> dict:
        """Get raw (untyped) configuration dictionary."""
        return self._raw_configs.get(config_name, {})
    
    def reload(self) -> None:
        """Reload all configuration files."""
        self._raw_configs.clear()
        self._settings = None
        self._agents = None
        self._tools = None
        self._load_all_configs()


# Global config instance getter
def get_config(config_dir: str | None = None) -> ConfigLoader:
    """
    Get the global configuration loader instance.
    
    Args:
        config_dir: Optional path to configuration directory.
                   Only used on first call.
    
    Returns:
        ConfigLoader instance
    
    Usage:
        from src.utils import get_config
        
        config = get_config()
        aws_region = config.settings.aws.region
    """
    return ConfigLoader(config_dir)
