/**
 * API routes for querying benchmark results from Timestream.
 */

import { Router } from "express";
import { TimestreamClient } from "../timestream-client.js";

const router = Router();

// Initialize Timestream client
const timestream = new TimestreamClient({
	region: process.env.AWS_REGION || "us-east-1",
	database: process.env.TIMESTREAM_DATABASE || "voice-rtc-benchmarks",
	table: process.env.TIMESTREAM_TABLE || "latency_measurements",
});

/**
 * GET /api/results/aggregated
 * Get aggregated statistics over time period.
 *
 * Query params:
 * - platform: daily | livekit (optional)
 * - location: location ID (optional)
 * - hours: hours to look back (default: 24)
 */
router.get("/aggregated", async (req, res) => {
	try {
		const platform = req.query.platform as string | undefined;
		const location_id = req.query.location as string | undefined;
		const hours_ago = req.query.hours
			? Number.parseInt(req.query.hours as string, 10)
			: 24;

		const results = await timestream.queryAggregatedStats({
			platform,
			location_id,
			hours_ago,
		});

		res.json({
			data: results,
			query: { platform, location_id, hours_ago },
		});
	} catch (error) {
		console.error("Error querying aggregated stats:", error);
		res.status(500).json({
			error: "Failed to query aggregated statistics",
			message: error instanceof Error ? error.message : "Unknown error",
		});
	}
});

/**
 * GET /api/results/timeseries
 * Get time-series data for a specific metric.
 *
 * Query params:
 * - metric: metric name (required)
 * - platform: daily | livekit (optional)
 * - location: location ID (optional)
 * - hours: hours to look back (default: 24)
 */
router.get("/timeseries", async (req, res) => {
	try {
		const metric_name = req.query.metric as string;

		if (!metric_name) {
			res.status(400).json({ error: "metric query parameter is required" });
			return;
		}

		const platform = req.query.platform as string | undefined;
		const location_id = req.query.location as string | undefined;
		const hours_ago = req.query.hours
			? Number.parseInt(req.query.hours as string, 10)
			: 24;

		const results = await timestream.queryTimeSeries({
			metric_name,
			platform,
			location_id,
			hours_ago,
		});

		res.json({
			data: results,
			query: { metric_name, platform, location_id, hours_ago },
		});
	} catch (error) {
		console.error("Error querying time series:", error);
		res.status(500).json({
			error: "Failed to query time series data",
			message: error instanceof Error ? error.message : "Unknown error",
		});
	}
});

/**
 * GET /api/results/locations
 * Get list of unique locations.
 */
router.get("/locations", async (_req, res) => {
	try {
		const locations = await timestream.getLocations();

		res.json({
			data: locations,
		});
	} catch (error) {
		console.error("Error querying locations:", error);
		res.status(500).json({
			error: "Failed to query locations",
			message: error instanceof Error ? error.message : "Unknown error",
		});
	}
});

/**
 * GET /api/results/latest
 * Get latest statistics for all locations and platforms.
 */
router.get("/latest", async (_req, res) => {
	try {
		const results = await timestream.getLatestStats();

		res.json({
			data: results,
		});
	} catch (error) {
		console.error("Error querying latest stats:", error);
		res.status(500).json({
			error: "Failed to query latest statistics",
			message: error instanceof Error ? error.message : "Unknown error",
		});
	}
});

export { router as timestreamRouter };
