/**
 * Amazon Timestream client for querying benchmark results.
 */

import {
	QueryCommand,
	type QueryCommandOutput,
	type Row,
	TimestreamQueryClient,
} from "@aws-sdk/client-timestream-query";

export interface TimestreamConfig {
	region: string;
	database: string;
	table: string;
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

export class TimestreamClient {
	private client: TimestreamQueryClient;
	private database: string;
	private table: string;

	constructor(config: TimestreamConfig) {
		this.client = new TimestreamQueryClient({ region: config.region });
		this.database = config.database;
		this.table = config.table;
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

		let query = `
      SELECT
        platform,
        location_id,
        measure_name,
        AVG(measure_value::double) as avg_value,
        MIN(measure_value::double) as min_value,
        MAX(measure_value::double) as max_value,
        COUNT(*) as sample_count,
        bin(time, ${hours_ago}h) as time_period
      FROM "${this.database}"."${this.table}"
      WHERE time >= ago(${hours_ago}h)
    `;

		if (platform) {
			query += ` AND platform = '${platform}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${location_id}'`;
		}

		const metricsFilter = metrics.map((m) => `'${m}'`).join(", ");
		query += ` AND measure_name IN (${metricsFilter})`;
		query += " GROUP BY platform, location_id, measure_name, bin(time, 1h)";
		query += " ORDER BY time_period DESC";

		const command = new QueryCommand({ QueryString: query });
		const response: QueryCommandOutput = await this.client.send(command);

		return this.parseAggregatedResults(response);
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
        measure_name,
        measure_value::double as value,
        time
      FROM "${this.database}"."${this.table}"
      WHERE time >= ago(${hours_ago}h)
        AND measure_name = '${metric_name}'
    `;

		if (platform) {
			query += ` AND platform = '${platform}'`;
		}

		if (location_id) {
			query += ` AND location_id = '${location_id}'`;
		}

		query += " ORDER BY time DESC LIMIT 1000";

		const command = new QueryCommand({ QueryString: query });
		const response: QueryCommandOutput = await this.client.send(command);

		return this.parseTimeSeriesResults(response);
	}

	/**
	 * Get list of unique locations from the data.
	 */
	async getLocations(): Promise<string[]> {
		const query = `
      SELECT DISTINCT location_id
      FROM "${this.database}"."${this.table}"
      WHERE time >= ago(7d)
      ORDER BY location_id
    `;

		const command = new QueryCommand({ QueryString: query });
		const response: QueryCommandOutput = await this.client.send(command);

		return (
			response.Rows?.map((row) => {
				const data = row.Data?.[0];
				return data?.ScalarValue || "unknown";
			}) || []
		);
	}

	/**
	 * Get latest statistics for all locations and platforms.
	 */
	async getLatestStats(): Promise<AggregatedMetric[]> {
		const query = `
      SELECT
        platform,
        location_id,
        measure_name,
        measure_value::double as avg_value,
        measure_value::double as min_value,
        measure_value::double as max_value,
        1 as sample_count,
        time as time_period
      FROM "${this.database}"."${this.table}"
      WHERE time >= ago(1h)
        AND measure_name IN ('mean_rtt', 'p95_rtt', 'p99_rtt', 'jitter', 'packet_loss_rate')
      ORDER BY time DESC
      LIMIT 100
    `;

		const command = new QueryCommand({ QueryString: query });
		const response: QueryCommandOutput = await this.client.send(command);

		return this.parseAggregatedResults(response);
	}

	private parseAggregatedResults(
		response: QueryCommandOutput,
	): AggregatedMetric[] {
		if (!response.Rows) return [];

		return response.Rows.map((row: Row) => {
			const data = row.Data || [];
			return {
				platform: data[0]?.ScalarValue || "unknown",
				location_id: data[1]?.ScalarValue || "unknown",
				metric_name: data[2]?.ScalarValue || "unknown",
				avg_value: Number.parseFloat(data[3]?.ScalarValue || "0"),
				min_value: Number.parseFloat(data[4]?.ScalarValue || "0"),
				max_value: Number.parseFloat(data[5]?.ScalarValue || "0"),
				sample_count: Number.parseInt(data[6]?.ScalarValue || "0", 10),
				time_period: data[7]?.ScalarValue || "",
			};
		});
	}

	private parseTimeSeriesResults(
		response: QueryCommandOutput,
	): TimeSeriesDataPoint[] {
		if (!response.Rows) return [];

		return response.Rows.map((row: Row) => {
			const data = row.Data || [];
			return {
				platform: data[0]?.ScalarValue || "unknown",
				location_id: data[1]?.ScalarValue || "unknown",
				metric_name: data[2]?.ScalarValue || "unknown",
				value: Number.parseFloat(data[3]?.ScalarValue || "0"),
				timestamp: data[4]?.ScalarValue || "",
			};
		});
	}
}
