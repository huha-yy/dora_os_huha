"""Utility functions for the chatbot package"""

import os
from pathlib import Path

# Root directory of the chatbot package
ROOT_DIR = Path(__file__).parent


def resolve_model_path(path: str) -> str:
    """
    Resolve a model path relative to ROOT_DIR if it's a relative path.
    
    Args:
        path: Model path (can be absolute or relative)
    
    Returns:
        Resolved absolute path if input was relative, otherwise returns as-is
    """
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return str(ROOT_DIR / path)
