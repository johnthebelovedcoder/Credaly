"""
Webhook URL Validator — prevents SSRF attacks via malicious webhook endpoints.
Per PRD FR-035: lenders register webhook endpoints; we must ensure they can't
target internal services (169.254.169.254, localhost, internal IPs).
"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / cloud metadata
    ipaddress.ip_network("10.0.0.0/8"),        # Private
    ipaddress.ip_network("172.16.0.0/12"),     # Private
    ipaddress.ip_network("192.168.0.0/16"),    # Private
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
]


class WebhookURLValidationError(ValueError):
    """Raised when a webhook URL fails SSRF validation."""
    pass


def validate_webhook_url(url: str) -> None:
    """
    Validate a webhook URL is safe to call.

    Checks:
    1. Must use HTTPS (no HTTP, ftp, file, etc.)
    2. Must not point to localhost or cloud metadata endpoints
    3. Must not resolve to a private/internal IP address

    Raises WebhookURLValidationError if any check fails.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise WebhookURLValidationError(
            f"Webhook URL must use HTTPS, got: {parsed.scheme}"
        )

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise WebhookURLValidationError("Webhook URL must have a hostname")

    if hostname.lower() in BLOCKED_HOSTS:
        raise WebhookURLValidationError(
            f"Webhook URL hostname is blocked: {hostname}"
        )

    # Resolve DNS and check IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, parsed.port or 443, socket.AF_INET)
        for family, socktype, proto, canonname, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in BLOCKED_NETWORKS:
                if ip in network:
                    raise WebhookURLValidationError(
                        f"Webhook URL resolves to blocked network {network}: {ip}"
                    )
    except socket.gaierror:
        raise WebhookURLValidationError(
            f"Webhook URL hostname could not be resolved: {hostname}"
        )
