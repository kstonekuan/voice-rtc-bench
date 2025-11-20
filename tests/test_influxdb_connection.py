#!/usr/bin/env python3
"""
Test script to verify InfluxDB connection using settings from .env file.
"""

import sys
from pathlib import Path

# Add workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from shared.settings import BenchmarkRunnerSettings  # noqa: E402


def test_influxdb_connection() -> bool:
    """Test InfluxDB connection and basic operations."""
    print("=" * 70)
    print("Testing InfluxDB Connection")
    print("=" * 70)

    # Load settings from .env
    try:
        settings = BenchmarkRunnerSettings()
        print("\n✅ Settings loaded successfully")
        print(f"   URL: {settings.influxdb.influxdb_url}")
        print(f"   Database: {settings.influxdb.influxdb_database}")
        print(f"   Organization: {settings.influxdb.influxdb_org}")
    except Exception as e:
        print(f"\n❌ Failed to load settings: {e}")
        return False

    # Import and create InfluxDB client
    try:
        from benchmark_runner.influxdb import InfluxDBClientWrapper

        client = InfluxDBClientWrapper(
            url=settings.influxdb.influxdb_url,
            token=settings.influxdb.influxdb_token,
            org=settings.influxdb.influxdb_org,
            database=settings.influxdb.influxdb_database,
        )
        print("\n✅ InfluxDB client created")
    except Exception as e:
        print(f"\n❌ Failed to create InfluxDB client: {e}")
        return False

    # Test 1: Try to query recent results (should work even if empty)
    print("\n" + "-" * 70)
    print("Test 1: Query recent results")
    print("-" * 70)
    try:
        results = client.query_results(hours_ago=24, limit=10)
        print("✅ Query successful!")
        if results:
            print(f"   Found {len(results)} result(s) in last 24 hours")
            # Show unique locations and platforms
            platforms = {str(r.get("platform")) for r in results if r.get("platform")}
            locations = {str(r.get("location_id")) for r in results if r.get("location_id")}
            if platforms:
                print(f"   Platforms: {', '.join(platforms)}")
            if locations:
                print(f"   Locations: {', '.join(locations)}")
        else:
            print("   No results found (database might be empty)")
    except Exception as e:
        print(f"❌ Failed to query results: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 2: Try to query aggregated stats
    print("\n" + "-" * 70)
    print("Test 2: Query aggregated statistics")
    print("-" * 70)
    try:
        stats = client.query_aggregated_stats(hours_ago=24)
        print("✅ Query successful!")
        if stats:
            print(f"   Found aggregated stats for {len(stats)} metric(s)")
            for metric_name, values in list(stats.items())[:3]:
                print(
                    f"   - {metric_name}: avg={values['avg']:.2f}ms, "
                    f"min={values['min']:.2f}ms, max={values['max']:.2f}ms, "
                    f"samples={values['sample_count']}"
                )
            if len(stats) > 3:
                print(f"   ... and {len(stats) - 3} more metrics")
        else:
            print("   No statistics found (database might be empty)")
    except Exception as e:
        print(f"❌ Failed to query statistics: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 3: Try to write a test point
    print("\n" + "-" * 70)
    print("Test 3: Write test data point")
    print("-" * 70)
    try:
        # Create a minimal test result
        import time

        from benchmark_runner.types import BenchmarkMetadata, BenchmarkResult, BenchmarkStatistics

        now = time.time()
        test_result = BenchmarkResult(
            platform="daily",
            metadata=BenchmarkMetadata(
                platform="daily",
                location_id=settings.location_id or "test-location",
                iterations=1,
                timeout_ms=5000,
                start_time=now,
                end_time=now,
                duration_ms=0.0,
            ),
            statistics=BenchmarkStatistics(
                total_messages=1,
                successful_messages=1,
                failed_messages=0,
                packet_loss_rate=0.0,
                mean_rtt=50.0,
                median_rtt=50.0,
                min_rtt=50.0,
                max_rtt=50.0,
                std_dev_rtt=0.0,
                p50_rtt=50.0,
                p95_rtt=50.0,
                p99_rtt=50.0,
                jitter=0.0,
            ),
            measurements=[],
        )

        success = client.write_benchmark_result(test_result)
        if success:
            print("✅ Test data written successfully!")
            print("   Test point written with:")
            print(f"   - Platform: {test_result.platform}")
            print(f"   - Location: {test_result.metadata.location_id}")
            print(f"   - Mean RTT: {test_result.statistics.mean_rtt}ms")
        else:
            print("❌ Failed to write test data")
            return False
    except Exception as e:
        print(f"❌ Failed to write test data: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 4: Verify the written data
    print("\n" + "-" * 70)
    print("Test 4: Verify written data")
    print("-" * 70)
    try:
        import time

        time.sleep(2)  # Wait a moment for data to be indexed

        results = client.query_results(
            platform="daily",
            location_id=settings.location_id or "test-location",
            hours_ago=1,
            limit=10,
        )
        if results:
            print("✅ Verification successful!")
            print(f"   Found {len(results)} data point(s) from test location")
        else:
            print("⚠️  Could not find test data (might take a moment to index)")
    except Exception as e:
        print(f"⚠️  Verification check failed: {e}")
        import traceback

        traceback.print_exc()

    # Close connection
    try:
        client.close()
        print("\n✅ Connection closed")
    except Exception as e:
        print(f"\n⚠️  Warning during close: {e}")

    return True


if __name__ == "__main__":
    print()
    success = test_influxdb_connection()
    print("\n" + "=" * 70)
    if success:
        print("🎉 All tests passed! InfluxDB is configured correctly.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("❌ Tests failed. Please check your configuration.")
        print("=" * 70)
        sys.exit(1)
