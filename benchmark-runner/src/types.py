"""
Type definitions for the benchmark runner.

This module re-exports types from the shared package for backward compatibility.
"""

# Re-export all types from shared package
from shared.types import (
    BenchmarkConfig,
    BenchmarkMetadata,
    BenchmarkResult,
    BenchmarkStatistics,
    LatencyMeasurement,
    PingMessage,
    PongMessage,
)

__all__ = [
    "BenchmarkConfig",
    "BenchmarkMetadata",
    "BenchmarkResult",
    "BenchmarkStatistics",
    "LatencyMeasurement",
    "PingMessage",
    "PongMessage",
]
