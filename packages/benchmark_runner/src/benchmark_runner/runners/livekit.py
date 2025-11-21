"""
LiveKit platform benchmark runner.
"""

import json

from livekit import rtc
from loguru import logger

from benchmark_runner.types import PingMessage

from .base import BaseBenchmarkRunner


class LiveKitBenchmarkRunner(BaseBenchmarkRunner):
    """Benchmark runner for LiveKit platform."""

    def __init__(self, server_url: str, token: str) -> None:
        super().__init__()
        self.server_url = server_url
        self.token = token
        self.room: rtc.Room | None = None

    def _handle_data_received(self, payload: bytes, participant: rtc.Participant | None) -> None:
        """Handle incoming data channel messages."""
        try:
            # Decode message
            message_str = payload.decode("utf-8")
            data = json.loads(message_str)

            # Delegate to base class handler
            self.handle_pong_message(data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse pong message: {e}")
        except Exception as e:
            logger.error(f"Error handling pong message: {e}", exc_info=True)

    async def connect(self) -> None:
        """Connect to the LiveKit room."""
        logger.info("🚀 Initializing LiveKit benchmark runner...")

        self.room = rtc.Room()

        # Set up event handlers
        @self.room.on("data_received")
        def on_data_received(data: rtc.DataPacket) -> None:
            self._handle_data_received(data.data, data.participant)

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            logger.debug(f"Participant connected: {participant.identity}")

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            logger.debug(f"Participant disconnected: {participant.identity}")

        # Connect to room
        logger.info("📞 Connecting to LiveKit room...")
        await self.room.connect(self.server_url, self.token)

        logger.info("✅ Connected to LiveKit room")

    async def disconnect(self) -> None:
        """Disconnect from the LiveKit room."""
        if self.room:
            await self.room.disconnect()
        logger.info("👋 Disconnected from LiveKit room")

    async def send_ping_message(self, ping_message: PingMessage) -> None:
        """Send a ping message via LiveKit's data channel."""
        if not self.room:
            raise RuntimeError("Must call connect() before sending messages")

        ping_json = ping_message.model_dump_json()
        await self.room.local_participant.publish_data(
            ping_json.encode("utf-8"),
            reliable=True,
        )

    def get_platform_name(self) -> str:
        """Return the platform name."""
        return "livekit"

    def get_room_url(self) -> str:
        """Return the room URL."""
        return self.server_url
