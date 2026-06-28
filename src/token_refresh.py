"""Background auto-refresh for the long-lived Instagram access token.

Instagram (Instagram Login) long-lived tokens are valid for 60 days and can be
refreshed any time after they are 24 hours old, which resets the clock to a
fresh 60 days. This module refreshes the in-memory token on a schedule so the
server never serves an expired token.

Note: this refreshes the token the running process uses. To persist across
redeploys, copy the refreshed value the server logs into your Railway
INSTAGRAM_ACCESS_TOKEN variable occasionally (the server keeps working in the
meantime because it refreshes itself on every restart too).
"""

import asyncio
import structlog
import httpx

logger = structlog.get_logger()

# Refresh every 50 days (well inside the 60-day window).
REFRESH_INTERVAL_SECONDS = 50 * 24 * 60 * 60
# On startup, wait a short time before the first refresh attempt.
STARTUP_DELAY_SECONDS = 60


async def _refresh_once(settings) -> bool:
    """Perform a single ig_refresh_token call. Returns True on success."""
    base = settings.instagram_api_base_url  # https://graph.instagram.com
    url = f"{base}/refresh_access_token"
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": settings.instagram_access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            logger.warning("Token refresh non-200", status=resp.status_code, body=resp.text[:300])
            return False
        data = resp.json()
        new_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not new_token:
            logger.warning("Token refresh returned no access_token", body=str(data)[:300])
            return False
        # Update the in-memory token so all subsequent API calls use the fresh one.
        settings.instagram_access_token = new_token
        logger.info(
            "Instagram token refreshed",
            expires_in_days=round((expires_in or 0) / 86400, 1),
            new_token_prefix=new_token[:8],
        )
        # Log the full new token once so it can be copied into Railway if desired.
        logger.info("NEW_LONG_LIVED_TOKEN", token=new_token)
        return True
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        return False


async def token_refresh_loop(settings):
    """Background loop: refresh on startup (once warm) then every 50 days."""
    # Only run if we're on the Instagram endpoint (graph.instagram.com).
    if "graph.instagram.com" not in settings.instagram_api_base_url:
        logger.info("Auto-refresh disabled (not using graph.instagram.com)")
        return

    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    # Attempt an initial refresh so a long-idle deploy gets a fresh 60 days.
    await _refresh_once(settings)

    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        await _refresh_once(settings)
