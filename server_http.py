import contextlib
import os
from collections.abc import AsyncIterator

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from src.instagram_mcp_server import InstagramMCPServer

# Build the Instagram MCP server (low-level Server instance lives at .server)
ig_server = InstagramMCPServer()
mcp_server = ig_server.server

# Disable DNS-rebinding host checks (we run behind Railway's proxy)
security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Streamable HTTP session manager (stateless = simplest for hosted, no-auth use)
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


# Mount the MCP handler at ROOT. The StreamableHTTP session manager ignores the
# request path and serves whatever reaches it, so mounting at "/" means BOTH
# /mcp and /mcp/ are handled identically with NO 307 redirect (the redirect was
# dropping the POST body and breaking Claude's handshake).
app = Starlette(
    routes=[
        Mount("/", app=handle_mcp),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
