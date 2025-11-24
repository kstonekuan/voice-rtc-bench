import { useEffect, useState } from "react";
import "./App.css";
import {
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { WorldMap } from "./components/WorldMap";
import {
	type AggregatedMetric,
	apiClient,
	type TimeSeriesDataPoint,
} from "./lib/api-client";

function App() {
	// State
	const [locations, setLocations] = useState<string[]>([]);
	const [selectedLocation, setSelectedLocation] = useState<string>("all");
	const [selectedPlatform, setSelectedPlatform] = useState<
		"all" | "daily" | "livekit"
	>("all");
	const [timeRange, setTimeRange] = useState<number>(24);
	const [metrics, setMetrics] = useState<AggregatedMetric[]>([]);
	const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesDataPoint[]>(
		[],
	);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [apiHealthy, setApiHealthy] = useState(false);
	const [viewMode, setViewMode] = useState<"map" | "grid">("map");

	// Check API health on mount
	useEffect(() => {
		apiClient.healthCheck().then(setApiHealthy);
	}, []);

	// Load locations on mount
	useEffect(() => {
		apiClient
			.getLocations()
			.then(setLocations)
			.catch((err) => console.error("Failed to load locations:", err));
	}, []);

	// Load metrics when filters change
	useEffect(() => {
		const loadMetrics = async () => {
			setLoading(true);
			setError(null);

			try {
				const data = await apiClient.getAggregatedStats({
					platform: selectedPlatform === "all" ? undefined : selectedPlatform,
					location: selectedLocation === "all" ? undefined : selectedLocation,
					hours: timeRange,
				});
				setMetrics(data);
			} catch (err) {
				setError(err instanceof Error ? err.message : "Failed to load metrics");
			} finally {
				setLoading(false);
			}
		};

		if (apiHealthy) {
			loadMetrics();
		}
	}, [selectedLocation, selectedPlatform, timeRange, apiHealthy]);

	// Load time-series data when filters change
	useEffect(() => {
		const loadTimeSeries = async () => {
			try {
				const data = await apiClient.getTimeSeries({
					metric: "mean_rtt",
					platform: selectedPlatform === "all" ? undefined : selectedPlatform,
					location: selectedLocation === "all" ? undefined : selectedLocation,
					hours: timeRange,
				});
				setTimeSeriesData(data);
			} catch (err) {
				console.error("Failed to load time series data:", err);
			}
		};

		if (apiHealthy) {
			loadTimeSeries();
		}
	}, [selectedLocation, selectedPlatform, timeRange, apiHealthy]);

	// Group metrics by platform and location
	const groupedMetrics = metrics.reduce(
		(acc, metric) => {
			const key = `${metric.platform}-${metric.location_id}`;
			if (!acc[key]) {
				acc[key] = {
					platform: metric.platform,
					location: metric.location_id,
					metrics: {},
				};
			}
			acc[key].metrics[metric.metric_name] = metric;
			return acc;
		},
		{} as Record<
			string,
			{
				platform: string;
				location: string;
				metrics: Record<string, AggregatedMetric>;
			}
		>,
	);

	const groups = Object.values(groupedMetrics);
	const dailyGroups = groups.filter((g) => g.platform === "daily");
	const livekitGroups = groups.filter((g) => g.platform === "livekit");

	return (
		<div className="app">
			{/* Header */}
			<header className="header">
				<h1 className="header-title">Voice RTC Benchmark Dashboard</h1>
				<p className="header-subtitle">
					Real-time Data Channel Latency Metrics: Pipecat (Daily) vs LiveKit
				</p>
				{!apiHealthy && (
					<div className="api-warning">
						⚠️ API server not responding. Start with: pnpm dev:api
					</div>
				)}
			</header>

			{/* Control Panel */}
			<section className="control-panel">
				<div className="control-grid">
					<div className="control-group">
						<label htmlFor="location" className="control-label">
							Location
						</label>
						<select
							id="location"
							className="control-input"
							value={selectedLocation}
							onChange={(e) => setSelectedLocation(e.target.value)}
						>
							<option value="all">All Locations</option>
							{locations.map((loc) => (
								<option key={loc} value={loc}>
									{loc}
								</option>
							))}
						</select>
					</div>

					<div className="control-group">
						<label htmlFor="platform" className="control-label">
							Platform
						</label>
						<select
							id="platform"
							className="control-input"
							value={selectedPlatform}
							onChange={(e) =>
								setSelectedPlatform(
									e.target.value as "all" | "daily" | "livekit",
								)
							}
						>
							<option value="all">Both Platforms</option>
							<option value="daily">Pipecat (Daily) Only</option>
							<option value="livekit">LiveKit Only</option>
						</select>
					</div>

					<div className="control-group">
						<label htmlFor="time-range" className="control-label">
							Time Range
						</label>
						<select
							id="time-range"
							className="control-input"
							value={timeRange}
							onChange={(e) => setTimeRange(Number(e.target.value))}
						>
							<option value={1}>Last Hour</option>
							<option value={6}>Last 6 Hours</option>
							<option value={24}>Last 24 Hours</option>
							<option value={168}>Last Week</option>
						</select>
					</div>

					<div className="control-group">
						<label htmlFor="view-mode" className="control-label">
							View Mode
						</label>
						<div className="view-toggle">
							<button
								type="button"
								className={`view-toggle-btn ${viewMode === "map" ? "active" : ""}`}
								onClick={() => setViewMode("map")}
							>
								Map
							</button>
							<button
								type="button"
								className={`view-toggle-btn ${viewMode === "grid" ? "active" : ""}`}
								onClick={() => setViewMode("grid")}
							>
								Grid
							</button>
						</div>
					</div>
				</div>
			</section>

			{/* Loading / Error States */}
			{loading && <div className="loading-message">Loading metrics...</div>}
			{error && <div className="error-message">{error}</div>}

			{/* Empty State */}
			{!loading && !error && groups.length === 0 && (
				<div className="empty-state">
					<p>No benchmark data available for the selected filters.</p>
					<p className="empty-state-hint">
						Run benchmarks using the Python CLI to populate data.
					</p>
				</div>
			)}

			{/* Results */}
			{!loading && !error && groups.length > 0 && (
				<>
					{/* Map View */}
					{viewMode === "map" && (
						<>
							<WorldMap metrics={metrics} />

							{/* Time Series Chart - shown below map */}
							{timeSeriesData.length > 0 && (
								<TimeSeriesChart
									data={timeSeriesData}
									selectedPlatform={selectedPlatform}
								/>
							)}
						</>
					)}

					{/* Grid View */}
					{viewMode === "grid" && (
						<>
							{/* Daily Results */}
							{dailyGroups.length > 0 && (
								<section className="platform-section">
									<h2 className="platform-title">Pipecat (Daily) Results</h2>
									<div className="benchmark-grid">
										{dailyGroups.map((group) => (
											<MetricsCard
												key={`daily-${group.location}`}
												platform="daily"
												location={group.location}
												metrics={group.metrics}
											/>
										))}
									</div>
								</section>
							)}

							{/* LiveKit Results */}
							{livekitGroups.length > 0 && (
								<section className="platform-section">
									<h2 className="platform-title">LiveKit Results</h2>
									<div className="benchmark-grid">
										{livekitGroups.map((group) => (
											<MetricsCard
												key={`livekit-${group.location}`}
												platform="livekit"
												location={group.location}
												metrics={group.metrics}
											/>
										))}
									</div>
								</section>
							)}
						</>
					)}

					{/* Comparison Section - shown in both views */}
					{dailyGroups.length > 0 && livekitGroups.length > 0 && (
						<ComparisonSection
							dailyGroups={dailyGroups}
							livekitGroups={livekitGroups}
						/>
					)}
				</>
			)}
		</div>
	);
}

// Metrics Card Component
function MetricsCard({
	platform,
	location,
	metrics,
}: {
	platform: string;
	location: string;
	metrics: Record<string, AggregatedMetric>;
}) {
	const meanRtt = metrics.mean_rtt;
	const p95Rtt = metrics.p95_rtt;
	const p99Rtt = metrics.p99_rtt;
	const jitter = metrics.jitter;
	const packetLoss = metrics.packet_loss_rate;

	return (
		<div className={`benchmark-card ${platform}`}>
			<div className="benchmark-header">
				<h3 className="benchmark-title">
					{platform === "daily" ? "Pipecat (Daily)" : "LiveKit"}
				</h3>
				<div className="location-badge">{location}</div>
			</div>

			<div className="stats-grid">
				{meanRtt && (
					<div className="stat-item">
						<div className="stat-label">Mean RTT</div>
						<div className="stat-value">
							{meanRtt.avg_value.toFixed(2)}
							<span className="stat-unit">ms</span>
						</div>
						<div className="stat-range">
							{meanRtt.min_value.toFixed(1)} - {meanRtt.max_value.toFixed(1)} ms
						</div>
					</div>
				)}

				{p95Rtt && (
					<div className="stat-item">
						<div className="stat-label">P95 RTT</div>
						<div className="stat-value">
							{p95Rtt.avg_value.toFixed(2)}
							<span className="stat-unit">ms</span>
						</div>
						<div className="stat-range">
							{p95Rtt.min_value.toFixed(1)} - {p95Rtt.max_value.toFixed(1)} ms
						</div>
					</div>
				)}

				{p99Rtt && (
					<div className="stat-item">
						<div className="stat-label">P99 RTT</div>
						<div className="stat-value">
							{p99Rtt.avg_value.toFixed(2)}
							<span className="stat-unit">ms</span>
						</div>
						<div className="stat-range">
							{p99Rtt.min_value.toFixed(1)} - {p99Rtt.max_value.toFixed(1)} ms
						</div>
					</div>
				)}

				{jitter && (
					<div className="stat-item">
						<div className="stat-label">Jitter</div>
						<div className="stat-value">
							{jitter.avg_value.toFixed(2)}
							<span className="stat-unit">ms</span>
						</div>
						<div className="stat-range">
							{jitter.min_value.toFixed(1)} - {jitter.max_value.toFixed(1)} ms
						</div>
					</div>
				)}

				{packetLoss && (
					<div className="stat-item">
						<div className="stat-label">Packet Loss</div>
						<div className="stat-value">
							{(packetLoss.avg_value * 100).toFixed(2)}
							<span className="stat-unit">%</span>
						</div>
					</div>
				)}

				<div className="stat-item">
					<div className="stat-label">Sample Count</div>
					<div className="stat-value">{meanRtt?.sample_count || 0}</div>
				</div>
			</div>
		</div>
	);
}

// Comparison Section Component
function ComparisonSection({
	dailyGroups,
	livekitGroups,
}: {
	dailyGroups: Array<{
		platform: string;
		location: string;
		metrics: Record<string, AggregatedMetric>;
	}>;
	livekitGroups: Array<{
		platform: string;
		location: string;
		metrics: Record<string, AggregatedMetric>;
	}>;
}) {
	// Average across all locations for each platform
	const avgDaily = (metricName: string) => {
		const values = dailyGroups
			.map((g) => g.metrics[metricName]?.avg_value)
			.filter((v): v is number => v !== undefined);
		return values.length > 0
			? values.reduce((a, b) => a + b, 0) / values.length
			: 0;
	};

	const avgLiveKit = (metricName: string) => {
		const values = livekitGroups
			.map((g) => g.metrics[metricName]?.avg_value)
			.filter((v): v is number => v !== undefined);
		return values.length > 0
			? values.reduce((a, b) => a + b, 0) / values.length
			: 0;
	};

	const comparisons = [
		{
			label: "Mean RTT",
			daily: avgDaily("mean_rtt"),
			livekit: avgLiveKit("mean_rtt"),
		},
		{
			label: "P95 RTT",
			daily: avgDaily("p95_rtt"),
			livekit: avgLiveKit("p95_rtt"),
		},
		{
			label: "P99 RTT",
			daily: avgDaily("p99_rtt"),
			livekit: avgLiveKit("p99_rtt"),
		},
		{
			label: "Jitter",
			daily: avgDaily("jitter"),
			livekit: avgLiveKit("jitter"),
		},
	];

	return (
		<section className="comparison-section">
			<h2 className="comparison-title">
				Platform Comparison (Averaged Across Locations)
			</h2>
			<div className="comparison-grid">
				{comparisons.map((comp) => {
					const dailyWins = comp.daily > 0 && comp.daily < comp.livekit;
					const livekitWins = comp.livekit > 0 && comp.livekit < comp.daily;
					return (
						<div key={comp.label} className="comparison-stat">
							<div className="comparison-stat-label">{comp.label}</div>
							<div className="comparison-values">
								<span className="comparison-value daily">
									{comp.daily.toFixed(2)}ms
									{dailyWins && (
										<span className="winner-badge">
											<svg
												width="12"
												height="12"
												viewBox="0 0 24 24"
												fill="currentColor"
												style={{
													display: "inline-block",
													verticalAlign: "middle",
												}}
											>
												<path d="M12 2l2.4 7.4h7.6l-6 4.6 2.3 7-6.3-4.6-6.3 4.6 2.3-7-6-4.6h7.6z" />
											</svg>
										</span>
									)}
								</span>
								<span className="comparison-separator">vs</span>
								<span className="comparison-value livekit">
									{comp.livekit.toFixed(2)}ms
									{livekitWins && (
										<span className="winner-badge">
											<svg
												width="12"
												height="12"
												viewBox="0 0 24 24"
												fill="currentColor"
												style={{
													display: "inline-block",
													verticalAlign: "middle",
												}}
											>
												<path d="M12 2l2.4 7.4h7.6l-6 4.6 2.3 7-6.3-4.6-6.3 4.6 2.3-7-6-4.6h7.6z" />
											</svg>
										</span>
									)}
								</span>
							</div>
						</div>
					);
				})}
			</div>
		</section>
	);
}

// Time Series Chart Component
function TimeSeriesChart({
	data,
	selectedPlatform,
}: {
	data: TimeSeriesDataPoint[];
	selectedPlatform: "all" | "daily" | "livekit";
}) {
	// Transform data for recharts format using Map for O(n) complexity
	// Previously used array.find() which was O(n²)
	const dataMap = new Map<
		string,
		{ timestamp: string; daily?: number; livekit?: number }
	>();

	for (const point of data) {
		// Convert timestamp string to number (milliseconds) and create Date
		const timestampMs = Math.floor(Number(point.timestamp));
		const timestamp = new Date(timestampMs).toLocaleString();

		const existing = dataMap.get(timestamp);
		if (existing) {
			// Type-safe platform assignment
			if (point.platform === "daily") {
				existing.daily = point.value;
			} else if (point.platform === "livekit") {
				existing.livekit = point.value;
			}
		} else {
			// Type-safe initial value creation
			const newPoint: { timestamp: string; daily?: number; livekit?: number } =
				{
					timestamp,
				};
			if (point.platform === "daily") {
				newPoint.daily = point.value;
			} else if (point.platform === "livekit") {
				newPoint.livekit = point.value;
			}
			dataMap.set(timestamp, newPoint);
		}
	}

	// Convert Map to array and sort by timestamp
	const chartData = Array.from(dataMap.values()).sort((a, b) => {
		const dateA = new Date(a.timestamp);
		const dateB = new Date(b.timestamp);
		return dateA.getTime() - dateB.getTime();
	});

	return (
		<section className="time-series-section">
			<h2 className="time-series-title">Mean RTT Latency Over Time</h2>
			<div className="chart-container">
				<ResponsiveContainer width="100%" height={400}>
					<LineChart data={chartData}>
						<CartesianGrid strokeDasharray="3 3" />
						<XAxis
							dataKey="timestamp"
							angle={-45}
							textAnchor="end"
							height={100}
							tick={{ fontSize: 12 }}
						/>
						<YAxis
							label={{
								value: "Latency (ms)",
								angle: -90,
								position: "insideLeft",
							}}
						/>
						<Tooltip />
						<Legend />
						{(selectedPlatform === "all" || selectedPlatform === "daily") && (
							<Line
								type="monotone"
								dataKey="daily"
								stroke="#00d4ff"
								name="Pipecat (Daily)"
								strokeWidth={2}
								dot={{ r: 4 }}
							/>
						)}
						{(selectedPlatform === "all" || selectedPlatform === "livekit") && (
							<Line
								type="monotone"
								dataKey="livekit"
								stroke="#00ff88"
								name="LiveKit"
								strokeWidth={2}
								dot={{ r: 4 }}
							/>
						)}
					</LineChart>
				</ResponsiveContainer>
			</div>
		</section>
	);
}

export default App;
