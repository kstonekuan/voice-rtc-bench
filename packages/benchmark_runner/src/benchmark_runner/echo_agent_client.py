"""
Client for echo agent API.

Provides utilities for requesting room credentials from the echo agent.
"""

import httpx
from loguru import logger
from shared.types import RoomCredentials


class EchoAgentClient:
    """Client for interacting with the echo agent API."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
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

        This calls the /connect endpoint which creates a temporary room
        for the platform (Daily or LiveKit depending on which agent is running).

        Returns:
            RoomCredentials containing URLs and tokens (either Daily or LiveKit, not both)

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

                # Log which platform credentials were received
                if credentials.daily is not None:
                    logger.info("✅ Received Daily room credentials:")
                    logger.info(f"   Daily room: {credentials.daily.room_url}")
                elif credentials.livekit is not None:
                    logger.info("✅ Received LiveKit room credentials:")
                    logger.info(f"   LiveKit room: {credentials.livekit.room_name}")
                else:
                    raise ValueError("No credentials received from echo agent")

                return credentials

        except httpx.HTTPError as e:
            logger.error(f"Failed to request rooms: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing room credentials: {e}")
            raise ValueError(f"Invalid response from echo agent: {e}") from e

    async def disconnect_room(self, room_id: str) -> bool:
        """
        Request disconnection from a room.

        This calls the /disconnect endpoint which triggers the echo agent
        to disconnect from the specified room and clean up resources.

        Args:
            room_id: Identifier of the room to disconnect from

        Returns:
            True if disconnection was successful, False otherwise

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Requesting disconnection from room: {room_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/disconnect", json={"room_id": room_id}
                )
                response.raise_for_status()

                data = response.json()
                logger.info(f"✅ Disconnected from room: {room_id}")
                return data.get("status") == "success"

        except httpx.HTTPError as e:
            logger.error(f"Failed to disconnect from room {room_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error disconnecting from room {room_id}: {e}")
            return False


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
