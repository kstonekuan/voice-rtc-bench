"""
LiveKit platform benchmark runner.
"""

import asyncio
import json
import time

from livekit import rtc
from loguru import logger

from ..stats import calculate_statistics
from ..types import (
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkResult,
    LatencyMeasurement,
    PingMessage,
    PongMessage,
)


class LiveKitBenchmarkRunner:
    """Benchmark runner for LiveKit platform."""

    def __init__(self, server_url: str, token: str):
        self.server_url = server_url
        self.token = token
        self.room: rtc.Room | None = None

        # Benchmark state
        self.measurements: list[LatencyMeasurement] = []
        self.pending_pings: dict[float, float] = {}  # timestamp -> send_time
        self.total_attempts = 0

    def _handle_data_received(self, payload: bytes, participant: rtc.Participant | None) -> None:
        """Handle incoming data channel messages."""
        try:
            # Decode message
            message_str = payload.decode("utf-8")
            data = json.loads(message_str)

            message_type = data.get("type")

            if message_type == "pong":
                receive_time = time.perf_counter() * 1000  # Convert to ms
                pong = PongMessage(**data)

                # Find matching ping
                send_time = self.pending_pings.pop(pong.client_timestamp, None)

                if send_time is not None:
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
        def on_data_received(data: rtc.DataPacket):
            self._handle_data_received(data.data, data.participant)

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.debug(f"Participant connected: {participant.identity}")

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
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

    async def run_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """
        Run the benchmark with the given configuration.

        Args:
            config: Benchmark configuration

        Returns:
            BenchmarkResult with measurements and statistics
        """
        if not self.room:
            raise RuntimeError("Must call connect() before running benchmark")

        start_time = time.time()
        self.measurements = []
        self.pending_pings = {}
        self.total_attempts = 0

        logger.info(f"🏁 Starting LiveKit benchmark: {config.iterations} iterations")

        # Send pings
        for i in range(config.iterations):
            timestamp = time.perf_counter() * 1000  # Milliseconds
            send_time = time.perf_counter() * 1000

            ping_message = PingMessage(
                type="ping",
                timestamp=timestamp,
            )

            # Send ping via data channel
            ping_json = ping_message.model_dump_json()
            await self.room.local_participant.publish_data(
                ping_json.encode("utf-8"),
                reliable=True,
            )

            self.pending_pings[timestamp] = send_time
            self.total_attempts += 1

            logger.debug(f"📤 Sent ping #{i + 1}/{config.iterations}")

            # Wait cooldown period
            await asyncio.sleep(config.cooldown_ms / 1000)

        # Wait for remaining pongs with timeout
        logger.info(f"⏳ Waiting for remaining pongs (timeout: {config.timeout_ms}ms)...")
        wait_start = time.time()
        while len(self.pending_pings) > 0:
            elapsed_ms = (time.time() - wait_start) * 1000
            if elapsed_ms > config.timeout_ms:
                logger.warning(
                    f"⚠️ Timeout reached. {len(self.pending_pings)} pings did not receive pongs"
                )
                break
            await asyncio.sleep(0.01)

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        logger.info(
            f"✅ Benchmark complete: {len(self.measurements)}/{self.total_attempts} successful"
        )

        # Calculate statistics
        statistics = calculate_statistics(self.measurements, self.total_attempts)

        # Create metadata
        metadata = BenchmarkMetadata(
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            iterations=config.iterations,
            timeout_ms=config.timeout_ms,
            platform="livekit",
            room_url=self.server_url,
            location_id=config.location_id,
        )

        return BenchmarkResult(
            platform="livekit",
            measurements=self.measurements,
            statistics=statistics,
            metadata=metadata,
        )
