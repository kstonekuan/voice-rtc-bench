"""
LiveKit platform implementation.

Contains all LiveKit-specific code including agent logic and API endpoints.
"""

import asyncio
import json
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from livekit import api as livekit_api
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from loguru import logger
from pydantic import BaseModel
from shared.settings import EchoAgentSettings
from shared.types import LiveKitRoomInfo, PongMessage, RoomCredentials
from shared.utils import setup_logging

from echo_agent.base import PlatformHandler


class DisconnectRequest(BaseModel):
    """Request model for disconnecting from a room."""

    room_id: str


class MessageHandler:
    """Message handling logic for LiveKit platform."""

    def __init__(self) -> None:
        self.message_count = 0

    def create_pong_message(self, client_timestamp: float) -> dict[str, Any]:
        """Create a pong response message."""
        self.message_count += 1
        server_receive_time = time.time() * 1000

        pong = PongMessage(
            client_timestamp=client_timestamp,
            server_receive_time=server_receive_time,
            server_send_time=time.time() * 1000,
            message_count=self.message_count,
        )
        return pong.model_dump()


class LiveKitEchoHandler:
    """LiveKit-specific echo handler."""

    def __init__(self, agent_name: str = "livekit-echo") -> None:
        self.agent_name = agent_name
        self.room: rtc.Room | None = None
        self.handler = MessageHandler()
        self.background_tasks: set[asyncio.Task] = set()
        self.exit_event = asyncio.Event()

    def request_disconnect(self) -> None:
        """Request the agent to disconnect from the room."""
        logger.info(f"[LiveKit] Disconnect requested for {self.agent_name}")
        self.exit_event.set()

    async def handle_data_received(self, data_packet: rtc.DataPacket) -> None:
        """Handle incoming data channel messages."""
        try:
            message_str = data_packet.data.decode("utf-8")
            data = json.loads(message_str)

            message_type = data.get("type")

            if message_type == "ping":
                client_timestamp = data.get("timestamp")
                pong_message = self.handler.create_pong_message(client_timestamp)

                if self.room:
                    pong_json = json.dumps(pong_message)
                    await self.room.local_participant.publish_data(
                        pong_json.encode("utf-8"),
                        reliable=True,
                    )
                    logger.debug(f"🏓 [LiveKit] Ping #{self.handler.message_count} -> Pong sent")
            else:
                logger.debug(f"[LiveKit] Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"[LiveKit] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[LiveKit] Error handling data packet: {e}", exc_info=True)

    async def entrypoint(self, ctx: JobContext) -> None:
        """Agent entrypoint - called when assigned to a room."""
        logger.info(f"🚀 [LiveKit] {self.agent_name} starting...")
        logger.info(f"📞 [LiveKit] Connecting to room: {ctx.room.name}")

        self.room = ctx.room

        @ctx.room.on("data_received")
        def on_data_received(data_packet: rtc.DataPacket) -> None:
            task = asyncio.create_task(self.handle_data_received(data_packet))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        @ctx.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            logger.info(f"[LiveKit] Participant connected: {participant.identity}")

        @ctx.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            logger.info(f"[LiveKit] Participant disconnected: {participant.identity}")

        await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_NONE)

        logger.info("✅ [LiveKit] Connected to room successfully")
        logger.info("👂 [LiveKit] Listening for ping messages...")
        logger.info("✨ [LiveKit] Agent is ready")

        await self.exit_event.wait()
        logger.info(f"👋 [LiveKit] Agent stopped. Total messages: {self.handler.message_count}")


class LiveKitPlatformHandler(PlatformHandler):
    """Platform handler for LiveKit."""

    def __init__(self) -> None:
        self.settings = EchoAgentSettings()
        setup_logging(level=self.settings.log_level)

        self.active_rooms: dict[str, Any] = {}
        self.app: FastAPI | None = None
        self.api_thread: threading.Thread | None = None

    def create_livekit_token(self, room_name: str, expiry_seconds: int = 600) -> LiveKitRoomInfo:
        """Generate LiveKit access token for a room."""
        expiry_time = time.time() + expiry_seconds

        token_obj = livekit_api.AccessToken(
            self.settings.livekit.livekit_api_key, self.settings.livekit.livekit_api_secret
        )
        token_obj.with_identity("benchmark-runner")
        token_obj.with_name("benchmark-runner")
        token_obj.with_grants(
            livekit_api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        token_obj.with_ttl(timedelta(seconds=expiry_seconds))

        token = token_obj.to_jwt()
        logger.info(f"✅ Generated LiveKit token for room: {room_name}")

        return LiveKitRoomInfo(
            server_url=self.settings.livekit.livekit_url,
            room_name=room_name,
            token=token,
            expires_at=expiry_time,
        )

    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        if self.app is None:
            self.app = self._create_app()
        return self.app

    def _create_app(self) -> FastAPI:
        """Create FastAPI application with LiveKit endpoints."""

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            logger.info("🚀 Starting FastAPI server...")
            yield
            logger.info("🛑 Shutting down FastAPI server...")

        app = FastAPI(title="LiveKit Echo Agent API", version="1.0.0", lifespan=lifespan)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok", "platform": "livekit"}

        @app.post("/connect", response_model=RoomCredentials)
        async def connect() -> RoomCredentials:
            try:
                room_id = f"benchmark-{int(time.time())}"
                livekit_room = self.create_livekit_token(room_name=room_id, expiry_seconds=600)

                self.active_rooms[room_id] = {
                    "livekit_room": livekit_room.room_name,
                    "created_at": time.time(),
                }

                logger.info(f"🎯 Created room for session: {room_id}")
                logger.info(f"   LiveKit: {livekit_room.room_name}")

                return RoomCredentials(
                    room_id=room_id,
                    daily=None,
                    livekit=livekit_room,
                )

            except Exception as e:
                logger.error(f"Failed to create room: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Room creation failed: {e!s}") from e

        @app.get("/rooms")
        async def list_rooms() -> dict[str, Any]:
            return {"active_rooms": self.active_rooms}

        @app.post("/disconnect")
        async def disconnect(request: DisconnectRequest) -> dict[str, Any]:
            room_id = request.room_id

            if room_id not in self.active_rooms:
                raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

            try:
                room_info = self.active_rooms.pop(room_id, None)
                logger.info(f"🧹 Cleaned up room tracking for: {room_id}")

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

    async def livekit_request_fnc(self, ctx: JobContext) -> None:
        """Request function for LiveKit agent worker."""
        logger.info(f"[LiveKit] Received job request for room: {ctx.room.name}")
        agent = LiveKitEchoHandler()
        await agent.entrypoint(ctx)

    def run_livekit_worker(self) -> None:
        """Run the LiveKit worker."""
        logger.info("🎯 [LiveKit] Worker starting...")
        cli.run_app(
            WorkerOptions(
                entrypoint_fnc=self.livekit_request_fnc,
            )
        )

    async def run(self, host: str, port: int) -> None:
        """Start the LiveKit agent and API server."""
        # Validate configuration
        try:
            _ = self.settings.livekit.livekit_url
            _ = self.settings.livekit.livekit_api_key
            _ = self.settings.livekit.livekit_api_secret
        except Exception as e:
            logger.error(f"❌ LiveKit not configured: {e}")
            logger.info(
                "Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET environment variables"
            )
            raise

        logger.info("=" * 72)
        logger.info("🎯 LiveKit Echo Agent")
        logger.info("=" * 72)
        logger.info("Platform:    livekit")
        logger.info(f"API Server:  Running on port {port}")
        logger.info("=" * 72)

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

        # Start LiveKit worker
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self.run_livekit_worker)]

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down LiveKit agent...")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Clean up resources."""
        logger.info("✅ LiveKit platform shutdown complete")


def get_handler() -> LiveKitPlatformHandler:
    """Get a LiveKit platform handler instance."""
    return LiveKitPlatformHandler()
