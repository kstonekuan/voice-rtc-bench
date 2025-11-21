# Voice RTC Benchmark

A distributed benchmarking system for comparing WebRTC voice AI platforms (Daily vs LiveKit) across multiple geographic locations and time periods.

## Overview

This project measures the **network transport baseline latency** of Daily.co and LiveKit by sending ping-pong messages through WebRTC data channels. Results are aggregated in Amazon Timestream for InfluxDB and visualized in a real-time dashboard.

### What You Get

- 🌍 **Distributed Benchmarking**: Deploy runners to multiple locations
- 📊 **Time-Series Data**: Historical metrics stored in Amazon Timestream for InfluxDB
- 📈 **Aggregated Analytics**: Mean, P50, P95, P99, jitter, packet loss over time
- 🎯 **Platform Comparison**: Side-by-side Daily vs LiveKit analysis
- 🎨 **Real-time Dashboard**: Brutalist technical aesthetic with live data
- 🔬 **Reproducible Methodology**: Fair comparison across locations

## Project Structure

```
voice-rtc-bench/
├── packages/
│   ├── echo_agent/            # Python echo agent (Daily + LiveKit)
│   │   ├── src/echo_agent/    # Agent source code
│   │   │   ├── main.py        # Entry point
│   │   │   ├── platforms/     # Platform-specific implementations
│   │   │   └── ...
│   │   └── pyproject.toml
│   ├── benchmark_runner/      # Python CLI for running benchmarks
│   │   ├── src/benchmark_runner/
│   │   │   ├── runners/       # Benchmark clients
│   │   │   ├── main.py        # Entry point
│   │   │   └── ...
│   │   └── pyproject.toml
│   └── shared/                # Shared utilities and types
│       └── pyproject.toml
├── frontend/                  # React dashboard + TypeScript API
│   ├── src/                   # React app (data visualization)
│   ├── server/                # Express API (InfluxDB queries)
│   └── package.json
└── pyproject.toml             # Workspace configuration
```

## Architecture

### Distributed System Flow

```
┌─────────────────────────────────────────────────────────────┐
│       Benchmark Runners (Python CLI - Multi-Region)          │
│                                                              │
│  Location A (us-west-2)    Location B (eu-central-1)        │
│  benchmark-runner CLI      benchmark-runner CLI             │
│         │                          │                         │
│         └──────────┬───────────────┘                         │
│                    │ 1. POST /connect                        │
│                    │ (to specific platform agent)            │
│                    ▼                                         │
├─────────────────────────────────────────────────────────────┤
│            Echo Agents (Cloud - Separate Processes)          │
│                                                              │
│  ┌─────────────────────────┐    ┌─────────────────────────┐  │
│  │ Daily Agent (Port 8000) │    │ LiveKit Agent (Port 8001)│ │
│  │ • POST /connect         │    │ • POST /connect         │  │
│  │ • Creates Daily rooms   │    │ • Creates LiveKit rooms │  │
│  └──────────┬──────────────┘    └──────────┬──────────────┘  │
│             │                          │                     │
│             │ 2. WebRTC Ping-Pong      │                     │
│             ▼                          ▼                     │
│  ┌──────────────────────┐       ┌──────────────────────┐     │
│  │ Daily WebRTC Rooms   │       │ LiveKit WebRTC Rooms │     │
│  └──────────┬───────────┘       └──────────┬───────────┘     │
│             │                          │                     │
│             │ 3. Write results         │                     │
│             ▼                          ▼                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │          Amazon Timestream for InfluxDB 3           │     │
│  └──────────────────────────┬──────────────────────────┘     │
│                             │ 4. Query metrics               │
│                             ▼                                │
│  ┌─────────────────────────────────────────────────────┐     │
│  │             TypeScript API Server                   │     │
│  └──────────────────────────┬──────────────────────────┘     │
│                             │ 5. Visualize                   │
│                             ▼                                │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                React Dashboard                      │     │
└─────────────────────────────────────────────────────────────┘
```

### How It Works

2. **Benchmark Runners** (scheduled or manual) call `POST /connect` API endpoint on the respective agent
3. **Echo Agents** create temporary rooms and return credentials
4. **Benchmark Runners** connect to rooms and run ping-pong latency tests
5. **Results** are written to Amazon Timestream for InfluxDB for time-series storage
6. **Echo agents automatically leave** the room when the benchmark client disconnects
7. **Rooms auto-expire** after 10 minutes (Daily) or when empty (LiveKit)
8. **Dashboard** queries InfluxDB and visualizes metrics with filters

## Quick Start

### Prerequisites

- **Python 3.11+** with `uv` installed
- **Node.js 18+** with `pnpm` installed
- **Daily account** (free tier works)
- **LiveKit Cloud account** (free tier works)
- **AWS account** with Amazon Timestream for InfluxDB access (for production)

### Step 1: Set Up Platform Accounts

**Daily.co:**
1. Sign up at [daily.co](https://www.daily.co/)
2. Go to [Developers](https://dashboard.daily.co/developers)
3. Get your **API key** (for creating rooms programmatically)

**LiveKit:**
1. Sign up at [livekit.io](https://livekit.io/)
2. Create a project at [cloud.livekit.io](https://cloud.livekit.io)
3. Get your **server URL**: `wss://your-project.livekit.cloud`
4. Generate **API key** and **API secret** from project settings

**Amazon Timestream for InfluxDB (Optional - for production):**
1. Set up AWS account
2. Create an Amazon Timestream for InfluxDB 3 instance in your region
3. Get your InfluxDB endpoint URL from the AWS console
4. Get your authentication token from AWS Secrets Manager
5. Create database/bucket: `voice-rtc-benchmarks`

### Step 2: Start Echo Agents

The echo agents run as separate processes. You can run them in separate terminals.

**Daily Agent (Port 8000):**
```bash
# From root directory
uv run echo-agent --platform daily
```

**LiveKit Agent (Port 8001):**
```bash
# From root directory
uv run echo-agent --platform livekit
```

You should see output indicating the server is running on the respective port.

### Step 3: Run Benchmarks

The benchmark runner automatically requests room credentials from the echo agent.

**Run Daily benchmark:**

```bash
# From root directory
uv run benchmark-runner \
  --platform daily \
  --agent-url "http://localhost:8000" \
  --iterations 100 \
  --location "us-west-2"
```

**Run LiveKit benchmark:**

```bash
uv run benchmark-runner \
  --platform livekit \
  --agent-url "http://localhost:8001" \
  --iterations 100 \
  --location "us-west-2"
```

**Run both platforms (sequentially):**

```bash
# Run Daily
uv run benchmark-runner --platform daily --agent-url "http://localhost:8000" --location "us-west-2"

# Run LiveKit
uv run benchmark-runner --platform livekit --agent-url "http://localhost:8001" --location "us-west-2"
```

**With InfluxDB integration:**

```bash
# Results automatically written to InfluxDB if configured in .env
uv run benchmark-runner \
  --platform daily \
  --agent-url "http://localhost:8000" \
  --location "us-west-2"
```

The benchmark runner will:
1. Request room credentials from the echo agent
2. Connect to the platform room
3. Run ping-pong latency tests
4. Write results to InfluxDB (if configured)
5. Echo agent automatically disconnects when the benchmark completes
6. Rooms auto-expire after 10 minutes

### Step 4: View Results in Dashboard

**Terminal 1 - API Server:**
```bash
cd frontend
pnpm install
cp .env.example .env
# Edit .env and add InfluxDB credentials
pnpm dev:api
```

**Terminal 2 - Frontend:**
```bash
cd frontend
pnpm dev
```

Open `http://localhost:5173` in your browser.

The dashboard shows:
- Aggregated metrics from all benchmark runs
- Filters by location, platform, and time range
- Min/max ranges for each metric
- Platform comparison across locations

## Deployment

### Echo Agents

Deploy separate services for Daily and LiveKit agents.

**Fly.io (Daily Agent):**
```bash
cd packages/echo_agent
fly launch --name voice-rtc-daily
fly secrets set DAILY_API_KEY="..."
# Update fly.toml to run: echo-agent --platform daily
fly deploy
```

**Fly.io (LiveKit Agent):**
```bash
cd packages/echo_agent
fly launch --name voice-rtc-livekit
fly secrets set LIVEKIT_URL="..." LIVEKIT_API_KEY="..." LIVEKIT_API_SECRET="..."
# Update fly.toml to run: echo-agent --platform livekit
fly deploy
```

**Railway / Render:**
- Create two services from the same repo.
- Service 1 (Daily): Command `uv run echo-agent --platform daily`
- Service 2 (LiveKit): Command `uv run echo-agent --platform livekit`

### Benchmark Runners

Deploy to multiple locations using:

**AWS Lambda + EventBridge:**
- Package `benchmark-runner/` as Lambda function
- Trigger on schedule (e.g., hourly)
- Set `LOCATION_ID` per region

**Cron Jobs:**
```bash
# Run every hour from root directory
0 * * * * cd /path/to/voice-rtc-bench && uv run benchmark-runner both ... --location "us-west-2"
```

**Docker:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --all-packages
CMD ["uv", "run", "benchmark-runner", "both", ...]
```

### Frontend + API

**Vercel / Netlify:**
- Deploy frontend as static site
- Deploy API as serverless functions

**Single Server:**
```bash
cd frontend
pnpm build
pnpm build:api
# Serve dist/ with nginx
# Run API server: node dist/server/index.js
```

## Tech Stack

| Component        | Technology                                            |
| ---------------- | ----------------------------------------------------- |
| Echo Agent       | Python 3.11+ with `daily-python` and `livekit-agents` |
| Benchmark Runner | Python with `typer`, `pydantic`, `influxdb3-python`   |
| API Server       | TypeScript + Express + InfluxDB 3 Client              |
| Frontend         | React 19 + TypeScript + Vite                          |
| Styling          | Custom CSS with brutalist aesthetic                   |
| Time-Series DB   | Amazon Timestream for InfluxDB 3                      |
| Type Checking    | `ty` (Python), `tsc` (TypeScript)                     |
| Linting          | `ruff` (Python), `biome` (TypeScript)                 |
| Package Managers | `uv` (Python), `pnpm` (Node.js)                       |

## What This Measures

- **Round-Trip Time (RTT)**: Client → Server → Client latency
- **Jitter**: Variation in consecutive message latencies
- **Packet Loss**: Percentage of timed-out messages
- **Percentiles**: P50 (median), P95, P99 distributions

**Important Note**: This measures the network "speed limit". Actual voice AI latency will be higher due to:
- Audio codec overhead (5-20ms)
- Jitter buffers (20-200ms)
- STT/LLM/TTS processing time (100-1000ms+)

This provides the **infrastructure baseline** for voice AI applications.

## Results Interpretation

### What Makes a Good Result?

- **Mean RTT < 100ms**: Excellent for voice AI
- **P99 RTT < 200ms**: Consistent, low-jitter performance
- **Packet Loss < 1%**: Reliable transport
- **Jitter < 20ms**: Smooth, predictable latency

### Comparing Platforms

The dashboard shows which platform has lower latency for each metric across locations. Lower is better for RTT, jitter, and packet loss.

**Remember**: This is the baseline. Add 100-300ms for typical voice AI processing overhead.

## CLI Reference

### Daily Benchmark

```bash
# Run from root directory
uv run benchmark-runner daily \
  --room-url URL \           # Daily room URL (required)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --influxdb-url URL \       # InfluxDB endpoint URL (optional)
  --influxdb-token TOKEN \   # InfluxDB auth token (optional)
  --influxdb-org ORG \       # InfluxDB organization (optional)
  --influxdb-database NAME \ # InfluxDB database (optional)
  --verbose                  # Enable debug logging
```

### LiveKit Benchmark

```bash
# Run from root directory
uv run benchmark-runner livekit \
  --server-url URL \         # LiveKit server URL (required)
  --token TOKEN \            # Access token (required)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --influxdb-url URL \       # InfluxDB endpoint URL (optional)
  --influxdb-token TOKEN \   # InfluxDB auth token (optional)
  --influxdb-org ORG \       # InfluxDB organization (optional)
  --influxdb-database NAME \ # InfluxDB database (optional)
  --verbose                  # Enable debug logging
```

### Both Platforms (Parallel)

```bash
# Run from root directory
uv run benchmark-runner both \
  --daily-agent-url URL \    # Daily Agent API URL (optional)
  --livekit-agent-url URL \  # LiveKit Agent API URL (optional)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --influxdb-url URL \       # InfluxDB endpoint URL (optional)
  --influxdb-token TOKEN \   # InfluxDB auth token (optional)
  --influxdb-org ORG \       # InfluxDB organization (optional)
  --influxdb-database NAME \ # InfluxDB database (optional)
  --verbose                  # Enable debug logging
```

## API Reference

### GET /api/results/aggregated

Get aggregated statistics over time period.

**Query Parameters:**
- `platform` - Filter by platform: `daily` or `livekit` (optional)
- `location` - Filter by location ID (optional)
- `hours` - Hours to look back (default: 24)

**Response:**
```json
{
  "data": [
    {
      "platform": "daily",
      "location_id": "us-west-2",
      "metric_name": "mean_rtt",
      "avg_value": 45.23,
      "min_value": 42.18,
      "max_value": 52.34,
      "sample_count": 24,
      "time_period": "2025-11-19T10:00:00Z"
    }
  ]
}
```

### GET /api/results/timeseries

Get time-series data for a specific metric.

**Query Parameters:**
- `metric` - Metric name (required): `mean_rtt`, `p95_rtt`, `p99_rtt`, `jitter`, `packet_loss_rate`
- `platform` - Filter by platform (optional)
- `location` - Filter by location ID (optional)
- `hours` - Hours to look back (default: 24)

### GET /api/results/locations

Get list of unique locations.

**Response:**
```json
{
  "data": ["us-west-2", "eu-central-1", "ap-southeast-1"]
}
```

### GET /api/results/latest

Get latest statistics for all locations and platforms.

## Development

### Code Quality

All projects use linting and type checking:

**Python (from root directory):**
```bash
uv run ruff check --fix     # Lint and fix
uv run ruff format          # Format
uv run ty check             # Type check
```

**TypeScript (frontend):**
```bash
pnpm check                # Lint + type check
pnpm lint                 # Biome linting
pnpm typecheck            # TypeScript checking
```

### Project Configuration

All Python projects use:
- **ruff** for linting and formatting (line length: 100)
- **ty** for type checking
- **uv** for dependency management

Frontend uses:
- **biome** for linting and formatting
- **TypeScript** for type checking
- **pnpm** for dependency management

## Design Philosophy

The dashboard embraces a **"Technical Performance Lab"** aesthetic:

- **Brutalist minimalism** with precision focus
- **Monospace typography** (Azeret Mono) for technical authenticity
- **Platform-specific colors**: Cyan (#00d4ff) for Daily, Lime (#00ff88) for LiveKit
- **Scan-line effects** and noise texture for "monitoring equipment" feel
- **Time-series data visualization** with location filtering
- **No-nonsense information hierarchy**

## Future Enhancements

- **Audio loopback testing**: Measure actual audio path latency (beyond data channels)
- **Full STT→LLM→TTS pipeline**: End-to-end voice AI latency
- **Network condition simulation**: Test under various network conditions
- **Additional platforms**: Add support for Agora, Twilio, etc.
- **Advanced analytics**: Correlation analysis, anomaly detection
- **Alerting**: Slack/email notifications for degraded performance

## Contributing

Contributions welcome! This is an open-source benchmarking tool for the voice AI community.

## License

MIT