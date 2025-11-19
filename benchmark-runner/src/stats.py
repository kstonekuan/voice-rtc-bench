"""
Statistical analysis utilities for benchmark results.
"""

import math
from collections.abc import Sequence

from .types import BenchmarkStatistics, LatencyMeasurement


def calculate_statistics(
    measurements: Sequence[LatencyMeasurement],
    total_attempts: int,
) -> BenchmarkStatistics:
    """
    Calculate comprehensive statistics from latency measurements.

    Args:
        measurements: List of successful latency measurements
        total_attempts: Total number of ping attempts (including failed)

    Returns:
        BenchmarkStatistics with all calculated metrics
    """
    successful = len(measurements)
    failed = total_attempts - successful
    packet_loss_rate = failed / total_attempts if total_attempts > 0 else 0.0

    if successful == 0:
        return BenchmarkStatistics(
            total_messages=total_attempts,
            successful_messages=0,
            failed_messages=failed,
            packet_loss_rate=packet_loss_rate,
            mean_rtt=0.0,
            median_rtt=0.0,
            min_rtt=0.0,
            max_rtt=0.0,
            std_dev_rtt=0.0,
            p50_rtt=0.0,
            p95_rtt=0.0,
            p99_rtt=0.0,
            jitter=0.0,
        )

    rtts = [m.round_trip_time for m in measurements]
    sorted_rtts = sorted(rtts)

    return BenchmarkStatistics(
        total_messages=total_attempts,
        successful_messages=successful,
        failed_messages=failed,
        packet_loss_rate=packet_loss_rate,
        mean_rtt=_mean(rtts),
        median_rtt=_percentile(sorted_rtts, 50),
        min_rtt=min(rtts),
        max_rtt=max(rtts),
        std_dev_rtt=_standard_deviation(rtts),
        p50_rtt=_percentile(sorted_rtts, 50),
        p95_rtt=_percentile(sorted_rtts, 95),
        p99_rtt=_percentile(sorted_rtts, 99),
        jitter=_calculate_jitter(rtts),
    )


def _mean(numbers: Sequence[float]) -> float:
    """Calculate mean (average) of numbers."""
    if len(numbers) == 0:
        return 0.0
    return sum(numbers) / len(numbers)


def _standard_deviation(numbers: Sequence[float]) -> float:
    """Calculate standard deviation."""
    if len(numbers) == 0:
        return 0.0

    avg = _mean(numbers)
    square_diffs = [(value - avg) ** 2 for value in numbers]
    avg_square_diff = _mean(square_diffs)
    return math.sqrt(avg_square_diff)


def _percentile(sorted_numbers: Sequence[float], p: float) -> float:
    """
    Calculate percentile from sorted array.

    Args:
        sorted_numbers: Pre-sorted array of numbers
        p: Percentile to calculate (0-100)

    Returns:
        Percentile value using linear interpolation
    """
    if len(sorted_numbers) == 0:
        return 0.0
    if p <= 0:
        return sorted_numbers[0]
    if p >= 100:
        return sorted_numbers[-1]

    index = (p / 100) * (len(sorted_numbers) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    weight = index % 1

    if lower == upper:
        return sorted_numbers[lower]

    return sorted_numbers[lower] * (1 - weight) + sorted_numbers[upper] * weight


def _calculate_jitter(rtts: Sequence[float]) -> float:
    """
    Calculate jitter (average deviation from mean).

    Jitter is calculated as the mean absolute difference between
    consecutive RTT measurements.

    Args:
        rtts: List of RTT values in order

    Returns:
        Jitter value in milliseconds
    """
    if len(rtts) < 2:
        return 0.0

    differences = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
    return _mean(differences)


def format_statistics(stats: BenchmarkStatistics) -> str:
    """
    Format statistics for console output.

    Args:
        stats: BenchmarkStatistics to format

    Returns:
        Formatted string for console display
    """
    lines = [
        "",
        "📊 Benchmark Statistics",
        "─" * 50,
        f"Total Messages:     {stats.total_messages}",
        f"Successful:         {stats.successful_messages}",
        f"Failed:             {stats.failed_messages}",
        f"Packet Loss:        {stats.packet_loss_rate * 100:.2f}%",
        "",
        "Round-Trip Time (RTT):",
        f"  Mean:             {stats.mean_rtt:.2f} ms",
        f"  Median (P50):     {stats.median_rtt:.2f} ms",
        f"  P95:              {stats.p95_rtt:.2f} ms",
        f"  P99:              {stats.p99_rtt:.2f} ms",
        f"  Min:              {stats.min_rtt:.2f} ms",
        f"  Max:              {stats.max_rtt:.2f} ms",
        f"  Std Dev:          {stats.std_dev_rtt:.2f} ms",
        f"  Jitter:           {stats.jitter:.2f} ms",
        "─" * 50,
    ]

    return "\n".join(lines)
