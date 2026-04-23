"""Configuration - imports from src for backwards compatibility"""

from src.config import (
    Config,
    TTSLanguageConfig,
    get_config,
    setup_logging,
)

__all__ = ["Config", "TTSLanguageConfig", "get_config", "setup_logging"]
