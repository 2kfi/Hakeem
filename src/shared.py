"""Shared utilities for LLMSIMT pipeline"""

try:
    from langdetect import detect as _detect

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    _detect = None

ALLOWED_AUDIO_FORMATS = frozenset(
    {
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/pcm",
        "audio/ogg",
    }
)

AUDIO_EXTENSIONS = frozenset({".wav", ".wave", ".ogg", ".flac", ".mp3"})


def validate_audio_format(filename: str, content_type: str) -> bool:
    """Validate audio file format.

    Args:
        filename: Name of the uploaded file
        content_type: MIME type from upload

    Returns:
        True if format is allowed
    """
    if content_type and content_type.lower() in ALLOWED_AUDIO_FORMATS:
        return True
    if filename and filename.lower().endswith(AUDIO_EXTENSIONS):
        return True
    return False


def detect_language(text: str) -> str:
    """Detect language of text.

    Args:
        text: Text to analyze

    Returns:
        Language code (default: "en")
    """
    if not text or not text.strip():
        return "en"
    if not LANGDETECT_AVAILABLE:
        return "en"
    try:
        detected = _detect(text[:200])
        return detected if detected else "en"
    except Exception:
        return "en"


def find_onnx_files(path: str) -> tuple:
    """Find ONNX and config files in a directory or path.

    Args:
        path: Directory path or file path

    Returns:
        Tuple of (onnx_path, config_path) or (None, None)
    """
    import os

    onnx_file = None
    config_file = None

    if not os.path.exists(path):
        return None, None

    if os.path.isfile(path):
        if path.endswith(".onnx"):
            onnx_file = path
            config_file = path + ".json"
            if not os.path.exists(config_file):
                base = path[:-5]
                if os.path.exists(base + ".json"):
                    config_file = base + ".json"
        return onnx_file, config_file

    for f in os.listdir(path):
        if f.endswith(".onnx"):
            onnx_file = os.path.join(path, f)
        elif f.endswith(".json"):
            config_file = os.path.join(path, f)

    if onnx_file and not config_file:
        base = onnx_file[:-5]
        if os.path.exists(base + ".json"):
            config_file = base + ".json"

    return onnx_file, config_file


def is_local_path(path: str) -> bool:
    """Check if path is a local path (not a HuggingFace repo).

    Args:
        path: Path to check

    Returns:
        True if local path
    """
    if not path:
        return False
    return path.startswith("/") or path.startswith("./") or path.startswith("\\")


def is_hf_repo(path: str) -> bool:
    """Check if path is a HuggingFace repository.

    Args:
        path: Path to check

    Returns:
        True if HF repo
    """
    if not path:
        return False
    return "/" in path and not is_local_path(path)
