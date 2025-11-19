"""
Pydantic Settings for environment configuration.

This module provides type-safe environment variable loading and validation
for both the echo agent and benchmark runner packages.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    """Common settings shared across all packages."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )


class DailySettings(BaseSettings):
    """Daily platform configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    daily_api_key: str = Field(..., description="Daily API key for creating rooms")
    daily_api_url: str = Field(
        default="https://api.daily.co/v1",
        description="Daily API URL",
    )
    daily_agent_name: str = Field(
        default="echo-agent",
        description="Agent name for Daily rooms",
    )


class LiveKitSettings(BaseSettings):
    """LiveKit platform configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    livekit_url: str = Field(
        ..., description="LiveKit server URL (e.g., wss://your-project.livekit.cloud)"
    )
    livekit_api_key: str = Field(..., description="LiveKit API key")
    livekit_api_secret: str = Field(..., description="LiveKit API secret")
    livekit_agent_name: str = Field(
        default="echo-agent",
        description="Agent name for LiveKit rooms",
    )


class EchoAgentSettings(BaseSettings):
    """Echo agent server configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8080, description="API server port")

    # Platform credentials (nested settings)
    daily: DailySettings = Field(default_factory=DailySettings)
    livekit: LiveKitSettings = Field(default_factory=LiveKitSettings)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


class TimestreamSettings(BaseSettings):
    """AWS Timestream configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    aws_region: str = Field(default="us-east-1", description="AWS region for Timestream")
    timestream_database: str = Field(
        default="voice-rtc-benchmarks",
        description="Timestream database name",
    )
    timestream_table: str = Field(
        default="latency_measurements",
        description="Timestream table name",
    )


class BenchmarkRunnerSettings(BaseSettings):
    """Benchmark runner configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Echo Agent API
    echo_agent_url: str = Field(
        default="http://localhost:8080",
        description="URL of the echo agent API",
    )

    # Benchmark parameters
    iterations: int = Field(default=100, ge=10, le=10000, description="Number of ping iterations")
    timeout_ms: int = Field(
        default=5000, ge=1000, le=30000, description="Timeout per ping in milliseconds"
    )
    cooldown_ms: int = Field(
        default=100, ge=0, le=5000, description="Cooldown between pings in milliseconds"
    )
    location_id: str = Field(default="unknown", description="Deployment location identifier")

    # AWS Timestream
    timestream: TimestreamSettings = Field(default_factory=TimestreamSettings)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
