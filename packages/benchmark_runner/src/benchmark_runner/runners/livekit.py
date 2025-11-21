"""
LiveKit platform benchmark runner.
"""

from livekit import rtc
from loguru import logger
from pydantic import ValidationError

from benchmark_runner.types import PingMessage, PongMessage

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
            # Use Pydantic V2's Rust-based JSON parser (faster than orjson + validate)
            # See: https://github.com/pydantic/pydantic/discussions/6388#discussioncomment-13944196
            # This skips intermediate dict conversion and validates in one fast Rust operation
            pong = PongMessage.model_validate_json(payload)

            # Only process pong messages
            if pong.type != "pong":
                return

            import time

            receive_time = time.perf_counter() * 1000

            # Find matching ping
            send_time = self.pending_pings.pop(pong.client_timestamp, None)

            if send_time is not None:
                from benchmark_runner.types import LatencyMeasurement

                # Calculate latency metrics
                round_trip_time = receive_time - send_time
                client_to_server = pong.server_receive_time - pong.client_timestamp
                server_to_client = receive_time - pong.server_send_time

                measurement = LatencyMeasurement(
                    round_trip_time=round_trip_time,
                    client_to_server=client_to_server,
                    server_to_client=server_to_client,
                    message_number=len(self.measurements) + 1,
                    timestamp=receive_time,
                )

                self.measurements.append(measurement)
                logger.debug(
                    f"📊 Measurement #{measurement.message_number}: RTT={round_trip_time:.2f}ms"
                )

        except ValidationError as e:
            logger.warning(f"Invalid pong message format: {e}")
        except Exception as e:
            logger.error(f"Error handling pong message: {e}", exc_info=True)

    async def connect(self) -> None:
        """Connect to the LiveKit room."""
        import asyncio

        logger.info("🚀 Initializing LiveKit benchmark runner...")

        self.room = rtc.Room()
        agent_connected = asyncio.Event()

        # Set up event handlers
        @self.room.on("data_received")
        def on_data_received(data: rtc.DataPacket) -> None:
            self._handle_data_received(data.data, data.participant)

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            logger.debug(f"Participant connected: {participant.identity}")
            # Signal that agent is connected
            agent_connected.set()

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            logger.debug(f"Participant disconnected: {participant.identity}")

        # Connect to room
        logger.info("📞 Connecting to LiveKit room...")
        await self.room.connect(self.server_url, self.token)

        logger.info("✅ Connected to LiveKit room")

        # Wait for agent to connect (with timeout)
        logger.info("⏳ Waiting for echo agent to connect...")
        try:
            await asyncio.wait_for(agent_connected.wait(), timeout=10.0)
            logger.info("✅ Echo agent connected and ready")
        except TimeoutError:
            logger.warning("⚠️ Timeout waiting for agent, proceeding anyway...")

        # Add small additional delay to ensure data channel is ready
        await asyncio.sleep(0.1)

    async def disconnect(self) -> None:
        """Disconnect from the LiveKit room."""
        if self.room:
            await self.room.disconnect()
        logger.info("👋 Disconnected from LiveKit room")

    async def send_ping_message(self, ping_message: PingMessage) -> None:
        """Send a ping message via LiveKit's data channel."""
        if not self.room:
            raise RuntimeError("Must call connect() before sending messages")

        # Use Pydantic V2's Rust-based serializer (faster than orjson)
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
