"""
Daily platform benchmark runner.
"""

import asyncio
import json
import time
from typing import Any

from daily import CallClient, Daily, EventHandler
from loguru import logger

from ..stats import calculate_statistics
from ..types import (
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkResult,
    LatencyMeasurement,
    PingMessage,
)


class DailyBenchmarkRunner(EventHandler):
    """Benchmark runner for Daily platform."""

    def __init__(self, room_url: str):
        super().__init__()
        self.room_url = room_url
        self.client: CallClient | None = None
        self.is_joined = False

        # Benchmark state
        self.measurements: list[LatencyMeasurement] = []
        self.pending_pings: dict[float, float] = {}  # timestamp -> send_time
        self.total_attempts = 0
        self.benchmark_complete = asyncio.Event()

    def on_joined(self, data: dict[str, Any] | None, error: str | None) -> None:
        """Called when successfully joined the room."""
        if error:
            logger.error(f"Failed to join Daily room: {error}")
            return

        self.is_joined = True
        logger.info(f"✅ Joined Daily room: {self.room_url}")

    def on_app_message(self, message: Any, sender: str) -> None:
        """Handle incoming pong messages."""
        try:
            # Parse incoming message
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            message_type = data.get("type")

            if message_type == "pong":
                receive_time = time.perf_counter() * 1000  # Convert to ms
                client_timestamp = data.get("client_timestamp")

                # Find matching ping
                send_time = self.pending_pings.pop(client_timestamp, None)

                if send_time is not None:
                    # Calculate latency metrics
                    round_trip_time = receive_time - send_time
                    server_receive_time = data.get("server_receive_time")
                    server_send_time = data.get("server_send_time")

                    client_to_server = server_receive_time - client_timestamp
                    server_to_client = receive_time - server_send_time

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

    def on_error(self, error: Any) -> None:
        """Called when an error occurs."""
        logger.error(f"Daily error: {error}")

    async def connect(self) -> None:
        """Connect to the Daily room."""
        Daily.init()
        logger.info("🚀 Initializing Daily benchmark runner...")

        self.client = CallClient(event_handler=self)

        # Configure to not subscribe to video/audio
        self.client.update_subscription_profiles(
            {
                "base": {
                    "camera": "unsubscribed",
                    "microphone": "unsubscribed",
                }
            }
        )

        # Join the room
        logger.info("📞 Joining Daily room...")
        self.client.join(
            self.room_url,
            completion=lambda data, error: self.on_joined(data, error),
            client_settings={
                "user_name": "benchmark-runner",
            },
        )

        # Wait for join to complete
        timeout = 10
        for _ in range(timeout * 10):
            if self.is_joined:
                break
            await asyncio.sleep(0.1)
        else:
            raise TimeoutError(f"Failed to join Daily room within {timeout} seconds")

        logger.info("✅ Connected to Daily room")

    async def disconnect(self) -> None:
        """Disconnect from the Daily room."""
        if self.client:
            self.client.leave()
            self.client.release()
        logger.info("👋 Disconnected from Daily room")

    async def run_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """
        Run the benchmark with the given configuration.

        Args:
            config: Benchmark configuration

        Returns:
            BenchmarkResult with measurements and statistics
        """
        start_time = time.time()
        self.measurements = []
        self.pending_pings = {}
        self.total_attempts = 0

        logger.info(f"🏁 Starting Daily benchmark: {config.iterations} iterations")

        # Send pings
        for i in range(config.iterations):
            timestamp = time.perf_counter() * 1000  # Milliseconds
            send_time = time.perf_counter() * 1000

            ping_message = PingMessage(
                type="ping",
                timestamp=timestamp,
            )

            # Send ping
            if self.client:
                self.client.send_app_message(ping_message.model_dump())
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
            platform="daily",
            room_url=self.room_url,
            location_id=config.location_id,
        )

        return BenchmarkResult(
            platform="daily",
            measurements=self.measurements,
            statistics=statistics,
            metadata=metadata,
        )
