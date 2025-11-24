"""
Amazon Timestream for InfluxDB 3 integration for storing and querying benchmark results.
"""

from datetime import datetime
from typing import Any

from influxdb_client_3 import InfluxDBClient3, Point
from loguru import logger

from .types import BenchmarkResult, BenchmarkStatistics


class InfluxDBClientWrapper:
    """Client for interacting with Amazon Timestream for InfluxDB 3."""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        database: str,
    ) -> None:
        """
        Initialize InfluxDB 3 client.

        Args:
            url: InfluxDB endpoint URL
            token: Authentication token
            org: Organization name
            database: Database/bucket name
        """
        self.database = database
        self.client = InfluxDBClient3(
            host=url,
            token=token,
            org=org,
            database=database,
        )

    def write_benchmark_result(self, result: BenchmarkResult) -> bool:
        """
        Write benchmark result to InfluxDB.
        Writes both individual measurements and a run summary with packet loss stats.

        Args:
            result: BenchmarkResult to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create points for individual measurements
            measurement_points = self._create_points_from_measurements(
                result.measurements,
                platform=result.platform,
                location_id=result.metadata.location_id or "unknown",
                run_id=result.metadata.run_id,
            )

            # Create a single summary point for this run with aggregated stats
            summary_point = self._create_run_summary_point(
                result.statistics,
                platform=result.platform,
                location_id=result.metadata.location_id or "unknown",
                run_id=result.metadata.run_id,
                timestamp=datetime.fromtimestamp(result.metadata.end_time),
            )

            # Batch write all points in a single operation
            all_points = measurement_points + [summary_point]
            self.client.write(all_points)

            logger.info(
                f"✅ Wrote {len(measurement_points)} measurements + 1 run summary to InfluxDB with run_id={result.metadata.run_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to write to InfluxDB: {e}", exc_info=True)
            return False

    def _create_points_from_measurements(
        self,
        measurements: list,
        platform: str,
        location_id: str,
        run_id: str,
    ) -> list[Point]:
        """
        Create InfluxDB points from raw measurements.

        Args:
            measurements: List of LatencyMeasurement objects
            platform: Platform name (daily/livekit)
            location_id: Location identifier
            run_id: Unique identifier for this benchmark run

        Returns:
            List of InfluxDB Point objects (one per measurement)
        """
        points = []

        # Create one point per measurement, all tagged with the same run_id
        for measurement in measurements:
            # Use the measurement's timestamp for time-series accuracy
            # Convert from milliseconds to datetime
            timestamp = datetime.fromtimestamp(measurement.timestamp / 1000)

            point = (
                Point("latency_measurements")
                .tag("platform", platform)
                .tag("location_id", location_id)
                .tag("run_id", run_id)
                .field("round_trip_time", measurement.round_trip_time)
                .field("client_to_server", measurement.client_to_server)
                .field("server_to_client", measurement.server_to_client)
                .field("message_number", measurement.message_number)
                .time(timestamp)
            )
            points.append(point)

        return points

    def _create_run_summary_point(
        self,
        stats: BenchmarkStatistics,
        platform: str,
        location_id: str,
        run_id: str,
        timestamp: datetime,
    ) -> Point:
        """
        Create a single summary point for a benchmark run.
        Contains aggregated statistics including packet loss rate.

        Args:
            stats: BenchmarkStatistics object
            platform: Platform name (daily/livekit)
            location_id: Location identifier
            run_id: Unique identifier for this benchmark run
            timestamp: Timestamp for the summary point

        Returns:
            InfluxDB Point object with run summary
        """
        return (
            Point("run_summary")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .tag("run_id", run_id)
            .field("total_messages", stats.total_messages)
            .field("successful_messages", stats.successful_messages)
            .field("failed_messages", stats.failed_messages)
            .field("packet_loss_rate", stats.packet_loss_rate)
            .time(timestamp)
        )

    def query_results(
        self,
        platform: str | None = None,
        location_id: str | None = None,
        hours_ago: int = 24,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query benchmark results from InfluxDB.

        Args:
            platform: Filter by platform (daily/livekit)
            location_id: Filter by location
            hours_ago: How many hours back to query (default: 24)
            limit: Maximum number of results (default: 1000)

        Returns:
            List of result dictionaries
        """
        # Build SQL query for InfluxDB 3
        query = f"""
        SELECT *
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '{hours_ago} hours'
        """

        if platform:
            query += f" AND platform = '{platform}'"

        if location_id:
            query += f" AND location_id = '{location_id}'"

        query += f" ORDER BY time DESC LIMIT {limit}"

        try:
            # Execute query and get results as pandas DataFrame
            table = self.client.query(query=query)

            # Convert to list of dictionaries
            results = []
            if table is not None and len(table) > 0:
                # Convert pyarrow table to pandas for easier manipulation
                df = table.to_pandas()
                results = df.to_dict("records")

            logger.info(f"✅ Retrieved {len(results)} records from InfluxDB")
            return results

        except Exception as e:
            logger.error("Failed to query InfluxDB: {}", str(e))
            return []

    def query_aggregated_stats(
        self,
        platform: str | None = None,
        location_id: str | None = None,
        hours_ago: int = 24,
    ) -> dict[str, Any]:
        """
        Query aggregated statistics over time period.

        Args:
            platform: Filter by platform (daily/livekit)
            location_id: Filter by location
            hours_ago: How many hours back to query (default: 24)

        Returns:
            Dictionary with aggregated statistics
        """
        # Define metrics to aggregate
        metrics = [
            "mean_rtt",
            "median_rtt",
            "p50_rtt",
            "p95_rtt",
            "p99_rtt",
            "min_rtt",
            "max_rtt",
            "jitter",
            "packet_loss_rate",
        ]

        aggregated = {}

        for metric in metrics:
            query = f"""
            SELECT
                AVG({metric}) as avg_value,
                MIN({metric}) as min_value,
                MAX({metric}) as max_value,
                COUNT({metric}) as sample_count
            FROM latency_measurements
            WHERE time >= now() - INTERVAL '{hours_ago} hours'
                AND {metric} IS NOT NULL
            """

            if platform:
                query += f" AND platform = '{platform}'"

            if location_id:
                query += f" AND location_id = '{location_id}'"

            try:
                table = self.client.query(query=query)

                if table is not None and len(table) > 0:
                    df = table.to_pandas()
                    if len(df) > 0:
                        row = df.iloc[0]
                        aggregated[metric] = {
                            "avg": float(row["avg_value"]) if row["avg_value"] is not None else 0.0,
                            "min": float(row["min_value"]) if row["min_value"] is not None else 0.0,
                            "max": float(row["max_value"]) if row["max_value"] is not None else 0.0,
                            "sample_count": int(row["sample_count"])
                            if row["sample_count"] is not None
                            else 0,
                        }

            except Exception as e:
                logger.error(f"Failed to query aggregated stats for {metric}: {e}")
                continue

        logger.info(f"✅ Retrieved aggregated stats for {len(aggregated)} metrics")
        return aggregated

    def close(self) -> None:
        """Close the InfluxDB client connection."""
        try:
            self.client.close()
            logger.info("✅ Closed InfluxDB connection")
        except Exception as e:
            logger.error(f"Failed to close InfluxDB connection: {e}")
