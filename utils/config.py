"""
utils/config.py — Load and access config.toml settings
"""
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


_config: dict = {}


def load_config(path: str = "config.toml") -> dict:
    """Load TOML config and cache it. Returns the config dict."""
    global _config
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path.resolve()}")
    with open(cfg_path, "rb") as f:
        _config = tomllib.load(f)
    return _config


def get(section: str, key: str, default=None):
    """Get a config value by section + key."""
    return _config.get(section, {}).get(key, default)


def get_section(section: str) -> dict:
    """Get an entire config section."""
    return _config.get(section, {})
