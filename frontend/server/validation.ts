/**
 * Zod validation schemas for API request parameters.
 * Prevents SQL injection and ensures type safety.
 */

import { z } from "zod";

// Valid metric names that can be queried
const VALID_METRICS = [
	"mean_rtt",
	"median_rtt",
	"p50_rtt",
	"p95_rtt",
	"p99_rtt",
	"min_rtt",
	"max_rtt",
	"std_dev_rtt",
	"jitter",
	"packet_loss_rate",
	"total_messages",
	"successful_messages",
	"failed_messages",
] as const;

// Platform must be one of these exact values
export const PlatformSchema = z.enum(["daily", "livekit"]).optional();

// Location ID must be alphanumeric with hyphens/underscores
export const LocationIdSchema = z
	.string()
	.regex(/^[a-zA-Z0-9_-]+$/, "Location ID must be alphanumeric")
	.min(1)
	.max(100)
	.optional();

// Metric name must be from the allowed list
export const MetricNameSchema = z.enum(VALID_METRICS);

// Hours must be a positive integer with reasonable bounds
export const HoursSchema = z.coerce
	.number()
	.int()
	.positive()
	.min(1)
	.max(8760) // Max 1 year
	.default(24);

// Query parameters for aggregated stats endpoint
export const AggregatedStatsParamsSchema = z.object({
	platform: PlatformSchema,
	location_id: LocationIdSchema,
	hours_ago: HoursSchema,
});

// Query parameters for time series endpoint
export const TimeSeriesParamsSchema = z.object({
	platform: PlatformSchema,
	location_id: LocationIdSchema,
	metric_name: MetricNameSchema,
	hours_ago: HoursSchema,
});

// Type exports for use in other files
export type Platform = z.infer<typeof PlatformSchema>;
export type LocationId = z.infer<typeof LocationIdSchema>;
export type MetricName = z.infer<typeof MetricNameSchema>;
export type AggregatedStatsParams = z.infer<typeof AggregatedStatsParamsSchema>;
export type TimeSeriesParams = z.infer<typeof TimeSeriesParamsSchema>;

// Export the list of valid metrics
export const VALID_METRIC_NAMES = VALID_METRICS;
