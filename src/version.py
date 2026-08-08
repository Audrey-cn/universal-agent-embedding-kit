"""UAEK release version authority for runtime entrypoints."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

SOURCE_VERSION = "0.3.0.dev1"


def get_version() -> str:
    """Return installed package metadata, or the source-tree fallback."""
    try:
        return version("uaek")
    except PackageNotFoundError:
        return SOURCE_VERSION


__version__ = get_version()
