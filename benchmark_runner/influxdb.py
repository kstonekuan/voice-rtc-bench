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
    ):
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

        Args:
            result: BenchmarkResult to store

        Returns:
            True if successful, False otherwise
        """
        try:
            points = self._create_points_from_statistics(
                result.statistics,
                platform=result.platform,
                location_id=result.metadata.location_id or "unknown",
            )

            # Write all points
            for point in points:
                self.client.write(point)

            logger.info(f"✅ Wrote {len(points)} points to InfluxDB")
            return True

        except Exception as e:
            logger.error(f"Failed to write to InfluxDB: {e}", exc_info=True)
            return False

    def _create_points_from_statistics(
        self,
        stats: BenchmarkStatistics,
        platform: str,
        location_id: str,
    ) -> list[Point]:
        """
        Create InfluxDB points from statistics.

        Args:
            stats: BenchmarkStatistics to convert
            platform: Platform name (daily/livekit)
            location_id: Location identifier

        Returns:
            List of InfluxDB Point objects
        """
        # We'll create one point per metric to match the Timestream structure
        # Measurement: latency_measurements
        # Tags: platform, location_id
        # Fields: individual metrics
        points = []
        timestamp = datetime.now()

        # Message count metrics
        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("total_messages", stats.total_messages)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("successful_messages", stats.successful_messages)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("failed_messages", stats.failed_messages)
            .time(timestamp)
        )

        # RTT metrics
        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("mean_rtt", stats.mean_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("median_rtt", stats.median_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("min_rtt", stats.min_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("max_rtt", stats.max_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("std_dev_rtt", stats.std_dev_rtt)
            .time(timestamp)
        )

        # Percentiles
        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("p50_rtt", stats.p50_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("p95_rtt", stats.p95_rtt)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("p99_rtt", stats.p99_rtt)
            .time(timestamp)
        )

        # Jitter and packet loss
        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("jitter", stats.jitter)
            .time(timestamp)
        )

        points.append(
            Point("latency_measurements")
            .tag("platform", platform)
            .tag("location_id", location_id)
            .field("packet_loss_rate", stats.packet_loss_rate)
            .time(timestamp)
        )

        return points

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
