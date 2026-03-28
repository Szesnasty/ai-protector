"""Network helpers for the red-team subsystem."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

_LOCALHOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})


@lru_cache(maxsize=1)
def _running_in_docker() -> bool:
    """Return True when the process is inside a Docker container."""
    return os.path.isfile("/.dockerenv")


def rewrite_localhost_for_docker(url: str) -> str:
    """Replace localhost with host.docker.internal when running in Docker.

    When the proxy-service runs inside a container, ``localhost`` refers to
    the container itself — not the host machine.  ``host.docker.internal``
    is the Docker-provided DNS name that resolves to the host.

    When running natively (``make dev``), the URL is returned unchanged.
    """
    if not _running_in_docker():
        return url
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    if parsed.hostname in _LOCALHOST_NAMES:
        replaced = parsed._replace(
            netloc=parsed.netloc.replace(parsed.hostname, "host.docker.internal", 1)
        )
        return urlunparse(replaced)
    return url
