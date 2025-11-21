#!/usr/bin/env python3
"""
Echo Agent - Platform-specific entry point.

Supports Daily or LiveKit platforms with completely separate implementations
to avoid library conflicts.
"""

import argparse
import asyncio
import sys

# Parse CLI arguments BEFORE any platform imports
parser = argparse.ArgumentParser(description="Echo Agent for Daily or LiveKit")
parser.add_argument(
    "--platform",
    choices=["daily", "livekit"],
    required=True,
    help="Platform to run (daily or livekit)",
)
parser.add_argument(
    "--port",
    type=int,
    default=None,
    help="API server port (default: 8000 for daily, 8001 for livekit)",
)
parser.add_argument(
    "--host",
    type=str,
    default="0.0.0.0",
    help="API server host (default: 0.0.0.0)",
)
args = parser.parse_args()

# Set default port based on platform if not specified
if args.port is None:
    args.port = 8000 if args.platform == "daily" else 8001

# Now import the platform-specific handler
# This ensures only one platform's libraries are loaded
if args.platform == "daily":
    from echo_agent.platforms.daily_platform import get_handler
elif args.platform == "livekit":
    from echo_agent.platforms.livekit_platform import get_handler
else:
    print(f"Unknown platform: {args.platform}", file=sys.stderr)
    sys.exit(1)


async def main() -> None:
    """Main entry point."""
    try:
        # Get platform-specific handler
        handler = get_handler()

        # Run the handler
        await handler.run(host=args.host, port=args.port)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


def run_cli() -> None:
    """Synchronous entry point for CLI script."""
    asyncio.run(main())


if __name__ == "__main__":
    run_cli()
