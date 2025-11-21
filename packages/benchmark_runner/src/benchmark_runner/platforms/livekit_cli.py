"""LiveKit platform-specific CLI implementation."""

import asyncio
import sys
from argparse import Namespace
from pathlib import Path

from rich.console import Console
from shared.settings import BenchmarkRunnerSettings
from shared.utils import setup_logging

from benchmark_runner.echo_agent_client import EchoAgentClient, get_room_credentials
from benchmark_runner.influxdb import InfluxDBClientWrapper
from benchmark_runner.runners.livekit import LiveKitBenchmarkRunner
from benchmark_runner.stats import format_statistics
from benchmark_runner.types import BenchmarkConfig

console = Console()


def run_livekit_benchmark(args: Namespace) -> None:
    """Run benchmark on LiveKit platform."""
    # Load settings
    settings = BenchmarkRunnerSettings()

    # Configure logging
    level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(level=level)

    # Use args or settings defaults
    iterations = args.iterations or settings.iterations
    timeout = args.timeout or settings.timeout_ms
    cooldown = args.cooldown or settings.cooldown_ms
    location_id = args.location or settings.location_id
    agent_url = args.agent_url

    # InfluxDB configuration
    influxdb_url = settings.influxdb.influxdb_url
    influxdb_token = settings.influxdb.influxdb_token
    influxdb_org = settings.influxdb.influxdb_org
    influxdb_database = settings.influxdb.influxdb_database

    influxdb = None
    if influxdb_url and influxdb_token and influxdb_database:
        influxdb = InfluxDBClientWrapper(
            url=influxdb_url,
            token=influxdb_token,
            org=influxdb_org,
            database=influxdb_database,
        )

    config = BenchmarkConfig(
        iterations=iterations,
        timeout_ms=timeout,
        cooldown_ms=cooldown,
        location_id=location_id,
    )

    async def run() -> None:
        # Request room credentials from echo agent
        console.print(f"🔗 Requesting LiveKit credentials from: {agent_url}")

        try:
            creds = await get_room_credentials(agent_url)
        except Exception as e:
            console.print(f"❌ Failed to get room credentials: {e}")
            raise

        if creds.livekit is None:
            console.print("❌ Missing LiveKit credentials from LiveKit agent")
            raise ValueError("LiveKit credentials required")

        console.print(f"✅ Received credentials for room: {creds.livekit.room_name}")

        # Create echo agent client for cleanup
        agent_client = EchoAgentClient(agent_url)

        # Create runner
        runner = LiveKitBenchmarkRunner(
            creds.livekit.server_url,
            creds.livekit.token,
        )

        try:
            console.print("📞 Connecting to room...")
            await runner.connect()

            console.print(f"🏁 Running benchmark ({config.iterations} iterations)...")
            result = await runner.run_benchmark(config)

            # Display results
            console.print("\n" + "=" * 60)
            console.print("📊 LIVEKIT RESULTS")
            console.print("=" * 60)
            console.print(format_statistics(result.statistics))

            # Save to file if requested
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(result.model_dump_json(indent=2))
                console.print(f"\n💾 Results saved to: {output_path}")

            # Write to InfluxDB if configured
            if influxdb and influxdb.write_benchmark_result(result):
                console.print("💾 Results written to InfluxDB")

        finally:
            await runner.disconnect()

            # Request echo agent to disconnect and clean up
            console.print("🔌 Requesting echo agent disconnect...")
            try:
                await agent_client.disconnect_room(creds.room_id)
            except Exception as e:
                console.print(f"⚠️  Failed to disconnect echo agent: {e}")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n\n🛑 Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n❌ Error: {e}")
        if args.verbose:
            console.print_exception()
        sys.exit(1)
