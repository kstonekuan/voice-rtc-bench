"""
Shared type definitions for voice-rtc-bench.

This module contains common Pydantic models used across the benchmark runner
and echo agent packages.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


# Protocol message types
class PingMessage(BaseModel):
    """Ping message sent from client to agent."""

    type: Literal["ping"] = "ping"
    timestamp: float


class PongMessage(BaseModel):
    """Pong message received from agent."""

    type: Literal["pong"] = "pong"
    client_timestamp: float
    server_receive_time: float
    server_send_time: float
    message_count: int


# Room credential types
class DailyRoomInfo(BaseModel):
    """Daily room information."""

    room_url: str
    expires_at: float


class LiveKitRoomInfo(BaseModel):
    """LiveKit room information."""

    server_url: str
    room_name: str
    token: str
    expires_at: float


class RoomCredentials(BaseModel):
    """Room credentials for both Daily and LiveKit platforms."""

    room_id: str
    daily: DailyRoomInfo | None = None
    livekit: LiveKitRoomInfo | None = None


# Benchmark result types
class LatencyMeasurement(BaseModel):
    """Single latency measurement."""

    round_trip_time: float = Field(description="Total RTT in milliseconds")
    client_to_server: float = Field(description="One-way latency estimate (ms)")
    server_to_client: float = Field(description="One-way latency estimate (ms)")
    message_number: int
    timestamp: float


class BenchmarkStatistics(BaseModel):
    """Comprehensive statistics from benchmark results."""

    total_messages: int
    successful_messages: int
    failed_messages: int
    packet_loss_rate: float

    # RTT statistics (in milliseconds)
    mean_rtt: float
    median_rtt: float
    min_rtt: float
    max_rtt: float
    std_dev_rtt: float
    p50_rtt: float
    p95_rtt: float
    p99_rtt: float

    # Jitter (variation in latency)
    jitter: float


class BenchmarkMetadata(BaseModel):
    """Metadata about the benchmark run."""

    start_time: float
    end_time: float
    duration_ms: float
    iterations: int
    timeout_ms: int
    platform: str
    room_url: str | None = None
    location_id: str | None = Field(default=None, description="Deployment location identifier")
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this benchmark run")


class BenchmarkResult(BaseModel):
    """Complete benchmark result."""

    platform: Literal["daily", "livekit"]
    measurements: list[LatencyMeasurement]
    statistics: BenchmarkStatistics
    metadata: BenchmarkMetadata


class BenchmarkConfig(BaseModel):
    """Configuration for running a benchmark."""

    iterations: int = Field(default=100, ge=10, le=10000)
    timeout_ms: int = Field(default=5000, ge=1000, le=30000)
    cooldown_ms: int = Field(default=100, ge=0, le=5000)
    location_id: str | None = Field(default=None, description="Deployment location identifier")
