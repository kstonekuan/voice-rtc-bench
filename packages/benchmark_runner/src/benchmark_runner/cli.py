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

from .echo_agent_client import EchoAgentClient, get_room_credentials
from .influxdb import InfluxDBClientWrapper
from .runners import DailyBenchmarkRunner, LiveKitBenchmarkRunner
from .stats import format_statistics
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


def create_influxdb_client(
    url: str | None,
    token: str | None,
    org: str | None,
    database: str | None,
) -> InfluxDBClientWrapper | None:
    """Create InfluxDB client if credentials provided."""
    if url and token and database:
        return InfluxDBClientWrapper(
            url=url,
            token=token,
            org=org or "default",
            database=database,
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
    influxdb_url: str = typer.Option(None, "--influxdb-url", help="InfluxDB endpoint URL"),
    influxdb_token: str = typer.Option(None, "--influxdb-token", help="InfluxDB auth token"),
    influxdb_org: str = typer.Option(None, "--influxdb-org", help="InfluxDB organization"),
    influxdb_database: str = typer.Option(None, "--influxdb-database", help="InfluxDB database"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Run benchmark on Daily platform."""
    configure_logging(verbose)

    influxdb = create_influxdb_client(influxdb_url, influxdb_token, influxdb_org, influxdb_database)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run() -> None:
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

            # Write to InfluxDB if configured
            if influxdb and influxdb.write_benchmark_result(result):
                console.print("💾 Results written to InfluxDB")

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
    influxdb_url: str = typer.Option(None, "--influxdb-url", help="InfluxDB endpoint URL"),
    influxdb_token: str = typer.Option(None, "--influxdb-token", help="InfluxDB auth token"),
    influxdb_org: str = typer.Option(None, "--influxdb-org", help="InfluxDB organization"),
    influxdb_database: str = typer.Option(None, "--influxdb-database", help="InfluxDB database"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Run benchmark on LiveKit platform."""
    configure_logging(verbose)

    influxdb = create_influxdb_client(influxdb_url, influxdb_token, influxdb_org, influxdb_database)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run() -> None:
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

            # Write to InfluxDB if configured
            if influxdb and influxdb.write_benchmark_result(result):
                console.print("💾 Results written to InfluxDB")

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
    daily_agent_url: str = typer.Option(
        None,
        "--daily-agent-url",
        help="Daily agent API URL (defaults to DAILY_AGENT_URL env var)",
    ),
    livekit_agent_url: str = typer.Option(
        None,
        "--livekit-agent-url",
        help="LiveKit agent API URL (defaults to LIVEKIT_AGENT_URL env var)",
    ),
    iterations: int = typer.Option(None, "--iterations", "-n", help="Number of pings to send"),
    timeout: int = typer.Option(None, "--timeout", "-t", help="Timeout in milliseconds"),
    cooldown: int = typer.Option(None, "--cooldown", "-c", help="Cooldown between pings (ms)"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location identifier"),
    output: Path = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
    influxdb_url: str = typer.Option(None, "--influxdb-url", help="InfluxDB endpoint URL"),
    influxdb_token: str = typer.Option(None, "--influxdb-token", help="InfluxDB auth token"),
    influxdb_org: str = typer.Option(None, "--influxdb-org", help="InfluxDB organization"),
    influxdb_database: str = typer.Option(None, "--influxdb-database", help="InfluxDB database"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """
    Run benchmarks on both Daily and LiveKit platforms in parallel.

    This command requests room credentials from the separate echo agent APIs and then
    runs benchmarks on both platforms simultaneously.
    """
    configure_logging(verbose)

    # Use settings for defaults
    daily_agent_url = daily_agent_url or settings.daily_agent_url
    livekit_agent_url = livekit_agent_url or settings.livekit_agent_url
    iterations = iterations or settings.iterations
    timeout = timeout or settings.timeout_ms
    cooldown = cooldown or settings.cooldown_ms
    location_id = location_id or settings.location_id
    influxdb_url = influxdb_url or settings.influxdb.influxdb_url
    influxdb_token = influxdb_token or settings.influxdb.influxdb_token
    influxdb_org = influxdb_org or settings.influxdb.influxdb_org
    influxdb_database = influxdb_database or settings.influxdb.influxdb_database

    if not daily_agent_url:
        console.print("❌ Missing Daily agent URL. Set DAILY_AGENT_URL or use --daily-agent-url")
        sys.exit(1)

    if not livekit_agent_url:
        console.print(
            "❌ Missing LiveKit agent URL. Set LIVEKIT_AGENT_URL or use --livekit-agent-url"
        )
        sys.exit(1)

    influxdb = create_influxdb_client(influxdb_url, influxdb_token, influxdb_org, influxdb_database)

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run_both() -> None:
        # Request room credentials from echo agents
        console.print(f"🔗 Requesting Daily credentials from: {daily_agent_url}")
        console.print(f"🔗 Requesting LiveKit credentials from: {livekit_agent_url}")

        try:
            daily_creds, livekit_creds = await asyncio.gather(
                get_room_credentials(daily_agent_url), get_room_credentials(livekit_agent_url)
            )
        except Exception as e:
            console.print(f"❌ Failed to get room credentials: {e}")
            raise

        console.print("✅ Received credentials:")

        if daily_creds.daily is None:
            console.print("❌ Missing Daily credentials from Daily agent")
            raise ValueError("Daily credentials required")

        if livekit_creds.livekit is None:
            console.print("❌ Missing LiveKit credentials from LiveKit agent")
            raise ValueError("LiveKit credentials required")

        console.print(f"   Daily room: {daily_creds.daily.room_url}")
        console.print(f"   LiveKit room: {livekit_creds.livekit.room_name}")
        console.print()

        # Create echo agent clients for cleanup
        daily_agent_client = EchoAgentClient(daily_agent_url)
        livekit_agent_client = EchoAgentClient(livekit_agent_url)

        # Create runners with credentials from API
        daily_runner = DailyBenchmarkRunner(daily_creds.daily.room_url)
        livekit_runner = LiveKitBenchmarkRunner(
            livekit_creds.livekit.server_url,
            livekit_creds.livekit.token,
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

            # Write to InfluxDB if configured
            if influxdb:
                if influxdb.write_benchmark_result(daily_result):
                    console.print("💾 Daily results written to InfluxDB")
                if influxdb.write_benchmark_result(livekit_result):
                    console.print("💾 LiveKit results written to InfluxDB")

        finally:
            # Disconnect both runners
            await asyncio.gather(
                daily_runner.disconnect(),
                livekit_runner.disconnect(),
            )

            # Request echo agent to disconnect and clean up
            console.print("🔌 Requesting echo agents disconnect...")
            try:
                await asyncio.gather(
                    daily_agent_client.disconnect_room(daily_creds.room_id),
                    livekit_agent_client.disconnect_room(livekit_creds.room_id),
                )
            except Exception as e:
                console.print(f"⚠️  Failed to disconnect echo agent: {e}")

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
