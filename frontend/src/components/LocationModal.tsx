import { useEffect } from "react";
import type { AggregatedMetric } from "../lib/api-client";

interface LocationModalProps {
	locationData: {
		locationId: string;
		label: string;
		pipecatMetrics: Record<string, AggregatedMetric>;
		livekitMetrics: Record<string, AggregatedMetric>;
		winner: "pipecat" | "livekit" | "tie";
		performanceDiff: number;
	};
	onClose: () => void;
}

export function LocationModal({ locationData, onClose }: LocationModalProps) {
	// Close on ESC key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				onClose();
			}
		};

		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [onClose]);

	const metrics = [
		{ key: "mean_rtt", label: "Mean RTT", unit: "ms" },
		{ key: "p95_rtt", label: "P95 RTT", unit: "ms" },
		{ key: "p99_rtt", label: "P99 RTT", unit: "ms" },
		{ key: "jitter", label: "Jitter", unit: "ms" },
		{ key: "packet_loss_rate", label: "Packet Loss", unit: "%", multiply: 100 },
	];

	return (
		<div className="modal-overlay" onClick={onClose}>
			<div className="modal-content" onClick={(e) => e.stopPropagation()}>
				{/* Header */}
				<div className="modal-header">
					<div>
						<h2 className="modal-title">{locationData.label}</h2>
						<div className="modal-subtitle">{locationData.locationId}</div>
					</div>
					<button type="button" className="modal-close" onClick={onClose}>
						×
					</button>
				</div>

				{/* Winner banner */}
				{locationData.winner !== "tie" && (
					<div className={`winner-banner ${locationData.winner}`}>
						<span className="winner-icon">▲</span>
						{locationData.winner === "pipecat" ? "Pipecat (Daily)" : "LiveKit"}{" "}
						performs {locationData.performanceDiff.toFixed(1)}% better at this
						location
					</div>
				)}

				{/* Comparison grid */}
				<div className="comparison-container">
					{/* Headers */}
					<div className="comparison-header">
						<div className="comparison-column">
							<h3 className="platform-header pipecat">Pipecat (Daily)</h3>
						</div>
						<div className="comparison-divider" />
						<div className="comparison-column">
							<h3 className="platform-header livekit">LiveKit</h3>
						</div>
					</div>

					{/* Metrics rows */}
					{metrics.map((metric) => {
						const pipecatValue =
							locationData.pipecatMetrics[metric.key]?.avg_value || 0;
						const livekitValue =
							locationData.livekitMetrics[metric.key]?.avg_value || 0;

						const pipecatDisplay = metric.multiply
							? pipecatValue * metric.multiply
							: pipecatValue;
						const livekitDisplay = metric.multiply
							? livekitValue * metric.multiply
							: livekitValue;

						// Determine winner for this metric (lower is better)
						let metricWinner: "pipecat" | "livekit" | "tie" = "tie";
						if (pipecatValue > 0 && livekitValue > 0) {
							if (pipecatValue < livekitValue * 0.95) metricWinner = "pipecat";
							else if (livekitValue < pipecatValue * 0.95)
								metricWinner = "livekit";
						}

						return (
							<div key={metric.key} className="metric-row">
								<div className="metric-label">{metric.label}</div>

								<div className="comparison-values">
									<div
										className={`metric-value ${metricWinner === "pipecat" ? "winner" : ""}`}
									>
										{pipecatDisplay > 0 ? (
											<>
												<span className="value-number">
													{pipecatDisplay.toFixed(2)}
												</span>
												<span className="value-unit">{metric.unit}</span>
												{metricWinner === "pipecat" && (
													<span className="winner-badge">✓</span>
												)}
											</>
										) : (
											<span className="no-data">—</span>
										)}
									</div>

									<div className="vs-divider">vs</div>

									<div
										className={`metric-value ${metricWinner === "livekit" ? "winner" : ""}`}
									>
										{livekitDisplay > 0 ? (
											<>
												<span className="value-number">
													{livekitDisplay.toFixed(2)}
												</span>
												<span className="value-unit">{metric.unit}</span>
												{metricWinner === "livekit" && (
													<span className="winner-badge">✓</span>
												)}
											</>
										) : (
											<span className="no-data">—</span>
										)}
									</div>
								</div>

								{/* Min-max ranges */}
								<div className="metric-ranges">
									<div className="range-value">
										{pipecatValue > 0 && (
											<>
												{(
													(locationData.pipecatMetrics[metric.key]?.min_value ||
														0) * (metric.multiply || 1)
												).toFixed(1)}
												-
												{(
													(locationData.pipecatMetrics[metric.key]?.max_value ||
														0) * (metric.multiply || 1)
												).toFixed(1)}
											</>
										)}
									</div>
									<div className="range-divider" />
									<div className="range-value">
										{livekitValue > 0 && (
											<>
												{(
													(locationData.livekitMetrics[metric.key]?.min_value ||
														0) * (metric.multiply || 1)
												).toFixed(1)}
												-
												{(
													(locationData.livekitMetrics[metric.key]?.max_value ||
														0) * (metric.multiply || 1)
												).toFixed(1)}
											</>
										)}
									</div>
								</div>
							</div>
						);
					})}
				</div>

				{/* Sample counts */}
				<div className="modal-footer">
					<div className="sample-count">
						<span className="footer-label">Sample Count:</span>
						<span className="footer-value pipecat">
							{locationData.pipecatMetrics.mean_rtt?.sample_count || 0}
						</span>
						<span className="footer-divider">/</span>
						<span className="footer-value livekit">
							{locationData.livekitMetrics.mean_rtt?.sample_count || 0}
						</span>
					</div>
				</div>
			</div>
		</div>
	);
}
