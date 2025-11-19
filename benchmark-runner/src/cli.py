"""
CLI interface for the benchmark runner.
"""

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from shared.settings import BenchmarkRunnerSettings
from shared.utils import setup_logging

from .echo_agent_client import get_room_credentials
from .runners import DailyBenchmarkRunner, LiveKitBenchmarkRunner
from .stats import format_statistics
from .timestream import TimestreamClient
from .types import BenchmarkConfig

# Load settings from environment
settings = BenchmarkRunnerSettings()

app = typer.Typer(
    name="benchmark-runner",
    help="Run WebRTC latency benchmarks for Daily and LiveKit platforms",
    add_completion=False,
)
console = Console()


def configure_logging(verbose: bool = False) -> None:
    """Configure logging with rich handler."""
    level = "DEBUG" if verbose else settings.log_level
    setup_logging(level=level, use_rich=True)


def create_timestream_client(
    database: str | None,
    table: str | None,
    region: str | None,
) -> TimestreamClient | None:
    """Create Timestream client if credentials provided."""
    if database and table:
        return TimestreamClient(
            database_name=database,
            table_name=table,
            region_name=region or "us-east-1",
        )
    return None


@app.command()
def daily(
    room_url: str = typer.Option(..., "--room-url", "-r", help="Daily room URL"),
    iterations: int = typer.Option(100, "--iterations", "-n", help="Number of pings to send"),
    timeout: int = typer.Option(5000, "--timeout", "-t", help="Timeout in milliseconds"),
    cooldown: int = typer.Option(100, "--cooldown", "-c", help="Cooldown between pings (ms)"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location identifier"),
    output: Path = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
    timestream_database: str = typer.Option(None, "--ts-database", help="Timestream database"),
    timestream_table: str = typer.Option(None, "--ts-table", help="Timestream table"),
    timestream_region: str = typer.Option("us-east-1", "--ts-region", help="Timestream region"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Run benchmark on Daily platform."""
    configure_logging(verbose)

    timestream = create_timestream_client(timestream_database, timestream_table, timestream_region)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run():
        runner = DailyBenchmarkRunner(room_url)

        try:
            await runner.connect()
            result = await runner.run_benchmark(config)

            # Display results
            console.print(format_statistics(result.statistics))

            # Save to file if requested
            if output:
                output.write_text(result.model_dump_json(indent=2))
                console.print(f"\n💾 Results saved to: {output}")

            # Write to Timestream if configured
            if timestream:
                if timestream.write_benchmark_result(result):
                    console.print("💾 Results written to Timestream")

            return result

        finally:
            await runner.disconnect()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n\n🛑 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n❌ Error: {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@app.command()
def livekit(
    server_url: str = typer.Option(..., "--server-url", "-s", help="LiveKit server URL"),
    token: str = typer.Option(..., "--token", "-t", help="LiveKit access token"),
    iterations: int = typer.Option(100, "--iterations", "-n", help="Number of pings to send"),
    timeout: int = typer.Option(5000, "--timeout", help="Timeout in milliseconds"),
    cooldown: int = typer.Option(100, "--cooldown", "-c", help="Cooldown between pings (ms)"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location identifier"),
    output: Path = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
    timestream_database: str = typer.Option(None, "--ts-database", help="Timestream database"),
    timestream_table: str = typer.Option(None, "--ts-table", help="Timestream table"),
    timestream_region: str = typer.Option("us-east-1", "--ts-region", help="Timestream region"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Run benchmark on LiveKit platform."""
    configure_logging(verbose)

    timestream = create_timestream_client(timestream_database, timestream_table, timestream_region)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run():
        runner = LiveKitBenchmarkRunner(server_url, token)

        try:
            await runner.connect()
            result = await runner.run_benchmark(config)

            # Display results
            console.print(format_statistics(result.statistics))

            # Save to file if requested
            if output:
                output.write_text(result.model_dump_json(indent=2))
                console.print(f"\n💾 Results saved to: {output}")

            # Write to Timestream if configured
            if timestream:
                if timestream.write_benchmark_result(result):
                    console.print("💾 Results written to Timestream")

            return result

        finally:
            await runner.disconnect()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n\n🛑 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n❌ Error: {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@app.command()
def both(
    echo_agent_url: str = typer.Option(
        None,
        "--echo-agent-url",
        "-u",
        help="Echo agent API URL (defaults to ECHO_AGENT_URL env var)",
    ),
    iterations: int = typer.Option(None, "--iterations", "-n", help="Number of pings to send"),
    timeout: int = typer.Option(None, "--timeout", "-t", help="Timeout in milliseconds"),
    cooldown: int = typer.Option(None, "--cooldown", "-c", help="Cooldown between pings (ms)"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location identifier"),
    output: Path = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
    timestream_database: str = typer.Option(None, "--ts-database", help="Timestream database"),
    timestream_table: str = typer.Option(None, "--ts-table", help="Timestream table"),
    timestream_region: str = typer.Option(None, "--ts-region", help="Timestream region"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """
    Run benchmarks on both Daily and LiveKit platforms in parallel.

    This command requests room credentials from the echo agent API and then
    runs benchmarks on both platforms simultaneously.
    """
    configure_logging(verbose)

    # Use settings for defaults
    echo_agent_url = echo_agent_url or settings.echo_agent_url
    iterations = iterations or settings.iterations
    timeout = timeout or settings.timeout_ms
    cooldown = cooldown or settings.cooldown_ms
    location_id = location_id or settings.location_id
    timestream_database = timestream_database or settings.timestream.timestream_database
    timestream_table = timestream_table or settings.timestream.timestream_table
    timestream_region = timestream_region or settings.timestream.aws_region

    timestream = create_timestream_client(timestream_database, timestream_table, timestream_region)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run_both():
        # Request room credentials from echo agent
        console.print(f"🔗 Requesting room credentials from echo agent: {echo_agent_url}")
        try:
            credentials = await get_room_credentials(echo_agent_url)
        except Exception as e:
            console.print(f"❌ Failed to get room credentials: {e}")
            raise

        console.print("✅ Received credentials:")
        console.print(f"   Daily room: {credentials.daily.room_url}")
        console.print(f"   LiveKit room: {credentials.livekit.room_name}")
        console.print()

        # Create runners with credentials from API
        daily_runner = DailyBenchmarkRunner(credentials.daily.room_url)
        livekit_runner = LiveKitBenchmarkRunner(
            credentials.livekit.server_url,
            credentials.livekit.token,
        )

        try:
            # Connect both
            console.print("📞 Connecting to rooms...")
            await asyncio.gather(
                daily_runner.connect(),
                livekit_runner.connect(),
            )

            # Run benchmarks in parallel
            console.print(f"🏁 Running benchmarks ({config.iterations} iterations)...")
            daily_result, livekit_result = await asyncio.gather(
                daily_runner.run_benchmark(config),
                livekit_runner.run_benchmark(config),
            )

            # Display results
            console.print("\n" + "=" * 60)
            console.print("📊 DAILY RESULTS")
            console.print("=" * 60)
            console.print(format_statistics(daily_result.statistics))

            console.print("\n" + "=" * 60)
            console.print("📊 LIVEKIT RESULTS")
            console.print("=" * 60)
            console.print(format_statistics(livekit_result.statistics))

            # Save to file if requested
            if output:
                combined_results = {
                    "daily": daily_result.model_dump(),
                    "livekit": livekit_result.model_dump(),
                }
                output.write_text(json.dumps(combined_results, indent=2))
                console.print(f"\n💾 Results saved to: {output}")

            # Write to Timestream if configured
            if timestream:
                if timestream.write_benchmark_result(daily_result):
                    console.print("💾 Daily results written to Timestream")
                if timestream.write_benchmark_result(livekit_result):
                    console.print("💾 LiveKit results written to Timestream")

            return daily_result, livekit_result

        finally:
            # Disconnect both
            await asyncio.gather(
                daily_runner.disconnect(),
                livekit_runner.disconnect(),
            )

    try:
        asyncio.run(run_both())
    except KeyboardInterrupt:
        console.print("\n\n🛑 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n❌ Error: {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
