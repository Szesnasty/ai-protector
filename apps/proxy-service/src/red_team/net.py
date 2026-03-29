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
        replaced = parsed._replace(netloc=parsed.netloc.replace(parsed.hostname, "host.docker.internal", 1))
        return urlunparse(replaced)
    return url


def validate_url(url: str) -> str | None:
    """Validate *url* against SSRF rules and return a reconstructed URL.

    Returns a **new** URL string built from parsed components if the URL is
    safe, or ``None`` if validation fails.  Reconstructing the URL from
    ``urlunparse`` ensures the returned value is not a direct pass-through
    of untrusted input.

    Rules applied:
    * Scheme must be http or https.
    * Hostname must be present.
    * In Docker: resolved IPs must not be private / loopback / link-local.
    * In local dev: all addresses are allowed (no SSRF risk).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return None

    hostname = parsed.hostname
    if not hostname:
        return None

    if _running_in_docker():
        # Docker DNS name is always allowed (it's the host machine)
        if hostname != "host.docker.internal":
            try:
                infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            except socket.gaierror:
                return None

            if not infos:
                return None

            for info in infos:
                addr = ipaddress.ip_address(info[4][0])
                if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                    return None

    # Reconstruct URL from validated, parsed components.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
