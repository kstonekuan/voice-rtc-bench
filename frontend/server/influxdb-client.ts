/**
 * Amazon Timestream for InfluxDB 3 client for querying benchmark results.
 * Uses validated parameters to prevent SQL injection.
 */

import { InfluxDBClient } from "@influxdata/influxdb3-client";
import type { LocationId, MetricName, Platform } from "./validation";
import { VALID_METRIC_NAMES } from "./validation";

export interface InfluxDBConfig {
	url: string;
	token: string;
	org: string;
	database: string;
}

/**
 * Safely escape SQL string values.
 * Prevents SQL injection by escaping single quotes.
 */
function escapeSQLString(value: string): string {
	return value.replace(/'/g, "''");
}

/**
 * Safely validate and use SQL identifier (column/table names).
 * Only allows alphanumeric and underscore characters.
 */
function validateSQLIdentifier(identifier: string): string {
	if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(identifier)) {
		throw new Error(`Invalid SQL identifier: ${identifier}`);
	}
	return identifier;
}

export interface AggregatedMetric {
	platform: string;
	location_id: string;
	metric_name: string;
	avg_value: number;
	min_value: number;
	max_value: number;
	sample_count: number;
	time_period: string;
}

export interface TimeSeriesDataPoint {
	platform: string;
	location_id: string;
	metric_name: string;
	value: number;
	timestamp: string;
}

export class InfluxDBClientWrapper {
	private client: InfluxDBClient;
	private database: string;

	constructor(config: InfluxDBConfig) {
		this.client = new InfluxDBClient({
			host: config.url,
			token: config.token,
			database: config.database,
		});
		this.database = config.database;
	}

	/**
	 * Query aggregated statistics over a time period.
	 * Parameters are validated to prevent SQL injection.
	 * Runs all metric queries in parallel for better performance.
	 */
	async queryAggregatedStats(params: {
		platform?: Platform;
		location_id?: LocationId;
		hours_ago?: number;
	}): Promise<AggregatedMetric[]> {
		const { platform, location_id, hours_ago = 24 } = params;

		// Use validated metrics from the allowlist
		const metrics: readonly MetricName[] = [
			"mean_rtt",
			"median_rtt",
			"p50_rtt",
			"p95_rtt",
			"p99_rtt",
			"min_rtt",
			"max_rtt",
			"jitter",
			"packet_loss_rate",
		];

		// Build query function for a single metric
		const queryMetric = async (
			metric: MetricName,
		): Promise<AggregatedMetric[]> => {
			const results: AggregatedMetric[] = [];

			// Validate metric name against allowlist
			const safeMetric = validateSQLIdentifier(metric);

			// Build query with safe parameter interpolation
			// Aggregate all data within the time range into a single value per platform/location
			let query = `
        SELECT
          platform,
          location_id,
          '${escapeSQLString(metric)}' as metric_name,
          AVG(${safeMetric}) as avg_value,
          MIN(${safeMetric}) as min_value,
          MAX(${safeMetric}) as max_value,
          COUNT(${safeMetric}) as sample_count,
          MAX(time) as time_period
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '${Number(hours_ago)} hours'
          AND ${safeMetric} IS NOT NULL
      `;

			// Add optional filters with escaped values
			if (platform) {
				query += ` AND platform = '${escapeSQLString(platform)}'`;
			}

			if (location_id) {
				query += ` AND location_id = '${escapeSQLString(location_id)}'`;
			}

			query += " GROUP BY platform, location_id";
			query += " ORDER BY platform, location_id";

			try {
				const records = await this.client.query(query, this.database, {
					type: "sql",
				});

				for await (const record of records) {
					results.push({
						platform: String(record.platform || "unknown"),
						location_id: String(record.location_id || "unknown"),
						metric_name: metric,
						avg_value: Number(record.avg_value) || 0,
						min_value: Number(record.min_value) || 0,
						max_value: Number(record.max_value) || 0,
						sample_count: Number.parseInt(
							String(record.sample_count || "0"),
							10,
						),
						time_period: String(record.time_period || ""),
					});
				}
			} catch (error) {
				console.error(`Failed to query aggregated stats for ${metric}:`, error);
			}

			return results;
		};

		// Run all metric queries in parallel
		const allResults = await Promise.all(metrics.map((m) => queryMetric(m)));

		// Flatten results from all queries
		return allResults.flat();
	}

	/**
	 * Query time-series data for charting.
	 * Parameters are validated to prevent SQL injection.
	 */
	async queryTimeSeries(params: {
		platform?: Platform;
		location_id?: LocationId;
		metric_name: MetricName;
		hours_ago?: number;
	}): Promise<TimeSeriesDataPoint[]> {
		const { platform, location_id, metric_name, hours_ago = 24 } = params;

		// Validate metric name against allowlist
		if (!VALID_METRIC_NAMES.includes(metric_name)) {
			throw new Error(`Invalid metric name: ${metric_name}`);
		}

		const safeMetric = validateSQLIdentifier(metric_name);

		let query = `
      SELECT
        platform,
        location_id,
        ${safeMetric} as value,
        time as timestamp
      FROM latency_measurements
      WHERE time >= now() - INTERVAL '${Number(hours_ago)} hours'
        AND ${safeMetric} IS NOT NULL
    `;

		// Add optional filters with escaped values
		if (platform) {
			query += ` AND platform = '${escapeSQLString(platform)}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${escapeSQLString(location_id)}'`;
		}

		query += " ORDER BY time DESC LIMIT 1000";

		const results: TimeSeriesDataPoint[] = [];

		try {
			const records = await this.client.query(query, this.database, {
				type: "sql",
			});

			for await (const record of records) {
				results.push({
					platform: String(record.platform || "unknown"),
					location_id: String(record.location_id || "unknown"),
					metric_name: metric_name,
					value: Number(record.value) || 0,
					timestamp: String(record.timestamp || ""),
				});
			}
		} catch (error) {
			console.error("Failed to query time series:", error);
		}

		return results;
	}

	/**
	 * Get list of unique locations from the data.
	 */
	async getLocations(): Promise<string[]> {
		const query = `
      SELECT DISTINCT location_id
      FROM latency_measurements
      WHERE time >= now() - INTERVAL '7 days'
      ORDER BY location_id
    `;

		const locations: string[] = [];

		try {
			const records = await this.client.query(query, this.database, {
				type: "sql",
			});

			for await (const record of records) {
				locations.push((record.location_id as string) || "unknown");
			}
		} catch (error) {
			console.error("Failed to query locations:", error);
		}

		return locations;
	}

	/**
	 * Get latest statistics for all locations and platforms.
	 * Uses validated metrics to prevent SQL injection.
	 */
	async getLatestStats(): Promise<AggregatedMetric[]> {
		const metrics: readonly MetricName[] = [
			"mean_rtt",
			"p95_rtt",
			"p99_rtt",
			"jitter",
			"packet_loss_rate",
		];

		const results: AggregatedMetric[] = [];

		for (const metric of metrics) {
			// Validate metric name against allowlist
			const safeMetric = validateSQLIdentifier(metric);

			const query = `
        SELECT
          platform,
          location_id,
          '${escapeSQLString(metric)}' as metric_name,
          ${safeMetric} as avg_value,
          ${safeMetric} as min_value,
          ${safeMetric} as max_value,
          1 as sample_count,
          time as time_period
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '1 hour'
          AND ${safeMetric} IS NOT NULL
        ORDER BY time DESC
        LIMIT 100
      `;

			try {
				const records = await this.client.query(query, this.database, {
					type: "sql",
				});

				for await (const record of records) {
					results.push({
						platform: String(record.platform || "unknown"),
						location_id: String(record.location_id || "unknown"),
						metric_name: metric,
						avg_value: Number(record.avg_value) || 0,
						min_value: Number(record.min_value) || 0,
						max_value: Number(record.max_value) || 0,
						sample_count: 1,
						time_period: String(record.time_period || ""),
					});
				}
			} catch (error) {
				console.error(`Failed to query latest stats for ${metric}:`, error);
			}
		}

		return results;
	}

	/**
	 * Close the InfluxDB client connection.
	 */
	async close(): Promise<void> {
		await this.client.close();
	}
}
