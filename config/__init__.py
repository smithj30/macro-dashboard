"""
Centralized application configuration.

Loads settings from config/app_config.yaml with sensible defaults.
API keys remain in .env — this module handles app-level settings only.
"""

import os
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).parent / "app_config.yaml"

_DEFAULTS = {
    "refresh": {
        "default_schedule": "daily",
        "ttl_seconds": {
            "fred": 1800,
            "bea": 3600,
            "zillow": 86400,
            "news": 900,
            "file": 0,
        },
    },
    "charts": {
        "default_height": 500,
        "template": "plotly_white",
        "show_legend": True,
        "show_rangeslider": True,
        "recession_shading": False,
        "color_palette": "Plotly",
    },
    "dashboards": {
        "default_layout": "half",
    },
    "cache": {
        "directory": "data/cache",
        "format": "parquet",
        "max_age_days": 30,
    },
    "logging": {
        "level": "INFO",
        "refresh_log": "data/refresh_log.json",
    },
}

_config: Dict[str, Any] = {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> Dict[str, Any]:
    """Load config from YAML, falling back to defaults."""
    global _config
    if _config:
        return _config

    cfg = _DEFAULTS.copy()

    if _CONFIG_PATH.exists():
        try:
            import yaml
            with open(_CONFIG_PATH, "r") as f:
                file_cfg = yaml.safe_load(f) or {}
            cfg = _deep_merge(_DEFAULTS, file_cfg)
        except ImportError:
            # yaml not installed — use defaults
            pass
        except Exception:
            pass

    _config = cfg
    return _config


def get(section: str, key: str = None, default: Any = None) -> Any:
    """
    Get a config value.

    Usage:
        get("charts", "default_height")  → 500
        get("charts")                    → full charts dict
    """
    cfg = load_config()
    section_data = cfg.get(section, {})
    if key is None:
        return section_data
    return section_data.get(key, default)


def get_ttl(provider: str) -> int:
    """Get the cache TTL in seconds for a provider."""
    cfg = load_config()
    return cfg.get("refresh", {}).get("ttl_seconds", {}).get(provider, 1800)
