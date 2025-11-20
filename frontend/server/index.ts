/**
 * API server for serving benchmark results from Amazon Timestream for InfluxDB.
 */

import cors from "cors";
import dotenv from "dotenv";
import express from "express";
import { influxdbRouter } from "./routes/influxdb.js";

dotenv.config();

const app = express();
const port = Number.parseInt(process.env.API_PORT || "3001", 10);

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use("/api/results", influxdbRouter);

// Health check
app.get("/health", (_req, res) => {
	res.json({ status: "ok" });
});

// Start server
app.listen(port, () => {
	console.log(`📡 API server listening on port ${port}`);
	console.log(`   Health: http://localhost:${port}/health`);
	console.log(`   Results: http://localhost:${port}/api/results`);
});
