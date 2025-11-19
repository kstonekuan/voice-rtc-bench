"""
CLI interface for the benchmark runner.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from .runners import DailyBenchmarkRunner, LiveKitBenchmarkRunner
from .stats import format_statistics
from .timestream import TimestreamClient
from .types import BenchmarkConfig

app = typer.Typer(
    name="benchmark-runner",
    help="Run WebRTC latency benchmarks for Daily and LiveKit platforms",
    add_completion=False,
)
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


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
    setup_logging(verbose)

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
    setup_logging(verbose)

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
    daily_room_url: str = typer.Option(..., "--daily-room", help="Daily room URL"),
    livekit_url: str = typer.Option(..., "--livekit-url", help="LiveKit server URL"),
    livekit_token: str = typer.Option(..., "--livekit-token", help="LiveKit access token"),
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
    """Run benchmarks on both Daily and LiveKit platforms in parallel."""
    setup_logging(verbose)

    timestream = create_timestream_client(timestream_database, timestream_table, timestream_region)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run_both():
        daily_runner = DailyBenchmarkRunner(daily_room_url)
        livekit_runner = LiveKitBenchmarkRunner(livekit_url, livekit_token)

        try:
            # Connect both
            await asyncio.gather(
                daily_runner.connect(),
                livekit_runner.connect(),
            )

            # Run benchmarks in parallel
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
