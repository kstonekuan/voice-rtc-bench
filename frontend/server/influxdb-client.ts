/**
 * Amazon Timestream for InfluxDB 3 client for querying benchmark results.
 */

import { InfluxDBClient } from "@influxdata/influxdb3-client";

export interface InfluxDBConfig {
	url: string;
	token: string;
	org: string;
	database: string;
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
	 */
	async queryAggregatedStats(params: {
		platform?: string;
		location_id?: string;
		hours_ago?: number;
	}): Promise<AggregatedMetric[]> {
		const { platform, location_id, hours_ago = 24 } = params;

		const metrics = [
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

		const results: AggregatedMetric[] = [];

		for (const metric of metrics) {
			let query = `
        SELECT
          platform,
          location_id,
          '${metric}' as metric_name,
          AVG(${metric}) as avg_value,
          MIN(${metric}) as min_value,
          MAX(${metric}) as max_value,
          COUNT(${metric}) as sample_count,
          DATE_BIN(INTERVAL '${hours_ago} hours', time, TIMESTAMP '1970-01-01') as time_period
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '${hours_ago} hours'
          AND ${metric} IS NOT NULL
      `;

			if (platform) {
				query += ` AND platform = '${platform}'`;
			}

			if (location_id) {
				query += ` AND location_id = '${location_id}'`;
			}

			query += " GROUP BY platform, location_id, time_period";
			query += " ORDER BY time_period DESC";

			try {
				const records = await this.client.query(query, this.database, {
					type: "sql",
				});

				for await (const record of records) {
					results.push({
						platform: (record.platform as string) || "unknown",
						location_id: (record.location_id as string) || "unknown",
						metric_name: metric,
						avg_value: Number(record.avg_value) || 0,
						min_value: Number(record.min_value) || 0,
						max_value: Number(record.max_value) || 0,
						sample_count: Number.parseInt(
							String(record.sample_count) || "0",
							10,
						),
						time_period: (record.time_period as string) || "",
					});
				}
			} catch (error) {
				console.error(`Failed to query aggregated stats for ${metric}:`, error);
			}
		}

		return results;
	}

	/**
	 * Query time-series data for charting.
	 */
	async queryTimeSeries(params: {
		platform?: string;
		location_id?: string;
		metric_name: string;
		hours_ago?: number;
	}): Promise<TimeSeriesDataPoint[]> {
		const { platform, location_id, metric_name, hours_ago = 24 } = params;

		let query = `
      SELECT
        platform,
        location_id,
        ${metric_name} as value,
        time as timestamp
      FROM latency_measurements
      WHERE time >= now() - INTERVAL '${hours_ago} hours'
        AND ${metric_name} IS NOT NULL
    `;

		if (platform) {
			query += ` AND platform = '${platform}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${location_id}'`;
		}

		query += " ORDER BY time DESC LIMIT 1000";

		const results: TimeSeriesDataPoint[] = [];

		try {
			const records = await this.client.query(query, this.database, {
				type: "sql",
			});

			for await (const record of records) {
				results.push({
					platform: (record.platform as string) || "unknown",
					location_id: (record.location_id as string) || "unknown",
					metric_name: metric_name,
					value: Number(record.value) || 0,
					timestamp: (record.timestamp as string) || "",
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
	 */
	async getLatestStats(): Promise<AggregatedMetric[]> {
		const metrics = [
			"mean_rtt",
			"p95_rtt",
			"p99_rtt",
			"jitter",
			"packet_loss_rate",
		];

		const results: AggregatedMetric[] = [];

		for (const metric of metrics) {
			const query = `
        SELECT
          platform,
          location_id,
          '${metric}' as metric_name,
          ${metric} as avg_value,
          ${metric} as min_value,
          ${metric} as max_value,
          1 as sample_count,
          time as time_period
        FROM latency_measurements
        WHERE time >= now() - INTERVAL '1 hour'
          AND ${metric} IS NOT NULL
        ORDER BY time DESC
        LIMIT 100
      `;

			try {
				const records = await this.client.query(query, this.database, {
					type: "sql",
				});

				for await (const record of records) {
					results.push({
						platform: (record.platform as string) || "unknown",
						location_id: (record.location_id as string) || "unknown",
						metric_name: metric,
						avg_value: Number(record.avg_value) || 0,
						min_value: Number(record.min_value) || 0,
						max_value: Number(record.max_value) || 0,
						sample_count: 1,
						time_period: (record.time_period as string) || "",
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
