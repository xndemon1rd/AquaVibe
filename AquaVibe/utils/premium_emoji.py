"""Compatibility shim: implementation lives in AquaVibe.core.premium_emoji."""
import sys as _sys
from AquaVibe.core import premium_emoji as _impl

_sys.modules[__name__] = _impl
