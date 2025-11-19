"""
FastAPI server for on-demand room creation.

Provides endpoints for benchmark runners to request temporary rooms
for both Daily and LiveKit platforms.
"""

import asyncio
import logging
import os
import time
from typing import Any

import aiohttp
from fastapi import FastAPI, HTTPException
from livekit import api
from pipecat.transports.daily.utils import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Echo Agent API", version="1.0.0")

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


class DailyRoomInfo(BaseModel):
    """Daily room information."""

    room_url: str
    expires_at: float


class LiveKitRoomInfo(BaseModel):
    """LiveKit room information."""

    server_url: str
    room_name: str
    token: str
    expires_at: float


class ConnectResponse(BaseModel):
    """Response from /connect endpoint."""

    daily: DailyRoomInfo
    livekit: LiveKitRoomInfo


async def initialize_daily_helper() -> None:
    """Initialize Daily REST helper with aiohttp session."""
    global daily_rest_helper, aiohttp_session

    if aiohttp_session is None:
        aiohttp_session = aiohttp.ClientSession()

    daily_api_key = os.getenv("DAILY_API_KEY")
    if not daily_api_key:
        raise ValueError("DAILY_API_KEY environment variable is required")

    daily_rest_helper = DailyRESTHelper(
        daily_api_key=daily_api_key,
        daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
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
    livekit_url = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_url, livekit_api_key, livekit_api_secret]):
        raise ValueError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required")

    expiry_time = time.time() + expiry_seconds

    token_obj = api.AccessToken(livekit_api_key, livekit_api_secret)
    token_obj.with_identity("benchmark-runner")
    token_obj.with_name("benchmark-runner")
    token_obj.with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
        )
    )
    token_obj.with_ttl(expiry_seconds)

    token = token_obj.to_jwt()
    logger.info(f"✅ Generated LiveKit token for room: {room_name}")

    return LiveKitRoomInfo(
        server_url=livekit_url,
        room_name=room_name,
        token=token,
        expires_at=expiry_time,
    )


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("🚀 Starting FastAPI server...")
    await initialize_daily_helper()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("🛑 Shutting down FastAPI server...")
    if aiohttp_session:
        await aiohttp_session.close()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "echo-agent-api"}


@app.post("/connect", response_model=ConnectResponse)
async def connect():
    """
    Create temporary rooms for both Daily and LiveKit.

    This endpoint creates on-demand rooms with 10-minute expiration for
    benchmark testing. Returns credentials for both platforms.

    Returns:
        ConnectResponse with Daily room URL and LiveKit token
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

        return ConnectResponse(
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
