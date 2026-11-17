"""stdio entry point launched by the agent's MCP client.

The client starts this file as a script. The server process stays a separate
program: the agent does not embed an ``MCPServer``.
"""

from pv_mcp.__main__ import main

if __name__ == "__main__":
    main()
