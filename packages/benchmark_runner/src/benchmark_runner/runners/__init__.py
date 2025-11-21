"""
Platform-specific benchmark runners.

IMPORTANT: Do not import both DailyBenchmarkRunner and LiveKitBenchmarkRunner
in the same process as they have conflicting WebRTC library dependencies.

Import them separately based on which platform you need:
    from benchmark_runner.runners.daily import DailyBenchmarkRunner
    from benchmark_runner.runners.livekit import LiveKitBenchmarkRunner
"""

# DO NOT import both runners here to avoid library conflicts
# from .daily import DailyBenchmarkRunner  # conflicts with LiveKit
# from .livekit import LiveKitBenchmarkRunner  # conflicts with Daily

__all__ = ["DailyBenchmarkRunner", "LiveKitBenchmarkRunner"]
