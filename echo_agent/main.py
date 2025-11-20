#!/usr/bin/env python3
"""
Unified Echo Agent - Responds to ping messages for both Daily and LiveKit.

This agent runs both Daily and LiveKit echo handlers concurrently,
providing a single deployment for benchmarking both platforms.

The agent also exposes a FastAPI server for on-demand room creation.
"""

import asyncio
import json
import sys
import threading
import time
from typing import Any

import uvicorn
from daily import CallClient, Daily, EventHandler
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from loguru import logger
from shared.settings import EchoAgentSettings
from shared.types import PongMessage
from shared.utils import setup_logging

# Load settings from environment
settings = EchoAgentSettings()

# Configure logging
setup_logging(level=settings.log_level)

# Global reference to active Daily handlers
active_daily_handlers: dict[str, "DailyEchoHandler"] = {}


class MessageHandler:
    """Shared message handling logic for both platforms."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.message_count = 0

    def create_pong_message(self, client_timestamp: float) -> dict[str, Any]:
        """
        Create a pong response message.

        Args:
            client_timestamp: The original client timestamp from the ping

        Returns:
            Pong message dictionary with timing information
        """
        self.message_count += 1
        server_receive_time = time.time() * 1000  # Convert to milliseconds

        # Use shared PongMessage type
        pong = PongMessage(
            client_timestamp=client_timestamp,
            server_receive_time=server_receive_time,
            server_send_time=time.time() * 1000,
            message_count=self.message_count,
        )
        return pong.model_dump()


class DailyEchoHandler(EventHandler):
    """Daily-specific echo handler."""

    def __init__(self, room_url: str, agent_name: str = "unified-daily-echo"):
        super().__init__()
        self.room_url = room_url
        self.agent_name = agent_name
        self.client: CallClient | None = None
        self.is_joined = False
        self.should_exit = False
        self.handler = MessageHandler("Daily")

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

        # Check if any non-agent participants remain
        if self.client:
            participants = self.client.participants()
            # Filter out the agent itself from the participant list
            non_agent_participants = [
                p for p_id, p in participants.items() if p.get("user_name") != self.agent_name
            ]

            if not non_agent_participants:
                logger.info("[Daily] Last client disconnected. Exiting room.")
                self.should_exit = True

    def on_app_message(self, message: Any, sender: str) -> None:
        """Handle incoming app-message event."""
        try:
            # Parse incoming message
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            message_type = data.get("type")

            if message_type == "ping":
                client_timestamp = data.get("timestamp")
                pong_message = self.handler.create_pong_message(client_timestamp)

                # Send response immediately
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

    def on_error(self, error: Any) -> None:
        """Called when an error occurs."""
        logger.error(f"❌ [Daily] Error: {error}")

    async def run(self) -> None:
        """Start the Daily echo handler."""
        try:
            # Initialize Daily
            Daily.init()
            logger.info(f"🚀 [Daily] Starting {self.agent_name}...")

            # Create client
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
            logger.info(f"📞 [Daily] Joining room: {self.room_url}")
            self.client.join(
                self.room_url,
                completion=lambda data, error: self.on_joined(data, error),
                client_settings={
                    "user_name": self.agent_name,
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

            logger.info("✨ [Daily] Agent is ready")

            # Run until client disconnects or interrupted
            try:
                while not self.should_exit:
                    await asyncio.sleep(1)
            finally:
                # Clean up
                if self.client:
                    self.client.leave()
                    self.client.release()
                logger.info(
                    f"👋 [Daily] Agent stopped. Total messages: {self.handler.message_count}"
                )

        except Exception as e:
            logger.error(f"[Daily] Fatal error: {e}", exc_info=True)
            raise


class LiveKitEchoHandler:
    """LiveKit-specific echo handler."""

    def __init__(self, agent_name: str = "unified-livekit-echo"):
        self.agent_name = agent_name
        self.room: rtc.Room | None = None
        self.handler = MessageHandler("LiveKit")
        self.background_tasks: set[asyncio.Task] = set()
        self.exit_event = asyncio.Event()

    async def handle_data_received(self, data_packet: rtc.DataPacket) -> None:
        """Handle incoming data channel messages."""
        try:
            # Decode message
            message_str = data_packet.data.decode("utf-8")
            data = json.loads(message_str)

            message_type = data.get("type")

            if message_type == "ping":
                client_timestamp = data.get("timestamp")
                pong_message = self.handler.create_pong_message(client_timestamp)

                # Send response immediately via data channel
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

        # Set up data channel listener
        @ctx.room.on("data_received")
        def on_data_received(data_packet: rtc.DataPacket):
            task = asyncio.create_task(self.handle_data_received(data_packet))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # Log when participants join/leave
        @ctx.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"[LiveKit] Participant connected: {participant.identity}")

        @ctx.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"[LiveKit] Participant disconnected: {participant.identity}")

            # Check if any remote participants remain
            if self.room and not self.room.remote_participants:
                logger.info("[LiveKit] Last client disconnected. Exiting room.")
                self.exit_event.set()

        # Wait for connection
        await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_NONE)

        logger.info("✅ [LiveKit] Connected to room successfully")
        logger.info("👂 [LiveKit] Listening for ping messages...")
        logger.info("✨ [LiveKit] Agent is ready")

        # Keep agent alive until exit event is set
        await self.exit_event.wait()
        logger.info(f"👋 [LiveKit] Agent stopped. Total messages: {self.handler.message_count}")


async def livekit_request_fnc(ctx: JobContext) -> None:
    """Request function for LiveKit agent worker."""
    logger.info(f"[LiveKit] Received job request for room: {ctx.room.name}")

    agent = LiveKitEchoHandler()

    await agent.entrypoint(ctx)


def run_livekit_worker() -> None:
    """Run the LiveKit worker in a separate process."""
    logger.info("🎯 [LiveKit] Worker starting...")

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=livekit_request_fnc,
        )
    )


async def run_daily_agent(room_url: str) -> None:
    """Run the Daily agent."""
    agent = DailyEchoHandler(room_url=room_url)
    await agent.run()


async def join_daily_room(room_url: str, room_id: str) -> None:
    """
    Join a Daily room on-demand.

    This is called when /connect API creates a new room.

    Args:
        room_url: Daily room URL to join
        room_id: Unique identifier for this room session
    """
    logger.info(f"🎯 [Daily] Joining on-demand room: {room_id}")

    agent = DailyEchoHandler(
        room_url=room_url,
        agent_name=f"echo-{room_id}",
    )

    # Store reference
    active_daily_handlers[room_id] = agent

    try:
        await agent.run()
    finally:
        # Clean up when agent exits
        active_daily_handlers.pop(room_id, None)
        logger.info(f"👋 [Daily] Left room: {room_id}")


async def main() -> None:
    """Main entry point - runs API server and LiveKit worker."""
    # Validate configuration - settings will raise validation error if required fields are missing
    # For optional platform enablement, we'll try to access settings and catch validation errors
    enable_daily = False
    enable_livekit = False

    try:
        # Try to access Daily settings
        _ = settings.daily.daily_api_key
        enable_daily = True
    except Exception:
        pass

    try:
        # Try to access LiveKit settings
        _ = settings.livekit.livekit_url
        _ = settings.livekit.livekit_api_key
        _ = settings.livekit.livekit_api_secret
        enable_livekit = True
    except Exception:
        pass

    if not enable_daily and not enable_livekit:
        logger.error("❌ No platform configured!")
        logger.info("Configure at least one platform:")
        logger.info("  Daily: Set DAILY_API_KEY (for on-demand room creation)")
        logger.info("  LiveKit: Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
        sys.exit(1)

    logger.info("=" * 72)
    logger.info("🎯 Unified Echo Agent with On-Demand Room Creation")
    logger.info("=" * 72)
    logger.info(f"Daily API:   {'✅ Enabled' if enable_daily else '❌ Disabled'}")
    logger.info(f"LiveKit:     {'✅ Enabled' if enable_livekit else '❌ Disabled'}")
    logger.info(f"API Server:  ✅ Running on port {settings.api_port}")
    logger.info("=" * 72)

    tasks = []

    # Start FastAPI server in background thread
    api_port = settings.api_port
    api_host = settings.api_host

    def run_api_server():
        """Run FastAPI server in background thread."""
        from api import app

        uvicorn.run(
            app,
            host=api_host,
            port=api_port,
            log_level=settings.log_level.lower(),
        )

    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    logger.info(f"✅ API server started on http://{api_host}:{api_port}")
    logger.info("📍 Endpoints: POST /connect, GET /health, GET /rooms")

    # Set callback for Daily room joining
    if enable_daily:
        from api import set_daily_room_callback

        set_daily_room_callback(join_daily_room)
        logger.info("✅ Daily room join callback configured")

    # Initialize Daily SDK
    if enable_daily:
        Daily.init()
        logger.info("✅ Daily SDK initialized (on-demand room creation)")

    # Start LiveKit worker if configured
    if enable_livekit:
        # LiveKit agent uses blocking CLI worker, so run in executor
        loop = asyncio.get_event_loop()
        tasks.append(loop.run_in_executor(None, run_livekit_worker))
    else:
        logger.warning("⚠️  LiveKit disabled - worker not started")

    # Keep main loop running
    if tasks:
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down unified agent...")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)
    else:
        # No background tasks, just keep API server running
        logger.info("⏳ API server running. Press Ctrl+C to exit.")
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down unified agent...")


if __name__ == "__main__":
    asyncio.run(main())
