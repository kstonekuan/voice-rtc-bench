# Benchmark Runner

Python-based benchmark runner for measuring WebRTC latency across Daily and LiveKit platforms. Part of the [Voice RTC Benchmark](../../README.md) project.

> For installation, deployment, and architecture overview, see the [main README](../../README.md).

## Quick Start

```bash
# Benchmark Daily platform
uv run benchmark-runner --platform daily --agent-url "http://localhost:8000"

# Benchmark LiveKit platform
uv run benchmark-runner --platform livekit --agent-url "http://localhost:8001"
```

## CLI Reference

### Required Arguments

- `--platform {daily,livekit}` - Platform to benchmark
- `--agent-url URL` - Echo agent API endpoint

### Optional Arguments

- `--iterations N` - Number of ping-pong iterations (default: from `.env`)
- `--timeout MS` - Timeout in milliseconds (default: from `.env`)
- `--cooldown MS` - Cooldown between pings in milliseconds (default: from `.env`)
- `--location ID` - Location identifier (e.g., "us-west-2", "eu-central-1") (default: from `.env`)
- `--output FILE` - Save results to JSON file
- `--verbose` - Enable verbose logging

### Examples

**Daily with custom settings:**
```bash
uv run benchmark-runner \
  --platform daily \
  --agent-url "http://localhost:8000" \
  --iterations 100 \
  --timeout 5000 \
  --cooldown 100 \
  --location "us-west-2" \
  --output results-daily.json
```

**LiveKit with defaults from .env:**
```bash
uv run benchmark-runner \
  --platform livekit \
  --agent-url "http://localhost:8001"
```

## Benchmark Flow

1. **Connect**: Request room credentials from echo agent via `POST /connect`
2. **Join**: Establish WebRTC connection to the platform
3. **Ping**: Send ping message with client timestamp
4. **Pong**: Receive pong with server timestamps
5. **Calculate**: Compute RTT and one-way latencies
6. **Repeat**: Continue for configured iterations
7. **Analyze**: Calculate statistics (mean, median, P95, P99, jitter)
8. **Store**: Write raw measurements to InfluxDB (if configured)

## Metrics Collected

- **Round-Trip Time (RTT)**: Total time from client → server → client
- **Client-to-Server**: One-way latency estimate
- **Server-to-Client**: One-way latency estimate
- **Packet Loss**: Percentage of pings without pongs
- **Jitter**: Variation in latency (consecutive RTT differences)
- **Percentiles**: P50, P95, P99 for distribution analysis

## Output Format

Results are saved in JSON format when using `--output`:

```json
{
  "platform": "daily",
  "measurements": [
    {
      "round_trip_time": 45.23,
      "client_to_server": 22.14,
      "server_to_client": 23.09,
      "message_number": 1,
      "timestamp": 1234567890.123
    }
  ],
  "statistics": {
    "total_messages": 100,
    "successful_messages": 98,
    "failed_messages": 2,
    "packet_loss_rate": 0.02,
    "mean_rtt": 47.52,
    "median_rtt": 46.11,
    "min_rtt": 42.18,
    "max_rtt": 89.34,
    "std_dev_rtt": 8.76,
    "p50_rtt": 46.11,
    "p95_rtt": 62.45,
    "p99_rtt": 78.21,
    "jitter": 3.45
  },
  "metadata": {
    "start_time": 1234567890.0,
    "end_time": 1234567900.0,
    "duration_ms": 10000.0,
    "iterations": 100,
    "timeout_ms": 5000,
    "platform": "daily",
    "location_id": "us-west-2",
    "run_id": "abc123"
  }
}
```

## Configuration

Environment variables (see `.env.example`):

```bash
# Benchmark Configuration
ITERATIONS=100
TIMEOUT_MS=5000
COOLDOWN_MS=100
LOCATION_ID=us-west-2

# InfluxDB Configuration (optional - for storing results)
INFLUXDB_URL=https://your-instance.timestream-influxdb.region.on.aws:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=default
INFLUXDB_DATABASE=voice-rtc-benchmarks
```

## InfluxDB Integration

When InfluxDB is configured, the benchmark runner automatically:

1. Writes each individual measurement with a unique `run_id`
2. Includes all metadata (platform, location, timestamps)
3. Enables time-series analysis and aggregation in the dashboard

See the main README for InfluxDB setup instructions.
