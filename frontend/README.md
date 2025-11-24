# Frontend Dashboard

Beautiful dashboard for visualizing and comparing Daily and LiveKit WebRTC latency across multiple locations and time periods. Part of the [Voice RTC Benchmark](../README.md) project.

> For project overview, architecture, and deployment instructions, see the [main README](../README.md).

## Quick Start

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your InfluxDB credentials
```

### 3. Start Development Servers

**Option 1: Start both client and server together (recommended):**
```bash
pnpm dev
```

**Option 2: Start separately:**

Terminal 1 - API Server:
```bash
pnpm dev:server
```

Terminal 2 - Frontend:
```bash
pnpm dev:client
```

Open `http://localhost:5173` in your browser.

## Scripts

- `pnpm dev` - Start both client and server in development mode
- `pnpm dev:client` - Start frontend dev server only (port 5173)
- `pnpm dev:server` - Start API server only (port 3001)
- `pnpm build` - Build frontend for production
- `pnpm build:server` - Build API server for production
- `pnpm preview` - Preview production build
- `pnpm start:server` - Start production API server
- `pnpm typecheck` - Run TypeScript type checking
- `pnpm lint` - Lint and auto-fix code with Biome
- `pnpm check` - Run both typecheck and lint

## Architecture

The frontend consists of two components:

### React Dashboard (Client)

- Queries the API server for aggregated metrics
- Filters data by location, platform, and time range
- Visualizes latency distributions and time-series trends
- Compares platforms side-by-side with automatic winner detection

### Express API Server

- Connects to Amazon Timestream for InfluxDB
- Queries raw measurement data
- Calculates statistics (mean, P50, P95, P99, jitter) from raw measurements at query time
- Serves aggregated metrics and time-series data to the React frontend

**Data Flow:**
```
Benchmark Runners → InfluxDB (raw measurements) → API Server (calculates stats) → React Dashboard
```

## API Endpoints

The Express server provides these endpoints:

- `GET /api/results/aggregated` - Get aggregated statistics by platform/location
- `GET /api/results/timeseries` - Get time-series data for charts
- `GET /api/results/locations` - Get list of available locations
- `GET /api/results/latest` - Get most recent benchmark results

Query parameters:
- `platform` - Filter by platform (`daily` or `livekit`)
- `location` - Filter by location ID
- `startTime` / `endTime` - Time range in ISO format

## Configuration

Environment variables (see `.env.example`):

```bash
# Mock Data Mode (for demo without InfluxDB)
VITE_USE_MOCK_DATA=false

# API Configuration
VITE_API_URL=http://localhost:3001  # Frontend → API connection
API_PORT=3001                       # API server port

# InfluxDB Configuration
INFLUXDB_URL=https://your-instance.timestream-influxdb.region.on.aws:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=default
INFLUXDB_DATABASE=voice-rtc-benchmarks
```

## Tech Stack

### Frontend
- React 19 with TypeScript
- Vite (build tool and dev server)
- Recharts (time-series visualization)
- Biome (linting and formatting)

### API Server
- Express HTTP server
- InfluxDB 3 Client for Timestream queries
- Zod for runtime validation and SQL injection prevention
