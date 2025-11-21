# Benchmark Runner

Python-based benchmark runner for measuring WebRTC latency across Daily and LiveKit platforms. Designed for distributed deployment to multiple geographic locations.

## Features

- **Dual Platform Support**: Benchmark both Daily and LiveKit
- **Distributed Deployment**: Deploy to multiple regions for comprehensive testing
- **Amazon Timestream Integration**: Store results in time-series database
- **CLI Interface**: Easy-to-use command-line tool with rich output
- **Flexible Configuration**: Environment variables and CLI arguments

## Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Usage

### Daily Benchmark

```bash
uv run python main.py daily \
  --room-url "https://your-domain.daily.co/room" \
  --iterations 100 \
  --timeout 5000 \
  --location "us-west-2" \
  --output results-daily.json
```

### LiveKit Benchmark

```bash
uv run python main.py livekit \
  --server-url "wss://your-server.livekit.cloud" \
  --token "your-access-token" \
  --iterations 100 \
  --timeout 5000 \
  --location "us-west-2" \
  --output results-livekit.json
```

### Both Platforms (Parallel)

```bash
uv run python main.py both \
  --daily-room "https://your-domain.daily.co/room" \
  --livekit-url "wss://your-server.livekit.cloud" \
  --livekit-token "your-token" \
  --iterations 100 \
  --location "us-west-2" \
  --output results-both.json
```

## CLI Options

### Common Options

- `--iterations, -n`: Number of ping-pong iterations (default: 100)
- `--timeout, -t`: Timeout in milliseconds (default: 5000)
- `--cooldown, -c`: Cooldown between pings in ms (default: 100)
- `--location, -l`: Location identifier (e.g., "us-west-2", "eu-central-1")
- `--output, -o`: Save results to JSON file
- `--verbose, -v`: Enable verbose logging

### Daily Command

- `--room-url, -r`: Daily room URL (required)

### LiveKit Command

- `--server-url, -s`: LiveKit server URL (required)
- `--token, -t`: LiveKit access token (required)

### Both Command

- `--daily-room`: Daily room URL (required)
- `--livekit-url`: LiveKit server URL (required)
- `--livekit-token`: LiveKit access token (required)

## Architecture

```
benchmark-runner/
├── src/
│   ├── types.py          # Pydantic models
│   ├── stats.py          # Statistical calculations
│   ├── cli.py            # CLI interface
│   ├── timestream.py     # AWS Timestream integration
│   └── runners/
│       ├── daily.py      # Daily benchmark runner
│       └── livekit.py    # LiveKit benchmark runner
├── main.py               # Entry point
└── pyproject.toml        # Dependencies
```

## Benchmark Flow

1. **Connect**: Establish WebRTC connection to platform
2. **Ping**: Send ping message with client timestamp
3. **Pong**: Receive pong with server timestamps
4. **Calculate**: Compute RTT and one-way latencies
5. **Repeat**: Continue for configured iterations
6. **Analyze**: Calculate statistics (mean, median, P95, P99, jitter)
7. **Store**: Save results to Timestream (if configured)

## Metrics Collected

- **Round-Trip Time (RTT)**: Total time from client → server → client
- **Client-to-Server**: One-way latency estimate
- **Server-to-Client**: One-way latency estimate
- **Packet Loss**: Percentage of pings without pongs
- **Jitter**: Variation in latency (consecutive RTT differences)
- **Percentiles**: P50, P95, P99 for distribution analysis

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv sync --no-dev

CMD ["uv", "run", "python", "main.py", "both", ...]
```

### Scheduled Runs (Cron)

```bash
# Run benchmark every hour
0 * * * * cd /path/to/benchmark-runner && uv run python main.py both ... >> /var/log/benchmark.log 2>&1
```

### AWS Lambda

Package with dependencies and trigger on schedule using EventBridge.

## Output Format

Results are saved in JSON format:

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
    "room_url": "https://...",
    "location_id": "us-west-2"
  }
}
```

## Timestream Integration

See `src/timestream.py` for integration with Amazon Timestream for storing benchmark results across multiple locations and time periods.
