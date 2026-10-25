"""Entry point: ``uv run pv-mcp`` for stdio, ``uv run pv-mcp http`` for Streamable HTTP."""

import sys

from pv_mcp.http_transport import transport_security
from pv_mcp.server import build_http_server, build_server
from pv_mcp.settings import Settings


def main() -> None:
    try:
        command = _command(sys.argv[1:])
        settings = Settings()
        if command == "http" or (command is None and settings.pv_mcp_transport == "http"):
            run_http(settings)
            return
        build_server(settings=settings).run(transport="stdio")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def run_http(settings: Settings) -> None:
    server = build_http_server(settings=settings)
    server.run(
        transport="streamable-http",
        host=settings.pv_mcp_http_host,
        port=settings.pv_mcp_http_port,
        transport_security=transport_security(settings),
    )


def _command(args: list[str]) -> str | None:
    if not args:
        return None
    if args == ["stdio"] or args == ["http"]:
        return args[0]
    raise SystemExit("usage: pv-mcp [stdio|http]")


if __name__ == "__main__":
    main()
