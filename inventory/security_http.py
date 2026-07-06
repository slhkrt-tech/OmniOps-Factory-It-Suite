"""HTTP helpers with SSRF and unsafe-scheme protections."""
from __future__ import annotations

import ipaddress
import socket
from urllib import parse, request
from urllib.error import URLError


_BLOCKED_SCHEMES = {'file', 'ftp', 'gopher', 'data', 'javascript'}


def _hostname_resolves_to_private(hostname: str) -> bool:
    if not hostname:
        return True
    if hostname.lower() in {'localhost'}:
        return True
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except socket.gaierror:
        return True
    return False


def validate_http_url(url: str, *, allowed_hosts: list[str] | None = None, allow_private_hosts: bool = False) -> str:
    """Validate URL scheme/host before server-side fetch."""
    parsed = parse.urlparse((url or '').strip())
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('Unsupported URL scheme.')
    if not parsed.netloc:
        raise ValueError('URL host is required.')

    host = parsed.hostname or ''
    host_lower = host.lower()
    if allowed_hosts:
        allowed = {item.lower() for item in allowed_hosts if item}
        if host_lower not in allowed and parsed.netloc.lower() not in allowed:
            raise ValueError('URL host is not allowed.')
    elif not allow_private_hosts and _hostname_resolves_to_private(host):
        raise ValueError('Private or local URLs are not allowed.')

    return parse.urlunparse(parsed)


def safe_urlopen(url: str, *, timeout: int = 30, allowed_hosts: list[str] | None = None, allow_private_hosts: bool = False):
    """Open HTTP(S) URL after SSRF validation."""
    validated = validate_http_url(url, allowed_hosts=allowed_hosts, allow_private_hosts=allow_private_hosts)
    return request.urlopen(validated, timeout=timeout)  # nosec B310 — validated by validate_http_url()
