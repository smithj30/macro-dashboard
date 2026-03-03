"""
Data providers — unified interface for all data sources.

Each provider implements BaseProvider and is registered in PROVIDERS.
"""

from providers.base_provider import BaseProvider
from providers.fred_provider import FredProvider
from providers.bea_provider import BEAProvider
from providers.zillow_provider import ZillowProvider
from providers.file_provider import FileProvider
from providers.news_provider import NewsProvider

# Provider registry — keyed by provider name used in feed configs
PROVIDERS = {
    "fred": FredProvider,
    "bea": BEAProvider,
    "zillow": ZillowProvider,
    "file": FileProvider,
    "news": NewsProvider,
}


def get_provider(name: str) -> BaseProvider:
    """Return a provider instance by name."""
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name!r}. Available: {list(PROVIDERS)}")
    return cls()
