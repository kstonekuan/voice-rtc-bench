"""
Daily platform implementation.

Contains all Daily-specific code including agent logic and API endpoints.
"""

import asyncio
import json
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import aiohttp
import uvicorn
from daily import CallClient, Daily, EventHandler
from fastapi import FastAPI, HTTPException
from loguru import logger
from pipecat.transports.daily.utils import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)
from pydantic import BaseModel
from shared.settings import EchoAgentSettings
from shared.types import DailyRoomInfo, PongMessage, RoomCredentials
from shared.utils import setup_logging

from echo_agent.base import PlatformHandler


class DisconnectRequest(BaseModel):
    """Request model for disconnecting from a room."""

    room_id: str


class MessageHandler:
    """Message handling logic for Daily platform."""

    def __init__(self) -> None:
        self.message_count = 0

    def create_pong_message(self, client_timestamp: float) -> dict[str, Any]:
        """Create a pong response message."""
        self.message_count += 1
        # Use perf_counter for consistent timing with client measurements
        server_receive_time = time.perf_counter() * 1000

        pong = PongMessage(
            client_timestamp=client_timestamp,
            server_receive_time=server_receive_time,
            server_send_time=time.perf_counter() * 1000,
            message_count=self.message_count,
        )
        return pong.model_dump()


class DailyEchoHandler(EventHandler):
    """Daily-specific echo handler."""

    def __new__(cls, *args: Any, **kwargs: Any) -> "DailyEchoHandler":  # noqa: ANN401
        """Create a new instance, filtering out kwargs that EventHandler doesn't accept."""
        return super().__new__(cls)

    def __init__(self, room_url: str, agent_name: str = "daily-echo") -> None:
        EventHandler.__init__(self)
        self.room_url = room_url
        self.agent_name = agent_name
        self.client: CallClient | None = None
        self.is_joined = False
        self.should_exit = False
        self.handler = MessageHandler()

    def on_joined(self, data: dict[str, Any] | None, error: str | None) -> None:
        """Called when successfully joined the room."""
        if error:
            logger.error(f"[Daily] Failed to join room: {error}")
            return

        self.is_joined = True
        logger.info(f"✅ [Daily] {self.agent_name} joined room")
        logger.info("👂 [Daily] Listening for ping messages...")

    def on_participant_joined(self, participant: dict[str, Any]) -> None:
        """Called when a participant joins."""
        participant_id = participant.get("id", "unknown")
        logger.info(f"[Daily] Participant joined: {participant_id}")

    def on_participant_left(self, participant: dict[str, Any], reason: str) -> None:
        """Called when a participant leaves."""
        participant_id = participant.get("id", "unknown")
        logger.info(f"[Daily] Participant left: {participant_id}")

    def request_disconnect(self) -> None:
        """Request the agent to disconnect from the room."""
        logger.info(f"[Daily] Disconnect requested for {self.agent_name}")
        self.should_exit = True

    def on_app_message(self, message: object, sender: str) -> None:
        """Handle incoming app-message event."""
        try:
            data = json.loads(message) if isinstance(message, str) else message
            data_dict = cast(dict[str, Any], data)

            message_type = data_dict.get("type")

            if message_type == "ping":
                client_timestamp = data_dict.get("timestamp") or 0.0
                pong_message = self.handler.create_pong_message(client_timestamp)

                if self.client:
                    self.client.send_app_message(pong_message)
                    logger.debug(
                        f"🏓 [Daily] Ping #{self.handler.message_count} from {sender} -> Pong sent"
                    )
            else:
                logger.debug(f"[Daily] Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"[Daily] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[Daily] Error handling app message: {e}", exc_info=True)

    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        logger.error(f"❌ [Daily] Error: {error}")

    async def run(self) -> None:
        """Start the Daily echo handler."""
        try:
            logger.info(f"🚀 [Daily] Starting {self.agent_name}...")

            self.client = CallClient(event_handler=self)

            self.client.update_subscription_profiles(
                {
                    "base": {
                        "camera": "unsubscribed",
                        "microphone": "unsubscribed",
                    }
                }
            )

            logger.info(f"📞 [Daily] Joining room: {self.room_url}")
            self.client.set_user_name(self.agent_name)
            self.client.join(
                self.room_url,
                completion=lambda data, error: self.on_joined(data, error),
            )

            timeout = 10
            for _ in range(timeout * 10):
                if self.is_joined:
                    break
                await asyncio.sleep(0.1)
            else:
                raise TimeoutError(f"Failed to join Daily room within {timeout} seconds")

            logger.info("✨ [Daily] Agent is ready")

            try:
                while not self.should_exit:
                    await asyncio.sleep(1)
            finally:
                if self.client:
                    self.client.leave()
                    self.client.release()
                logger.info(
                    f"👋 [Daily] Agent stopped. Total messages: {self.handler.message_count}"
                )

        except Exception as e:
            logger.error(f"[Daily] Fatal error: {e}", exc_info=True)
            raise


class DailyPlatformHandler(PlatformHandler):
    """Platform handler for Daily."""

    def __init__(self) -> None:
        self.settings = EchoAgentSettings()
        setup_logging(level=self.settings.log_level)

        self.active_handlers: dict[str, DailyEchoHandler] = {}
        self.daily_rest_helper: DailyRESTHelper | None = None
        self.aiohttp_session: aiohttp.ClientSession | None = None
        self.active_rooms: dict[str, Any] = {}
        self.app: FastAPI | None = None
        self.api_thread: threading.Thread | None = None

    async def initialize_daily_helper(self) -> None:
        """Initialize Daily REST helper."""
        if self.aiohttp_session is None:
            self.aiohttp_session = aiohttp.ClientSession()

        self.daily_rest_helper = DailyRESTHelper(
            daily_api_key=self.settings.daily.daily_api_key,
            aiohttp_session=self.aiohttp_session,
        )
        logger.info("✅ Daily REST helper initialized")

    async def create_daily_room(self, expiry_seconds: int = 600) -> DailyRoomInfo:
        """Create a temporary Daily room."""
        if self.daily_rest_helper is None:
            raise RuntimeError("Daily REST helper not initialized")

        expiry_time = time.time() + expiry_seconds

        params = DailyRoomParams(
            properties=DailyRoomProperties(
                exp=int(expiry_time),
                eject_at_room_exp=True,
            )
        )

        room = await self.daily_rest_helper.create_room(params)
        logger.info(f"✅ Created Daily room: {room.url}")

        return DailyRoomInfo(
            room_url=room.url,
            expires_at=expiry_time,
        )

    async def join_daily_room(self, room_url: str, room_id: str) -> None:
        """Join a Daily room on-demand."""
        logger.info(f"🎯 [Daily] Joining on-demand room: {room_id}")

        agent = DailyEchoHandler(
            room_url=room_url,
            agent_name=f"echo-{room_id}",
        )

        self.active_handlers[room_id] = agent

        try:
            await agent.run()
        finally:
            self.active_handlers.pop(room_id, None)
            logger.info(f"👋 [Daily] Left room: {room_id}")

    async def disconnect_from_room(self, room_id: str) -> None:
        """Disconnect from a room."""
        logger.info(f"🔌 [Disconnect] Request for room: {room_id}")

        daily_agent = self.active_handlers.get(room_id)
        if daily_agent:
            logger.info(f"🔌 [Daily] Disconnecting agent from room: {room_id}")
            daily_agent.request_disconnect()
        else:
            logger.info(f"[Daily] No active agent found for room: {room_id}")

        logger.info(f"✅ [Disconnect] Completed for room: {room_id}")

    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        if self.app is None:
            self.app = self._create_app()
        return self.app

    def _create_app(self) -> FastAPI:
        """Create FastAPI application with Daily endpoints."""

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            logger.info("🚀 Starting FastAPI server...")
            await self.initialize_daily_helper()
            yield
            logger.info("🛑 Shutting down FastAPI server...")
            if self.aiohttp_session:
                await self.aiohttp_session.close()

        app = FastAPI(title="Daily Echo Agent API", version="1.0.0", lifespan=lifespan)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok", "platform": "daily"}

        @app.post("/connect", response_model=RoomCredentials)
        async def connect() -> RoomCredentials:
            try:
                room_id = f"benchmark-{int(time.time())}"
                daily_room = await self.create_daily_room(expiry_seconds=600)

                self.active_rooms[room_id] = {
                    "daily_url": daily_room.room_url,
                    "created_at": time.time(),
                }

                logger.info(f"🎯 Created room for session: {room_id}")
                logger.info(f"   Daily: {daily_room.room_url}")

                # Trigger Daily room joining
                task = asyncio.create_task(self.join_daily_room(daily_room.room_url, room_id))
                self.active_rooms[room_id]["daily_join_task"] = task

                return RoomCredentials(
                    room_id=room_id,
                    daily=daily_room,
                    livekit=None,
                )

            except Exception as e:
                logger.error(f"Failed to create room: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Room creation failed: {e!s}") from e

        @app.get("/rooms")
        async def list_rooms() -> dict[str, Any]:
            return {"active_rooms": self.active_rooms}

        @app.post("/disconnect")
        @app.post("/disconnect")
        async def disconnect(request: DisconnectRequest) -> dict[str, Any]:
            room_id = request.room_id

            if room_id not in self.active_rooms:
                raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

            try:
                await self.disconnect_from_room(room_id)
                room_info = self.active_rooms.pop(room_id, None)

                return {
                    "status": "success",
                    "room_id": room_id,
                    "message": f"Disconnected from room {room_id}",
                    "cleaned_up": room_info is not None,
                }
            except Exception as e:
                logger.error(f"Failed to disconnect: {e}", exc_info=True)
                self.active_rooms.pop(room_id, None)
                raise HTTPException(status_code=500, detail=f"Disconnect failed: {e!s}") from e

        return app

    async def run(self, host: str, port: int) -> None:
        """Start the Daily agent and API server."""
        # Validate configuration
        try:
            _ = self.settings.daily.daily_api_key
        except Exception as e:
            logger.error(f"❌ Daily not configured: {e}")
            logger.info("Set DAILY_API_KEY environment variable")
            raise

        logger.info("=" * 72)
        logger.info("🎯 Daily Echo Agent")
        logger.info("=" * 72)
        logger.info("Platform:    daily")
        logger.info(f"API Server:  Running on port {port}")
        logger.info("=" * 72)

        # Initialize Daily SDK
        Daily.init()
        logger.info("✅ Daily SDK initialized")

        # Start FastAPI server in background thread
        app = self.get_app()

        def run_api_server() -> None:
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level=self.settings.log_level.lower(),
            )

        self.api_thread = threading.Thread(target=run_api_server, daemon=True)
        self.api_thread.start()

        logger.info(f"✅ API server started on http://{host}:{port}")
        logger.info("📍 Endpoints: POST /connect, POST /disconnect, GET /health, GET /rooms")
        logger.info("⏳ API server running. Press Ctrl+C to exit.")

        # Keep running
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down Daily agent...")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.aiohttp_session:
            await self.aiohttp_session.close()
        logger.info("✅ Daily platform shutdown complete")


def get_handler() -> DailyPlatformHandler:
    """Get a Daily platform handler instance."""
    return DailyPlatformHandler()
