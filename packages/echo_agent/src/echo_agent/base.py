"""
Base interface for platform handlers.

Defines the common interface that both Daily and LiveKit platforms must implement.
"""

from abc import ABC, abstractmethod

from fastapi import FastAPI


class PlatformHandler(ABC):
    """Abstract base class for platform-specific handlers."""

    @abstractmethod
    async def run(self, host: str, port: int) -> None:
        """
        Start the platform-specific agent and API server.

        Args:
            host: API server host
            port: API server port
        """
        pass

    @abstractmethod
    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.

        Returns:
            FastAPI app with platform-specific endpoints
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources and shutdown gracefully."""
        pass
