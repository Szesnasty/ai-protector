"""Network helpers for the red-team subsystem."""

from __future__ import annotations

import ipaddress
import os
import socket
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

_LOCALHOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
_ALLOWED_SCHEMES = frozenset({"http", "https"})


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


def is_safe_url(url: str) -> bool:
    """Return True if *url* targets an allowed scheme and non-internal host.

    Prevents SSRF by rejecting private, loopback, and link-local IPs when
    running inside Docker (deployed mode).  In local dev (no Docker) private
    addresses are allowed because the user is testing against their own machine.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Local dev: no SSRF risk, everything on localhost is fine
    if not _running_in_docker():
        return True

    # Docker DNS name is always allowed (it's the host machine)
    if hostname == "host.docker.internal":
        return True

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    if not infos:
        return False

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return False

    return True
