import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

"""AquaVibe package exports.

Runtime objects live in ``AquaVibe.core.runtime`` so importing the package
never depends on ``__main__`` or a partially initialized package namespace.
"""
from AquaVibe.core.runtime import (
    LOGGER,
    Apple,
    Carbon,
    Spotify,
    Telegram,
    app,
    userbot,
)

__all__ = [
    "LOGGER", "app", "userbot", "Apple", "Carbon", "Spotify",
    "Telegram",
]
