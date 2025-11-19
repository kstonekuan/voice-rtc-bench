"""
Client for echo agent API.

Provides utilities for requesting room credentials from the echo agent.
"""

import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DailyRoomInfo(BaseModel):
    """Daily room information from echo agent."""

    room_url: str
    expires_at: float


class LiveKitRoomInfo(BaseModel):
    """LiveKit room information from echo agent."""

    server_url: str
    room_name: str
    token: str
    expires_at: float


class RoomCredentials(BaseModel):
    """Room credentials from echo agent /connect endpoint."""

    daily: DailyRoomInfo
    livekit: LiveKitRoomInfo


class EchoAgentClient:
    """Client for interacting with the echo agent API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        """
        Initialize echo agent client.

        Args:
            base_url: Base URL of the echo agent API (e.g., http://localhost:8080)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> bool:
        """
        Check if echo agent is healthy.

        Returns:
            True if agent is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                data = response.json()
                return data.get("status") == "ok"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def request_rooms(self) -> RoomCredentials:
        """
        Request room creation from echo agent.

        This calls the /connect endpoint which creates temporary rooms
        for both Daily and LiveKit platforms.

        Returns:
            RoomCredentials containing URLs and tokens for both platforms

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        logger.info(f"Requesting room credentials from: {self.base_url}/connect")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/connect")
                response.raise_for_status()

                data = response.json()
                credentials = RoomCredentials(**data)

                logger.info("✅ Received room credentials:")
                logger.info(f"   Daily room: {credentials.daily.room_url}")
                logger.info(f"   LiveKit room: {credentials.livekit.room_name}")

                return credentials

        except httpx.HTTPError as e:
            logger.error(f"Failed to request rooms: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing room credentials: {e}")
            raise ValueError(f"Invalid response from echo agent: {e}")


async def get_room_credentials(
    echo_agent_url: str, timeout: float | None = None
) -> RoomCredentials:
    """
    Convenience function to get room credentials from echo agent.

    Args:
        echo_agent_url: URL of the echo agent API
        timeout: Optional request timeout in seconds

    Returns:
        RoomCredentials for both platforms
    """
    client = EchoAgentClient(echo_agent_url, timeout=timeout or 30.0)

    # Health check first
    if not await client.health_check():
        raise ConnectionError(f"Echo agent not healthy at {echo_agent_url}")

    return await client.request_rooms()
