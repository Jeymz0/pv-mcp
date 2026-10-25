"""Streamable HTTP host allowlist. Binding every interface does not open the Host check."""

from urllib.parse import urlsplit

from mcp.server.transport_security import TransportSecuritySettings

from pv_mcp.settings import Settings

_LOCAL_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*")
_LOCAL_ORIGINS = ("http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*")
_WILDCARD_BINDINGS = frozenset({"0.0.0.0", "::", "::0"})


def resource_server_url(settings: Settings) -> str:
    """URL stamped on dev tokens. Clients should call this exact path."""

    if settings.pv_mcp_resource_url:
        return settings.pv_mcp_resource_url
    host = settings.pv_mcp_http_host
    if host in _WILDCARD_BINDINGS:
        host = "127.0.0.1"
    return f"http://{host}:{settings.pv_mcp_http_port}/mcp"


def transport_security(settings: Settings) -> TransportSecuritySettings:
    """Allow localhost plus the configured resource host. Reject any other Host."""

    parts = urlsplit(resource_server_url(settings))
    hostname = parts.hostname or "127.0.0.1"
    hosts = list(_LOCAL_HOSTS)
    origins = list(_LOCAL_ORIGINS)
    hosts.extend(_host_patterns(hostname))
    if parts.scheme and parts.netloc:
        origins.append(f"{parts.scheme}://{parts.netloc}")
        origins.append(f"{parts.scheme}://{hostname}:*")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_unique(hosts),
        allowed_origins=_unique(origins),
    )


def _host_patterns(hostname: str) -> list[str]:
    if ":" in hostname:
        bracketed = f"[{hostname}]"
        return [f"{bracketed}:*", bracketed]
    return [f"{hostname}:*", hostname]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
