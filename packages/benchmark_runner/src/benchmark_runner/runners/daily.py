"""
Daily platform benchmark runner.
"""

import asyncio
import json
from typing import Any, cast

from daily import CallClient, Daily, EventHandler
from loguru import logger

from benchmark_runner.types import PingMessage

from .base import BaseBenchmarkRunner


class DailyBenchmarkRunner(EventHandler, BaseBenchmarkRunner):
    """Benchmark runner for Daily platform."""

    def __init__(self, room_url: str) -> None:
        EventHandler.__init__(self)
        BaseBenchmarkRunner.__init__(self)
        self.room_url = room_url
        self.client: CallClient | None = None
        self.is_joined = False

    def on_joined(self, data: dict[str, Any] | None, error: str | None) -> None:
        """Called when successfully joined the room."""
        if error:
            logger.error(f"Failed to join Daily room: {error}")
            return

        self.is_joined = True
        logger.info(f"✅ Joined Daily room: {self.room_url}")

    def on_app_message(self, message: object, sender: str) -> None:
        """Handle incoming pong messages."""
        try:
            # Parse incoming message
            data = json.loads(message) if isinstance(message, str) else message
            # Delegate to base class handler
            self.handle_pong_message(cast(dict[str, Any], data))

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse pong message: {e}")
        except Exception as e:
            logger.error(f"Error handling pong message: {e}", exc_info=True)

    def on_error(self, error: Exception) -> None:
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
        self.client.set_user_name("benchmark-runner")
        self.client.join(
            self.room_url,
            completion=lambda data, error: self.on_joined(data, error),
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

    async def send_ping_message(self, ping_message: PingMessage) -> None:
        """Send a ping message via Daily's app message channel."""
        if self.client:
            self.client.send_app_message(ping_message.model_dump())

    def get_platform_name(self) -> str:
        """Return the platform name."""
        return "daily"

    def get_room_url(self) -> str:
        """Return the room URL."""
        return self.room_url
