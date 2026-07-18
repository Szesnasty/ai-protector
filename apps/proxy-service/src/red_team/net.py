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


def _allow_private_targets() -> bool:
    """Whether reaching private / loopback / link-local targets is explicitly allowed.

    Defaults to **False** (secure): the scanner refuses to connect to internal
    addresses, which closes SSRF to cloud-metadata (169.254.169.254), loopback
    and RFC1918 hosts. Local demo / dev stacks that legitimately scan a target
    on a private network (e.g. the bundled agent on the compose network) opt in
    explicitly via ``RED_TEAM_ALLOW_PRIVATE_TARGETS=true``.
    """
    return os.environ.get("RED_TEAM_ALLOW_PRIVATE_TARGETS", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolves_to_internal(hostname: str) -> bool:
    """Resolve *hostname* and return True if any resolved IP is internal.

    Blocks loopback, private (RFC1918), link-local (incl. cloud metadata),
    reserved, unspecified and multicast ranges. Resolution failure is treated
    as blocked (fail closed).
    """
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return True
    if not infos:
        return True
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            return True
    return False


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
    * Unless private targets are explicitly allowed
      (``RED_TEAM_ALLOW_PRIVATE_TARGETS``), the resolved address must not be
      loopback / private / link-local / reserved / multicast — this is what
      stops SSRF to cloud metadata and internal services.

    This check is applied on **every** outbound scan request (see
    ``RealHttpClient.send_prompt``), not only the connectivity test.
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

    if not _allow_private_targets() and _resolves_to_internal(hostname):
        return None

    # Reconstruct URL from validated, parsed components.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
