/**
 * API client for fetching benchmark results from the backend.
 */

import {
	generateMockAggregatedMetrics,
	generateMockTimeSeriesData,
	getMockLatestMetrics,
	getMockLocations,
} from "./mock-data";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3001";
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === "true";

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
		// Return mock data if enabled
		if (USE_MOCK_DATA) {
			let data = generateMockAggregatedMetrics();

			// Apply filters
			if (params.platform) {
				data = data.filter((metric) => metric.platform === params.platform);
			}
			if (params.location) {
				data = data.filter((metric) => metric.location_id === params.location);
			}

			return data;
		}

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
		// Return mock data if enabled
		if (USE_MOCK_DATA) {
			const hours = params.hours || 24;
			let data = generateMockTimeSeriesData(params.metric, hours);

			// Apply filters
			if (params.platform) {
				data = data.filter((point) => point.platform === params.platform);
			}
			if (params.location) {
				data = data.filter((point) => point.location_id === params.location);
			}

			return data;
		}

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
		// Return mock data if enabled
		if (USE_MOCK_DATA) {
			return getMockLocations();
		}

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
		// Return mock data if enabled
		if (USE_MOCK_DATA) {
			return getMockLatestMetrics();
		}

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
		// Mock data is always "healthy"
		if (USE_MOCK_DATA) {
			return true;
		}

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
