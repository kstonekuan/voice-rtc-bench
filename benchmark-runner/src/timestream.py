"""
Amazon Timestream integration for storing and querying benchmark results.
"""

from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError
from loguru import logger

from .types import BenchmarkResult, BenchmarkStatistics


class TimestreamClient:
    """Client for interacting with Amazon Timestream."""

    def __init__(
        self,
        database_name: str,
        table_name: str,
        region_name: str = "us-east-1",
    ):
        """
        Initialize Timestream client.

        Args:
            database_name: Timestream database name
            table_name: Timestream table name
            region_name: AWS region (default: us-east-1)
        """
        self.database_name = database_name
        self.table_name = table_name

        # Timestream Write client
        self.write_client = boto3.client(
            "timestream-write",
            region_name=region_name,
        )

        # Timestream Query client
        self.query_client = boto3.client(
            "timestream-query",
            region_name=region_name,
        )

    def write_benchmark_result(self, result: BenchmarkResult) -> bool:
        """
        Write benchmark result to Timestream.

        Args:
            result: BenchmarkResult to store

        Returns:
            True if successful, False otherwise
        """
        try:
            current_time = str(int(datetime.now().timestamp() * 1000))

            # Common dimensions
            dimensions = [
                {"Name": "platform", "Value": result.platform},
                {"Name": "location_id", "Value": result.metadata.location_id or "unknown"},
            ]

            # Create records for statistics
            records = self._create_statistics_records(
                result.statistics,
                dimensions,
                current_time,
            )

            # Write records
            self.write_client.write_records(
                DatabaseName=self.database_name,
                TableName=self.table_name,
                Records=records,
            )

            logger.info(f"✅ Wrote {len(records)} records to Timestream")
            return True

        except ClientError as e:
            logger.error(f"Failed to write to Timestream: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing to Timestream: {e}", exc_info=True)
            return False

    def _create_statistics_records(
        self,
        stats: BenchmarkStatistics,
        dimensions: list[dict[str, str]],
        timestamp: str,
    ) -> list[dict[str, Any]]:
        """
        Create Timestream records from statistics.

        Args:
            stats: BenchmarkStatistics to convert
            dimensions: Common dimensions for all records
            timestamp: Timestamp for the records

        Returns:
            List of Timestream record dictionaries
        """
        # Map of measure names to values
        measures = {
            "total_messages": stats.total_messages,
            "successful_messages": stats.successful_messages,
            "failed_messages": stats.failed_messages,
            "packet_loss_rate": stats.packet_loss_rate,
            "mean_rtt": stats.mean_rtt,
            "median_rtt": stats.median_rtt,
            "min_rtt": stats.min_rtt,
            "max_rtt": stats.max_rtt,
            "std_dev_rtt": stats.std_dev_rtt,
            "p50_rtt": stats.p50_rtt,
            "p95_rtt": stats.p95_rtt,
            "p99_rtt": stats.p99_rtt,
            "jitter": stats.jitter,
        }

        records = []

        for measure_name, measure_value in measures.items():
            # Determine measure value type
            if isinstance(measure_value, int):
                measure_value_type = "BIGINT"
                measure_value_str = str(measure_value)
            else:  # float
                measure_value_type = "DOUBLE"
                measure_value_str = str(measure_value)

            record = {
                "Dimensions": dimensions,
                "MeasureName": measure_name,
                "MeasureValue": measure_value_str,
                "MeasureValueType": measure_value_type,
                "Time": timestamp,
            }

            records.append(record)

        return records

    def query_results(
        self,
        platform: str | None = None,
        location_id: str | None = None,
        hours_ago: int = 24,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query benchmark results from Timestream.

        Args:
            platform: Filter by platform (daily/livekit)
            location_id: Filter by location
            hours_ago: How many hours back to query (default: 24)
            limit: Maximum number of results (default: 1000)

        Returns:
            List of result dictionaries
        """
        # Build query
        query = f"""
        SELECT
            platform,
            location_id,
            measure_name,
            measure_value::double as value,
            time
        FROM "{self.database_name}"."{self.table_name}"
        WHERE time >= ago({hours_ago}h)
        """

        if platform:
            query += f" AND platform = '{platform}'"

        if location_id:
            query += f" AND location_id = '{location_id}'"

        query += f" ORDER BY time DESC LIMIT {limit}"

        try:
            response = self.query_client.query(QueryString=query)

            # Parse results
            results = []
            for row in response.get("Rows", []):
                data = row.get("Data", [])
                if len(data) >= 4:
                    results.append(
                        {
                            "platform": data[0].get("ScalarValue"),
                            "location_id": data[1].get("ScalarValue"),
                            "measure_name": data[2].get("ScalarValue"),
                            "value": float(data[3].get("ScalarValue", 0)),
                            "time": data[4].get("ScalarValue") if len(data) > 4 else None,
                        }
                    )

            logger.info(f"✅ Retrieved {len(results)} records from Timestream")
            return results

        except ClientError as e:
            logger.error(f"Failed to query Timestream: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying Timestream: {e}", exc_info=True)
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
        # Build query for each metric
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

        query = f"""
        SELECT
            measure_name,
            AVG(measure_value::double) as avg_value,
            MIN(measure_value::double) as min_value,
            MAX(measure_value::double) as max_value,
            COUNT(*) as sample_count
        FROM "{self.database_name}"."{self.table_name}"
        WHERE time >= ago({hours_ago}h)
        """

        if platform:
            query += f" AND platform = '{platform}'"

        if location_id:
            query += f" AND location_id = '{location_id}'"

        # Only include numeric metrics
        metrics_filter = "', '".join(metrics)
        query += f" AND measure_name IN ('{metrics_filter}')"
        query += " GROUP BY measure_name"

        try:
            response = self.query_client.query(QueryString=query)

            # Parse results into dictionary
            aggregated = {}
            for row in response.get("Rows", []):
                data = row.get("Data", [])
                if len(data) >= 5:
                    measure_name = data[0].get("ScalarValue")
                    aggregated[measure_name] = {
                        "avg": float(data[1].get("ScalarValue", 0)),
                        "min": float(data[2].get("ScalarValue", 0)),
                        "max": float(data[3].get("ScalarValue", 0)),
                        "sample_count": int(data[4].get("ScalarValue", 0)),
                    }

            logger.info(f"✅ Retrieved aggregated stats for {len(aggregated)} metrics")
            return aggregated

        except ClientError as e:
            logger.error(f"Failed to query aggregated stats: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error querying stats: {e}", exc_info=True)
            return {}

    def create_database_and_table(self) -> bool:
        """
        Create Timestream database and table if they don't exist.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create database
            try:
                self.write_client.create_database(DatabaseName=self.database_name)
                logger.info(f"✅ Created Timestream database: {self.database_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    logger.info(f"Database {self.database_name} already exists")
                else:
                    raise

            # Create table
            try:
                self.write_client.create_table(
                    DatabaseName=self.database_name,
                    TableName=self.table_name,
                    RetentionProperties={
                        "MemoryStoreRetentionPeriodInHours": 24,  # Hot data: 24 hours
                        "MagneticStoreRetentionPeriodInDays": 90,  # Historical: 90 days
                    },
                )
                logger.info(f"✅ Created Timestream table: {self.table_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    logger.info(f"Table {self.table_name} already exists")
                else:
                    raise

            return True

        except ClientError as e:
            logger.error(f"Failed to create database/table: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating database/table: {e}", exc_info=True)
            return False
