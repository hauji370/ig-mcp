import contextlib
import os
from collections.abc import AsyncIterator

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from src.instagram_mcp_server import InstagramMCPServer

# Build the Instagram MCP server
ig_server = InstagramMCPServer()
mcp_server = ig_server.server

# Disable DNS-rebinding host checks (we run behind Railway's proxy)
security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Streamable HTTP session manager
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    event_store=None,
    json_response=False,
    stateless=True,
    security_settings=security,
)


async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with session_manager.run():
        yield


# Mount handles /mcp/ — also add explicit /mcp route to avoid 307 redirect
app = Starlette(
    routes=[
        Mount("/mcp", app=handle_mcp),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, root_path="")
