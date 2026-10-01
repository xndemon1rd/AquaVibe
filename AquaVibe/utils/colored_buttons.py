"""Compatibility shim: implementation lives in AquaVibe.core.colored_buttons
so that core.bot can import it without loading the whole utils package
(which would create a circular import with AquaVibe.core.runtime)."""
import sys as _sys
from AquaVibe.core import colored_buttons as _impl

_sys.modules[__name__] = _impl
