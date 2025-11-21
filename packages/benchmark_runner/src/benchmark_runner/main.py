#!/usr/bin/env python3
"""
Benchmark Runner - Entry point for CLI.

Supports Daily or LiveKit platforms with completely separate implementations
to avoid library conflicts.
"""

import argparse
import sys

# Parse CLI arguments BEFORE any platform imports
parser = argparse.ArgumentParser(description="Benchmark Runner for Daily or LiveKit")
parser.add_argument(
    "--platform",
    choices=["daily", "livekit"],
    required=True,
    help="Platform to benchmark (daily or livekit)",
)
parser.add_argument(
    "--agent-url",
    type=str,
    required=True,
    help="Echo agent API URL",
)
parser.add_argument(
    "--iterations",
    type=int,
    default=None,
    help="Number of ping iterations (default: from env/settings)",
)
parser.add_argument(
    "--timeout",
    type=int,
    default=None,
    help="Timeout in milliseconds (default: from env/settings)",
)
parser.add_argument(
    "--cooldown",
    type=int,
    default=None,
    help="Cooldown between pings in milliseconds (default: from env/settings)",
)
parser.add_argument(
    "--location",
    type=str,
    default=None,
    help="Location identifier (default: from env/settings)",
)
parser.add_argument(
    "--output",
    type=str,
    default=None,
    help="Save results to JSON file",
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="Enable verbose logging",
)


def main() -> None:
    """Main CLI entry point."""
    args = parser.parse_args()

    # Now import the platform-specific CLI
    # This ensures only one platform's libraries are loaded
    if args.platform == "daily":
        from benchmark_runner.platforms.daily_cli import run_daily_benchmark

        run_daily_benchmark(args)
    elif args.platform == "livekit":
        from benchmark_runner.platforms.livekit_cli import run_livekit_benchmark

        run_livekit_benchmark(args)
    else:
        print(f"Unknown platform: {args.platform}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
