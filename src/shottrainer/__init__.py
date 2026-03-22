"""Optical shooting trainer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("shottrainer")
except PackageNotFoundError:
    # Running from source without an install. Fall back to a clear marker.
    __version__ = "0+unknown"

__all__ = ["__version__"]
