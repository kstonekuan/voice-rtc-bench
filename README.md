# Voice RTC Benchmark

A distributed benchmarking system for comparing WebRTC voice AI platforms (Daily vs LiveKit) across multiple geographic locations and time periods.

## Overview

This project measures the **network transport baseline latency** of Daily.co and LiveKit by sending ping-pong messages through WebRTC data channels. Results are aggregated in Amazon Timestream and visualized in a real-time dashboard.

### What You Get

- 🌍 **Distributed Benchmarking**: Deploy runners to multiple locations
- 📊 **Time-Series Data**: Historical metrics stored in Amazon Timestream
- 📈 **Aggregated Analytics**: Mean, P50, P95, P99, jitter, packet loss over time
- 🎯 **Platform Comparison**: Side-by-side Daily vs LiveKit analysis
- 🎨 **Real-time Dashboard**: Brutalist technical aesthetic with live data
- 🔬 **Reproducible Methodology**: Fair comparison across locations

## Project Structure

```
voice-rtc-bench/
├── echo-agent/                # Python echo agent (Daily + LiveKit)
│   ├── main.py                # Agent + FastAPI server
│   ├── api.py                 # Room creation endpoints
│   └── pyproject.toml
├── benchmark-runner/          # Python CLI for running benchmarks
│   └── src/
│       ├── runners/           # Daily and LiveKit benchmark clients
│       ├── timestream.py      # AWS Timestream integration
│       └── cli.py             # CLI interface
└── frontend/                  # React dashboard + TypeScript API
    ├── src/                   # React app (data visualization)
    └── server/                # Express API (Timestream queries)
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
└────────────────────┼─────────────────────────────────────────┘
                     ▼
           ┌─────────────────────────────────┐
           │ Unified Echo Agent (Cloud)      │
           │ ─────────────────────────────── │
           │ FastAPI Server (Port 8080)      │
           │  • POST /connect                │
           │  • Creates temporary rooms      │
           │  • Returns credentials          │
           │ ─────────────────────────────── │
           │ Daily Handler (on-demand)       │
           │ LiveKit Worker (dynamic)        │
           └──────────┬──────────────────────┘
                      │ 2. WebRTC Ping-Pong
                      ▼
           ┌──────────────────────────────────┐
           │  WebRTC Rooms (Temporary)        │
           │  • Echo agents leave when        │
           │    client disconnects            │
           │  • Daily: Auto-expires (10 min)  │
           │  • LiveKit: Auto-cleanup         │
           └──────────┬───────────────────────┘
                      │ 3. Write results
                      ▼
           ┌─────────────────┐
           │  Amazon         │
           │  Timestream     │
           │  (Time-Series)  │
           └────────┬────────┘
                    │ 4. Query metrics
                    ▼
           ┌────────────────────────────────┐
           │  TypeScript API Server         │
           │  Express + AWS SDK             │
           │  /api/results/*                │
           └────────┬───────────────────────┘
                    │ 5. Visualize
                    ▼
           ┌────────────────┐
           │  React         │
           │  Dashboard     │
           │  (Vite)        │
           └────────────────┘
```

### How It Works

1. **Echo Agent** runs continuously in the cloud with FastAPI server on port 8080
2. **Benchmark Runners** (scheduled or manual) call `POST /connect` API endpoint
3. **Echo Agent** creates temporary rooms for both platforms and returns credentials
4. **Benchmark Runners** connect to rooms and run ping-pong latency tests
5. **Results** are written to Amazon Timestream for time-series storage
6. **Echo agents automatically leave** the room when the benchmark client disconnects
7. **Rooms auto-expire** after 10 minutes (Daily) or when empty (LiveKit)
8. **Dashboard** queries Timestream and visualizes metrics with filters

## Quick Start

### Prerequisites

- **Python 3.11+** with `uv` installed
- **Node.js 18+** with `pnpm` installed
- **Daily account** (free tier works)
- **LiveKit Cloud account** (free tier works)
- **AWS account** with Timestream access (for production)

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

**AWS Timestream (Optional - for production):**
1. Set up AWS account
2. Enable Timestream in your region
3. Create database: `voice-rtc-benchmarks`
4. Create table: `latency_measurements`
5. Get AWS credentials (access key ID + secret)

### Step 2: Start Echo Agent

The echo agent runs as a FastAPI server that creates rooms on-demand:

```bash
cd echo-agent
uv sync
cp .env.example .env
```

Edit `.env` and configure:
```bash
# Daily API key for creating rooms
DAILY_API_KEY=your-daily-api-key-here

# LiveKit credentials
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# API server configuration
API_HOST=0.0.0.0
API_PORT=8080
```

Start the agent:
```bash
uv run python main.py
```

You should see:
```
========================================================================
🎯 Unified Echo Agent with On-Demand Room Creation
========================================================================
Daily API:   ✅ Enabled
LiveKit:     ✅ Enabled
API Server:  ✅ Running on port 8080
========================================================================
✅ API server started on http://0.0.0.0:8080
📍 Endpoints: POST /connect, GET /health, GET /rooms
```

### Step 3: Run Benchmarks

The benchmark runner automatically requests room credentials from the echo agent:

```bash
cd benchmark-runner
uv sync

# Run benchmarks on both platforms (recommended)
uv run python main.py both \
  --echo-agent-url "http://localhost:8080" \
  --iterations 100 \
  --location "us-west-2"
```

**With Timestream integration:**

```bash
uv run python main.py both \
  --echo-agent-url "http://localhost:8080" \
  --location "us-west-2" \
  --ts-database "voice-rtc-benchmarks" \
  --ts-table "latency_measurements"
```

The benchmark runner will:
1. Request room credentials from the echo agent
2. Connect to both Daily and LiveKit rooms
3. Run ping-pong latency tests
4. Write results to Timestream
5. Echo agents automatically leave when the client disconnects
6. Rooms auto-expire after 10 minutes

### Step 4: View Results in Dashboard

**Terminal 1 - API Server:**
```bash
cd frontend
pnpm install
cp .env.example .env
# Edit .env and add AWS credentials + Timestream config
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

### Unified Echo Agent

Deploy to any Python hosting platform:

**Fly.io:**
```bash
cd echo-agent
fly launch
fly secrets set DAILY_API_KEY="..." LIVEKIT_URL="..." LIVEKIT_API_KEY="..." LIVEKIT_API_SECRET="..."
fly deploy
```

**Railway / Render:**
- Use `Dockerfile` or `uv run python main.py`
- Set environment variables via dashboard

### Benchmark Runners

Deploy to multiple locations using:

**AWS Lambda + EventBridge:**
- Package `benchmark-runner/` as Lambda function
- Trigger on schedule (e.g., hourly)
- Set `LOCATION_ID` per region

**Cron Jobs:**
```bash
# Run every hour
0 * * * * cd /path/to/benchmark-runner && uv run python main.py both ... --location "us-west-2"
```

**Docker:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY benchmark-runner/ .
RUN pip install uv && uv sync
CMD ["uv", "run", "python", "main.py", "both", ...]
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
| Benchmark Runner | Python with `typer`, `pydantic`, `boto3`              |
| API Server       | TypeScript + Express + AWS SDK                        |
| Frontend         | React 19 + TypeScript + Vite                          |
| Styling          | Custom CSS with brutalist aesthetic                   |
| Time-Series DB   | Amazon Timestream                                     |
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
uv run python main.py daily \
  --room-url URL \           # Daily room URL (required)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --ts-database NAME \       # Timestream database (optional)
  --ts-table NAME \          # Timestream table (optional)
  --ts-region REGION \       # AWS region (default: us-west-2)
  --verbose                  # Enable debug logging
```

### LiveKit Benchmark

```bash
uv run python main.py livekit \
  --server-url URL \         # LiveKit server URL (required)
  --token TOKEN \            # Access token (required)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --ts-database NAME \       # Timestream database (optional)
  --ts-table NAME \          # Timestream table (optional)
  --ts-region REGION \       # AWS region (default: us-west-2)
  --verbose                  # Enable debug logging
```

### Both Platforms (Parallel)

```bash
uv run python main.py both \
  --daily-room URL \         # Daily room URL (required)
  --livekit-url URL \        # LiveKit server URL (required)
  --livekit-token TOKEN \    # LiveKit access token (required)
  --iterations N \           # Number of pings (default: 100)
  --timeout MS \             # Timeout in ms (default: 5000)
  --cooldown MS \            # Cooldown between pings (default: 100)
  --location ID \            # Location identifier (optional)
  --output FILE \            # Save JSON results (optional)
  --ts-database NAME \       # Timestream database (optional)
  --ts-table NAME \          # Timestream table (optional)
  --ts-region REGION \       # AWS region (default: us-west-2)
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

**Python (echo-agent + benchmark-runner):**
```bash
uvx ruff check .          # Lint
uvx ruff format .         # Format
uvx ty check .            # Type check
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