import { useState } from "react";
import {
	ComposableMap,
	Geographies,
	Geography,
	Marker,
} from "react-simple-maps";
import type { AggregatedMetric } from "../lib/api-client";
import { getLocationCoordinates } from "../lib/location-coordinates";
import { LocationModal } from "./LocationModal";
import "./WorldMap.css";

interface WorldMapProps {
	metrics: AggregatedMetric[];
}

interface LocationData {
	locationId: string;
	label: string;
	lat: number;
	lon: number;
	pipecatMetrics: Record<string, AggregatedMetric>;
	livekitMetrics: Record<string, AggregatedMetric>;
	winner: "pipecat" | "livekit" | "tie";
	performanceDiff: number; // Percentage difference
}

// World atlas TopoJSON from CDN
const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

export function WorldMap({ metrics }: WorldMapProps) {
	const [selectedLocation, setSelectedLocation] = useState<string | null>(null);
	const [hoveredLocation, setHoveredLocation] = useState<string | null>(null);

	// Group metrics by location
	const locationData = processLocationData(metrics);

	// Close modal
	const handleCloseModal = () => {
		setSelectedLocation(null);
	};

	// Handle location click
	const handleLocationClick = (locationId: string) => {
		setSelectedLocation(locationId);
	};

	return (
		<div className="world-map-container">
			<ComposableMap
				projection="geoMercator"
				projectionConfig={{
					scale: 147,
					center: [10, 20],
				}}
				width={800}
				height={400}
				className="world-map-svg"
			>
				{/* World map geography */}
				<Geographies geography={geoUrl}>
					{({ geographies }) =>
						geographies.map((geo) => (
							<Geography
								key={geo.rsmKey}
								geography={geo}
								fill="#141414"
								stroke="#4a4a4a"
								strokeWidth={1.2}
								style={{
									default: { outline: "none" },
									hover: { outline: "none" },
									pressed: { outline: "none" },
								}}
							/>
						))
					}
				</Geographies>

				{/* Location markers */}
				{locationData.map((location) => {
					const isHovered = hoveredLocation === location.locationId;
					const isSelected = selectedLocation === location.locationId;
					const markerColor =
						location.winner === "pipecat"
							? "#00d4ff"
							: location.winner === "livekit"
								? "#00ff88"
								: "#808080";

					return (
						<Marker
							key={location.locationId}
							coordinates={[location.lon, location.lat]}
							onMouseEnter={() => setHoveredLocation(location.locationId)}
							onMouseLeave={() => setHoveredLocation(null)}
							onClick={() => handleLocationClick(location.locationId)}
						>
							{/* Glow effect */}
							<circle
								r={isHovered || isSelected ? 10 : 7}
								fill={markerColor}
								opacity={0.2}
								className="marker-glow"
							/>

							{/* Outer ring */}
							<circle
								r={4}
								fill="none"
								stroke={markerColor}
								strokeWidth={1.5}
								className="marker-ring"
							/>

							{/* Inner dot */}
							<circle r={2} fill={markerColor} className="marker-dot" />

							{/* Location label */}
							{(isHovered || isSelected) && (
								<text
									y={-12}
									textAnchor="middle"
									fill="#e8e8e8"
									fontSize={9}
									fontFamily="Azeret Mono, monospace"
									className="marker-label"
								>
									{location.locationId.toUpperCase()}
								</text>
							)}
						</Marker>
					);
				})}
			</ComposableMap>

			{/* Legend */}
			<div className="map-legend">
				<div className="legend-item">
					<div className="legend-marker pipecat" />
					<span>Pipecat (Daily) Wins</span>
				</div>
				<div className="legend-item">
					<div className="legend-marker livekit" />
					<span>LiveKit Wins</span>
				</div>
				<div className="legend-item">
					<div className="legend-marker tie" />
					<span>Tied</span>
				</div>
			</div>

			{/* Tooltip for hovered location */}
			{hoveredLocation &&
				locationData.find((l) => l.locationId === hoveredLocation) && (
					<LocationTooltip
						locationData={
							locationData.find(
								(l) => l.locationId === hoveredLocation,
							) as LocationData
						}
					/>
				)}

			{/* Modal for selected location */}
			{selectedLocation &&
				locationData.find((l) => l.locationId === selectedLocation) && (
					<LocationModal
						locationData={
							locationData.find(
								(l) => l.locationId === selectedLocation,
							) as LocationData
						}
						onClose={handleCloseModal}
					/>
				)}
		</div>
	);
}

/**
 * Process metrics data and calculate winners for each location
 */
function processLocationData(metrics: AggregatedMetric[]): LocationData[] {
	// Group metrics by location
	const locationMap = new Map<
		string,
		{
			pipecat: Record<string, AggregatedMetric>;
			livekit: Record<string, AggregatedMetric>;
		}
	>();

	for (const metric of metrics) {
		const { location_id, platform, metric_name } = metric;

		if (!locationMap.has(location_id)) {
			locationMap.set(location_id, { pipecat: {}, livekit: {} });
		}

		const locationMetrics = locationMap.get(location_id)!;
		if (platform === "daily") {
			locationMetrics.pipecat[metric_name] = metric;
		} else {
			locationMetrics.livekit[metric_name] = metric;
		}
	}

	// Calculate winners and convert to array
	const locationData: LocationData[] = [];

	for (const [locationId, { pipecat, livekit }] of locationMap.entries()) {
		const coords = getLocationCoordinates(locationId);

		// Calculate average performance (lower is better for latency)
		const pipecatScore =
			(pipecat.mean_rtt?.avg_value || 0) + (pipecat.p95_rtt?.avg_value || 0);
		const livekitScore =
			(livekit.mean_rtt?.avg_value || 0) + (livekit.p95_rtt?.avg_value || 0);

		let winner: "pipecat" | "livekit" | "tie" = "tie";
		let performanceDiff = 0;

		if (pipecatScore > 0 && livekitScore > 0) {
			const diff = ((pipecatScore - livekitScore) / pipecatScore) * 100;
			performanceDiff = Math.abs(diff);

			if (Math.abs(diff) > 5) {
				// More than 5% difference
				winner = pipecatScore < livekitScore ? "pipecat" : "livekit";
			}
		} else if (pipecatScore > 0) {
			winner = "pipecat";
		} else if (livekitScore > 0) {
			winner = "livekit";
		}

		locationData.push({
			locationId,
			label: coords.label,
			lat: coords.lat,
			lon: coords.lon,
			pipecatMetrics: pipecat,
			livekitMetrics: livekit,
			winner,
			performanceDiff,
		});
	}

	return locationData;
}

/**
 * Hover tooltip component
 */
function LocationTooltip({ locationData }: { locationData: LocationData }) {
	const pipecatRtt = locationData.pipecatMetrics.mean_rtt?.avg_value || 0;
	const livekitRtt = locationData.livekitMetrics.mean_rtt?.avg_value || 0;

	return (
		<div className="map-tooltip">
			<div className="tooltip-header">{locationData.label}</div>
			<div className="tooltip-content">
				<div className="tooltip-row">
					<span className="platform-label pipecat">Pipecat:</span>
					<span className="metric-value">{pipecatRtt.toFixed(2)}ms</span>
				</div>
				<div className="tooltip-row">
					<span className="platform-label livekit">LiveKit:</span>
					<span className="metric-value">{livekitRtt.toFixed(2)}ms</span>
				</div>
				{locationData.winner !== "tie" && (
					<div className="tooltip-winner">
						{locationData.winner === "pipecat" ? "Pipecat" : "LiveKit"} is{" "}
						{locationData.performanceDiff.toFixed(1)}% faster
					</div>
				)}
			</div>
			<div className="tooltip-hint">Click for details</div>
		</div>
	);
}
