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
	 * Calculates statistics from raw measurement data.
	 * Parameters are validated to prevent SQL injection.
	 */
	async queryAggregatedStats(params: {
		platform?: Platform;
		location_id?: LocationId;
		hours_ago?: number;
	}): Promise<AggregatedMetric[]> {
		const { platform, location_id, hours_ago = 24 } = params;

		// Build query with jitter and packet loss calculation
		// Jitter is calculated per run from measurements, then averaged
		// Packet loss is averaged from run_summary table
		let query = `
      WITH run_jitter AS (
        SELECT
          run_id,
          platform,
          location_id,
          AVG(ABS(round_trip_time - LAG(round_trip_time) OVER (PARTITION BY run_id ORDER BY time))) as run_jitter_value
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '${Number(hours_ago)} hours'
          AND round_trip_time IS NOT NULL
    `;

		// Add optional filters with escaped values
		if (platform) {
			query += ` AND platform = '${escapeSQLString(platform)}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${escapeSQLString(location_id)}'`;
		}

		query += `
        GROUP BY run_id, platform, location_id
      ),
      run_stats AS (
        SELECT
          platform,
          location_id,
          AVG(packet_loss_rate) as avg_packet_loss,
          SUM(total_messages) as total_messages_sum,
          SUM(successful_messages) as successful_messages_sum,
          SUM(failed_messages) as failed_messages_sum
        FROM run_summary
        WHERE time >= now() - INTERVAL '${Number(hours_ago)} hours'
    `;

		// Add optional filters for run_stats
		if (platform) {
			query += ` AND platform = '${escapeSQLString(platform)}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${escapeSQLString(location_id)}'`;
		}

		query += `
        GROUP BY platform, location_id
      )
      SELECT
        m.platform,
        m.location_id,
        AVG(m.round_trip_time) as mean_rtt,
        approx_percentile_cont(m.round_trip_time, 0.5) as median_rtt,
        approx_percentile_cont(m.round_trip_time, 0.5) as p50_rtt,
        approx_percentile_cont(m.round_trip_time, 0.95) as p95_rtt,
        approx_percentile_cont(m.round_trip_time, 0.99) as p99_rtt,
        MIN(m.round_trip_time) as min_rtt,
        MAX(m.round_trip_time) as max_rtt,
        STDDEV(m.round_trip_time) as std_dev_rtt,
        AVG(rj.run_jitter_value) as jitter,
        rs.avg_packet_loss as packet_loss_rate,
        rs.total_messages_sum as total_messages,
        rs.successful_messages_sum as successful_messages,
        rs.failed_messages_sum as failed_messages,
        COUNT(*) as sample_count,
        MAX(m.time) as time_period
      FROM latency_measurements m
      LEFT JOIN run_jitter rj ON m.run_id = rj.run_id AND m.platform = rj.platform AND m.location_id = rj.location_id
      LEFT JOIN run_stats rs ON m.platform = rs.platform AND m.location_id = rs.location_id
      WHERE m.time >= now() - INTERVAL '${Number(hours_ago)} hours'
        AND m.round_trip_time IS NOT NULL
    `;

		// Add optional filters again for main query
		if (platform) {
			query += ` AND m.platform = '${escapeSQLString(platform)}'`;
		}

		if (location_id) {
			query += ` AND m.location_id = '${escapeSQLString(location_id)}'`;
		}

		query +=
			" GROUP BY m.platform, m.location_id, rs.avg_packet_loss, rs.total_messages_sum, rs.successful_messages_sum, rs.failed_messages_sum";
		query += " ORDER BY m.platform, m.location_id";

		const results: AggregatedMetric[] = [];

		try {
			const records = await this.client.query(query, this.database, {
				type: "sql",
			});

			// Process each platform/location combination
			for await (const record of records) {
				const platform_val = String(record.platform || "unknown");
				const location_val = String(record.location_id || "unknown");
				const time_period = String(record.time_period || "");
				const sample_count = Number.parseInt(
					String(record.sample_count || "0"),
					10,
				);

				// Create separate result entries for each metric
				const metrics = [
					{
						name: "mean_rtt",
						avg: Number(record.mean_rtt) || 0,
						min: Number(record.mean_rtt) || 0,
						max: Number(record.mean_rtt) || 0,
					},
					{
						name: "median_rtt",
						avg: Number(record.median_rtt) || 0,
						min: Number(record.median_rtt) || 0,
						max: Number(record.median_rtt) || 0,
					},
					{
						name: "p50_rtt",
						avg: Number(record.p50_rtt) || 0,
						min: Number(record.p50_rtt) || 0,
						max: Number(record.p50_rtt) || 0,
					},
					{
						name: "p95_rtt",
						avg: Number(record.p95_rtt) || 0,
						min: Number(record.p95_rtt) || 0,
						max: Number(record.p95_rtt) || 0,
					},
					{
						name: "p99_rtt",
						avg: Number(record.p99_rtt) || 0,
						min: Number(record.p99_rtt) || 0,
						max: Number(record.p99_rtt) || 0,
					},
					{
						name: "min_rtt",
						avg: Number(record.min_rtt) || 0,
						min: Number(record.min_rtt) || 0,
						max: Number(record.min_rtt) || 0,
					},
					{
						name: "max_rtt",
						avg: Number(record.max_rtt) || 0,
						min: Number(record.max_rtt) || 0,
						max: Number(record.max_rtt) || 0,
					},
					{
						name: "std_dev_rtt",
						avg: Number(record.std_dev_rtt) || 0,
						min: Number(record.std_dev_rtt) || 0,
						max: Number(record.std_dev_rtt) || 0,
					},
					{
						name: "jitter",
						avg: Number(record.jitter) || 0,
						min: Number(record.jitter) || 0,
						max: Number(record.jitter) || 0,
					},
					{
						name: "packet_loss_rate",
						avg: Number(record.packet_loss_rate) || 0,
						min: Number(record.packet_loss_rate) || 0,
						max: Number(record.packet_loss_rate) || 0,
					},
					{
						name: "total_messages",
						avg: Number(record.total_messages) || 0,
						min: Number(record.total_messages) || 0,
						max: Number(record.total_messages) || 0,
					},
					{
						name: "successful_messages",
						avg: Number(record.successful_messages) || 0,
						min: Number(record.successful_messages) || 0,
						max: Number(record.successful_messages) || 0,
					},
					{
						name: "failed_messages",
						avg: Number(record.failed_messages) || 0,
						min: Number(record.failed_messages) || 0,
						max: Number(record.failed_messages) || 0,
					},
				];

				for (const metric of metrics) {
					results.push({
						platform: platform_val,
						location_id: location_val,
						metric_name: metric.name,
						avg_value: metric.avg,
						min_value: metric.min,
						max_value: metric.max,
						sample_count: sample_count,
						time_period: time_period,
					});
				}
			}
		} catch (error) {
			console.error("Failed to query aggregated stats:", error);
		}

		return results;
	}

	/**
	 * Query time-series data for charting.
	 * Returns raw round_trip_time measurements over time.
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

		// For time series, we aggregate measurements by run_id
		// Each data point represents the average of ~100 pings from a single benchmark run
		let query = `
      SELECT
        platform,
        location_id,
        run_id,
        AVG(round_trip_time) as value,
        MAX(time) as timestamp
      FROM latency_measurements
      WHERE time >= now() - INTERVAL '${Number(hours_ago)} hours'
        AND round_trip_time IS NOT NULL
    `;

		// Add optional filters with escaped values
		if (platform) {
			query += ` AND platform = '${escapeSQLString(platform)}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${escapeSQLString(location_id)}'`;
		}

		query += " GROUP BY run_id, platform, location_id";
		query += " ORDER BY timestamp DESC LIMIT 1000";

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
	 * Calculates statistics from recent raw measurements.
	 */
	async getLatestStats(): Promise<AggregatedMetric[]> {
		// Calculate stats from the most recent hour of data
		return this.queryAggregatedStats({ hours_ago: 1 });
	}

	/**
	 * Close the InfluxDB client connection.
	 */
	async close(): Promise<void> {
		await this.client.close();
	}
}
