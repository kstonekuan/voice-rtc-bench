"""
Base benchmark runner with common functionality.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Literal, cast

from loguru import logger
from pydantic import ValidationError

from ..stats import calculate_statistics
from ..types import (
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkResult,
    LatencyMeasurement,
    PingMessage,
    PongMessage,
)


class BaseBenchmarkRunner(ABC):
    """Abstract base class for benchmark runners."""

    def __init__(self):
        # Benchmark state shared by all platforms
        self.measurements: list[LatencyMeasurement] = []
        self.pending_pings: dict[float, float] = {}  # timestamp -> send_time
        self.total_attempts = 0

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the platform room. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the platform room. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def send_ping_message(self, ping_message: PingMessage) -> None:
        """Send a ping message via the platform's data channel."""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the platform name (e.g., 'daily', 'livekit')."""
        pass

    def _get_platform_literal(self) -> Literal["daily", "livekit"]:
        """Return platform as literal type for BenchmarkResult."""
        platform = self.get_platform_name()
        if platform not in ("daily", "livekit"):
            raise ValueError(f"Invalid platform: {platform}")
        return cast(Literal["daily", "livekit"], platform)

    @abstractmethod
    def get_room_url(self) -> str:
        """Return the room URL for metadata."""
        pass

    def handle_pong_message(self, data: dict[str, Any]) -> None:
        """
        Handle incoming pong message. Common logic for all platforms.
        Uses Pydantic validation to ensure data integrity.

        Args:
            data: Parsed pong message dictionary
        """
        try:
            # Validate the pong message using Pydantic
            pong = PongMessage.model_validate(data)

            # Only process pong messages
            if pong.type != "pong":
                return

            receive_time = time.perf_counter() * 1000  # Convert to ms

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

        except ValidationError as e:
            logger.warning(f"Invalid pong message format: {e}")
        except Exception as e:
            logger.error(f"Error handling pong message: {e}", exc_info=True)

    async def run_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """
        Run the benchmark with the given configuration.
        Common implementation for all platforms.

        Args:
            config: Benchmark configuration

        Returns:
            BenchmarkResult with measurements and statistics
        """
        start_time = time.time()
        self.measurements = []
        self.pending_pings = {}
        self.total_attempts = 0

        platform_name = self.get_platform_name()
        logger.info(f"🏁 Starting {platform_name} benchmark: {config.iterations} iterations")

        # Send pings
        for i in range(config.iterations):
            timestamp = time.perf_counter() * 1000  # Milliseconds
            send_time = time.perf_counter() * 1000

            ping_message = PingMessage(
                type="ping",
                timestamp=timestamp,
            )

            # Send ping via platform-specific method
            await self.send_ping_message(ping_message)
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
        platform_literal = self._get_platform_literal()
        metadata = BenchmarkMetadata(
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            iterations=config.iterations,
            timeout_ms=config.timeout_ms,
            platform=platform_literal,
            room_url=self.get_room_url(),
            location_id=config.location_id,
        )

        return BenchmarkResult(
            platform=platform_literal,
            measurements=self.measurements,
            statistics=statistics,
            metadata=metadata,
        )
