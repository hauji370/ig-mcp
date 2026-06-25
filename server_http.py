import asyncio
import os
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import uvicorn
from src.instagram_mcp_server import InstagramMCPServer

server = InstagramMCPServer()
sse = SseServerTransport("/messages")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.server.run(streams[0], streams[1], server.server.create_initialization_options())
    return Response()

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return Response()

app = Starlette(routes=[
    Route("/sse", handle_sse),
    Route("/messages", handle_messages, methods=["POST"]),
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
