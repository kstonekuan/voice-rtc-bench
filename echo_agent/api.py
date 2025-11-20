"""
FastAPI server for on-demand room creation.

Provides endpoints for benchmark runners to request temporary rooms
for both Daily and LiveKit platforms.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import aiohttp
from fastapi import FastAPI, HTTPException
from livekit import api
from loguru import logger
from pipecat.transports.daily.utils import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)
from shared.settings import EchoAgentSettings
from shared.types import DailyRoomInfo, LiveKitRoomInfo, RoomCredentials

# Load settings from environment
settings = EchoAgentSettings()

# Room creation helpers
daily_rest_helper: DailyRESTHelper | None = None
aiohttp_session: aiohttp.ClientSession | None = None

# Store active room information for agent to join
active_rooms: dict[str, Any] = {}

# Callback for joining Daily rooms
join_daily_room_callback: Any = None


def set_daily_room_callback(callback):
    """Set the callback function for joining Daily rooms."""
    global join_daily_room_callback
    join_daily_room_callback = callback


async def initialize_daily_helper() -> None:
    """Initialize Daily REST helper with aiohttp session."""
    global daily_rest_helper, aiohttp_session

    if aiohttp_session is None:
        aiohttp_session = aiohttp.ClientSession()

    daily_rest_helper = DailyRESTHelper(
        daily_api_key=settings.daily.daily_api_key,
        aiohttp_session=aiohttp_session,
    )

    logger.info("✅ Daily REST helper initialized")


async def create_daily_room(expiry_seconds: int = 600) -> DailyRoomInfo:
    """
    Create a temporary Daily room.

    Args:
        expiry_seconds: Room expiration time in seconds (default: 10 minutes)

    Returns:
        DailyRoomInfo with room URL and expiration time
    """
    if daily_rest_helper is None:
        raise RuntimeError("Daily REST helper not initialized")

    expiry_time = time.time() + expiry_seconds

    params = DailyRoomParams(
        properties=DailyRoomProperties(
            exp=int(expiry_time),
            eject_at_room_exp=True,
        )
    )

    room = await daily_rest_helper.create_room(params)
    logger.info(f"✅ Created Daily room: {room.url}")

    return DailyRoomInfo(
        room_url=room.url,
        expires_at=expiry_time,
    )


def create_livekit_token(room_name: str, expiry_seconds: int = 600) -> LiveKitRoomInfo:
    """
    Generate LiveKit access token for a room.

    Args:
        room_name: Name of the LiveKit room
        expiry_seconds: Token expiration time in seconds (default: 10 minutes)

    Returns:
        LiveKitRoomInfo with server URL, room name, token, and expiration
    """
    expiry_time = time.time() + expiry_seconds

    token_obj = api.AccessToken(
        settings.livekit.livekit_api_key, settings.livekit.livekit_api_secret
    )
    token_obj.with_identity("benchmark-runner")
    token_obj.with_name("benchmark-runner")
    token_obj.with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
        )
    )
    token_obj.with_ttl(timedelta(seconds=expiry_seconds))

    token = token_obj.to_jwt()
    logger.info(f"✅ Generated LiveKit token for room: {room_name}")

    return LiveKitRoomInfo(
        server_url=settings.livekit.livekit_url,
        room_name=room_name,
        token=token,
        expires_at=expiry_time,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("🚀 Starting FastAPI server...")
    await initialize_daily_helper()
    yield
    # Shutdown
    logger.info("🛑 Shutting down FastAPI server...")
    if aiohttp_session:
        await aiohttp_session.close()


# FastAPI app with lifespan
app = FastAPI(title="Echo Agent API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "echo-agent-api"}


@app.post("/connect", response_model=RoomCredentials)
async def connect():
    """
    Create temporary rooms for both Daily and LiveKit.

    This endpoint creates on-demand rooms with 10-minute expiration for
    benchmark testing. Returns credentials for both platforms.

    Returns:
        RoomCredentials with Daily room URL and LiveKit token
    """
    try:
        # Generate unique room identifier
        room_id = f"benchmark-{int(time.time())}"

        # Create Daily room
        daily_room = await create_daily_room(expiry_seconds=600)

        # Generate LiveKit token
        livekit_room = create_livekit_token(room_name=room_id, expiry_seconds=600)

        # Store room info for agent to join
        active_rooms[room_id] = {
            "daily_url": daily_room.room_url,
            "livekit_room": livekit_room.room_name,
            "created_at": time.time(),
        }

        logger.info(f"🎯 Created rooms for session: {room_id}")
        logger.info(f"   Daily: {daily_room.room_url}")
        logger.info(f"   LiveKit: {livekit_room.room_name}")

        # Trigger Daily room joining if callback is set
        if join_daily_room_callback:
            logger.info(f"🔗 Triggering Daily room join for: {room_id}")
            task = asyncio.create_task(join_daily_room_callback(daily_room.room_url, room_id))
            # Store task reference to prevent it from being garbage collected
            active_rooms[room_id]["daily_join_task"] = task
        else:
            logger.warning("⚠️  No Daily room join callback set - agent will not join room")

        return RoomCredentials(
            daily=daily_room,
            livekit=livekit_room,
        )

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create rooms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Room creation failed: {e!s}")


@app.get("/rooms")
async def list_active_rooms():
    """List currently active rooms."""
    return {"active_rooms": active_rooms}
