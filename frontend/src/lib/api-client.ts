/**
 * API client for fetching benchmark results from the backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3001";

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

export interface QueryParams {
	platform?: "daily" | "livekit";
	location?: string;
	hours?: number;
}

export interface TimeSeriesParams extends QueryParams {
	metric: string;
}

class BenchmarkApiClient {
	private baseUrl: string;

	constructor(baseUrl: string = API_BASE_URL) {
		this.baseUrl = baseUrl;
	}

	/**
	 * Fetch aggregated statistics over time period.
	 */
	async getAggregatedStats(
		params: QueryParams = {},
	): Promise<AggregatedMetric[]> {
		const query = new URLSearchParams();
		if (params.platform) query.set("platform", params.platform);
		if (params.location) query.set("location", params.location);
		if (params.hours) query.set("hours", params.hours.toString());

		const response = await fetch(
			`${this.baseUrl}/api/results/aggregated?${query}`,
		);

		if (!response.ok) {
			throw new Error(
				`Failed to fetch aggregated stats: ${response.statusText}`,
			);
		}

		const data = await response.json();
		return data.data;
	}

	/**
	 * Fetch time-series data for a specific metric.
	 */
	async getTimeSeries(
		params: TimeSeriesParams,
	): Promise<TimeSeriesDataPoint[]> {
		const query = new URLSearchParams();
		query.set("metric", params.metric);
		if (params.platform) query.set("platform", params.platform);
		if (params.location) query.set("location", params.location);
		if (params.hours) query.set("hours", params.hours.toString());

		const response = await fetch(
			`${this.baseUrl}/api/results/timeseries?${query}`,
		);

		if (!response.ok) {
			throw new Error(`Failed to fetch time series: ${response.statusText}`);
		}

		const data = await response.json();
		return data.data;
	}

	/**
	 * Fetch list of unique locations.
	 */
	async getLocations(): Promise<string[]> {
		const response = await fetch(`${this.baseUrl}/api/results/locations`);

		if (!response.ok) {
			throw new Error(`Failed to fetch locations: ${response.statusText}`);
		}

		const data = await response.json();
		return data.data;
	}

	/**
	 * Fetch latest statistics for all locations and platforms.
	 */
	async getLatestStats(): Promise<AggregatedMetric[]> {
		const response = await fetch(`${this.baseUrl}/api/results/latest`);

		if (!response.ok) {
			throw new Error(`Failed to fetch latest stats: ${response.statusText}`);
		}

		const data = await response.json();
		return data.data;
	}

	/**
	 * Check if the API server is healthy.
	 */
	async healthCheck(): Promise<boolean> {
		try {
			const response = await fetch(`${this.baseUrl}/health`);
			return response.ok;
		} catch {
			return false;
		}
	}
}

// Export singleton instance
export const apiClient = new BenchmarkApiClient();
