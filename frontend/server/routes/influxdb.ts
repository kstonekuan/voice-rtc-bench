/**
 * API routes for querying benchmark results from InfluxDB.
 * Uses Zod validation to ensure type safety and prevent SQL injection.
 */

import type { RequestHandler } from "express";
import { Router } from "express";
import { z } from "zod";
import { InfluxDBClientWrapper } from "../influxdb-client.js";
import {
	AggregatedStatsParamsSchema,
	TimeSeriesParamsSchema,
} from "../validation.js";

const router = Router();

/**
 * Async handler wrapper to eliminate repetitive try/catch blocks.
 * Automatically catches errors and sends appropriate responses.
 */
function asyncHandler(handler: RequestHandler): RequestHandler {
	return async (req, res, next) => {
		try {
			await handler(req, res, next);
		} catch (error) {
			console.error("Route handler error:", error);

			// Handle Zod validation errors
			if (error instanceof z.ZodError) {
				res.status(400).json({
					error: "Invalid request parameters",
					details: error.errors,
				});
				return;
			}

			// Handle generic errors
			res.status(500).json({
				error: "Internal server error",
				message: error instanceof Error ? error.message : "Unknown error",
			});
		}
	};
}

// Initialize InfluxDB client
const influxdb = new InfluxDBClientWrapper({
	url: process.env.INFLUXDB_URL || "",
	token: process.env.INFLUXDB_TOKEN || "",
	org: process.env.INFLUXDB_ORG || "default",
	database: process.env.INFLUXDB_DATABASE || "voice-rtc-benchmarks",
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
router.get(
	"/aggregated",
	asyncHandler(async (req, res) => {
		// Validate query parameters with Zod
		const params = AggregatedStatsParamsSchema.parse({
			platform: req.query.platform,
			location_id: req.query.location,
			hours_ago: req.query.hours,
		});

		const results = await influxdb.queryAggregatedStats(params);

		res.json({
			data: results,
			query: params,
		});
	}),
);

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
router.get(
	"/timeseries",
	asyncHandler(async (req, res) => {
		// Validate query parameters with Zod
		const params = TimeSeriesParamsSchema.parse({
			platform: req.query.platform,
			location_id: req.query.location,
			metric_name: req.query.metric,
			hours_ago: req.query.hours,
		});

		const results = await influxdb.queryTimeSeries(params);

		res.json({
			data: results,
			query: params,
		});
	}),
);

/**
 * GET /api/results/locations
 * Get list of unique locations.
 */
router.get(
	"/locations",
	asyncHandler(async (_req, res) => {
		const locations = await influxdb.getLocations();
		res.json({ data: locations });
	}),
);

/**
 * GET /api/results/latest
 * Get latest statistics for all locations and platforms.
 */
router.get(
	"/latest",
	asyncHandler(async (_req, res) => {
		const results = await influxdb.getLatestStats();
		res.json({ data: results });
	}),
);

export { router as influxdbRouter };
