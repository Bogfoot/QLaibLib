"""Metrics package."""

from .core import REGISTRY
from . import visibility  # noqa: F401 - ensure registration
from . import qber  # noqa: F401 - ensure registration
from . import chsh  # noqa: F401 - ensure registration

__all__ = ["REGISTRY"]
