"""LLMSIMT-Hakeem - Voice AI Pipeline"""

from .config import Config, get_config, setup_logging
from .mcp import MCPWrapper, MCPSessionManager
from .shared import detect_language, validate_audio

__version__ = "0.1.0"
