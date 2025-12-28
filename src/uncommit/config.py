"""Configuration management for uncommit."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

# Try to import tomllib (Python 3.11+) or fall back to tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


class Config(BaseModel):
    """Application configuration."""

    model: str = Field(default="gemini-2.0-flash", description="Default model to use")
    api_key: str | None = Field(default=None, description="Google API key")

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file."""
        # Check for XDG config directory first (Linux/macOS)
        if xdg_config := os.getenv("XDG_CONFIG_HOME"):
            return Path(xdg_config) / "uncommit" / "config.toml"
        # Fall back to ~/.config on Unix or APPDATA on Windows
        if os.name == "nt":
            base = Path(os.getenv("APPDATA", Path.home()))
        else:
            base = Path.home() / ".config"
        return base / "uncommit" / "config.toml"


def load_config() -> Config:
    """Load configuration from environment variables and config file.
    
    Priority: Environment variables > .env.local > Config file > Defaults
    """
    # Load .env.local if it exists (for local development)
    from pathlib import Path
    env_local = Path.cwd() / ".env.local"
    if env_local.exists():
        try:
            with open(env_local) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass  # Ignore errors reading .env.local
    
    config_data: dict[str, str] = {}

    # 1. Load from config file if it exists
    config_path = Config.get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
                # Get settings from [default] section
                config_data.update(file_config.get("default", {}))
        except Exception:
            # Silently ignore config file errors, fall back to defaults
            pass

    # 2. Environment variables override config file
    if api_key := os.getenv("GOOGLE_API_KEY"):
        config_data["api_key"] = api_key
    if model := os.getenv("UNCOMMIT_MODEL"):
        config_data["model"] = model

    return Config(**config_data)
