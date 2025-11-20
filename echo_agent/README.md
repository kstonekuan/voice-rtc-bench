# Echo Agent

FastAPI-powered echo agent with on-demand room creation for Daily and LiveKit platforms.

## Features

- **On-Demand Room Creation**: Creates temporary rooms via REST API
- **Dual Platform Support**: Handles both Daily and LiveKit simultaneously
- **Pipecat-Style Architecture**: HTTP API for benchmark orchestration
- **Auto-Cleanup**: Echo agents leave when clients disconnect, rooms auto-expire
- **Production Ready**: FastAPI server, error handling, and logging

## Installation

```bash
# Install using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8080

# Daily API Key (for creating rooms)
DAILY_API_KEY=your-daily-api-key-here
DAILY_API_URL=https://api.daily.co/v1

# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Optional: Custom agent names
DAILY_AGENT_NAME=echo-daily
LIVEKIT_AGENT_NAME=echo-livekit

# Optional: Logging
LOG_LEVEL=INFO
```

## Usage

```bash
# Start the echo agent
uv run python main.py
```

The agent will:
1. Start FastAPI server on port 8080
2. Expose `/connect` endpoint for room creation
3. Create Daily rooms and LiveKit tokens on-demand
4. Join Daily rooms dynamically when requested
5. Handle LiveKit rooms via worker pattern
6. Respond to ping messages on both platforms
7. Automatically leave rooms when the last client disconnects

## API Endpoints

### `POST /connect`

Creates temporary rooms for both platforms and returns credentials.

**Response:**
```json
{
  "daily": {
    "room_url": "https://domain.daily.co/benchmark-1234567890",
    "expires_at": 1234567890.0
  },
  "livekit": {
    "server_url": "wss://project.livekit.cloud",
    "room_name": "benchmark-1234567890",
    "token": "eyJhbGc...",
    "expires_at": 1234567890.0
  }
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "echo-agent-api"
}
```

### `GET /rooms`

Lists currently active rooms.

## Platform-Specific Behavior

### Daily
- Creates rooms via REST API using pipecat's DailyRESTHelper
- Rooms auto-expire in 10 minutes
- Agent joins rooms on-demand when created
- Uses Daily's app-message API for ping-pong

### LiveKit
- Generates access tokens with room grants
- Rooms auto-create when first participant joins
- Worker handles all rooms dynamically
- Uses WebRTC data channels for ping-pong

## Message Format

**Ping (Client → Agent):**
```json
{
  "type": "ping",
  "timestamp": 1234567890.123
}
```

**Pong (Agent → Client):**
```json
{
  "type": "pong",
  "client_timestamp": 1234567890.123,
  "server_receive_time": 1234567890.456,
  "server_send_time": 1234567890.789,
  "message_count": 42
}
```

## Deployment

Deploy to any cloud platform supporting Python applications:

```bash
# Using Docker
docker build -t echo-agent .
docker run --env-file .env -p 8080:8080 echo-agent

# Using uv in production
uv run --no-dev python main.py

# Fly.io
fly launch
fly secrets set DAILY_API_KEY="..." LIVEKIT_URL="..." LIVEKIT_API_KEY="..." LIVEKIT_API_SECRET="..."
fly deploy
```

## Architecture

```
┌───────────────────────────────────────────────┐
│           Echo Agent (Cloud)                  │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │  FastAPI Server (Port 8080)             │ │
│  │  • POST /connect (create rooms)         │ │
│  │  • GET /health                          │ │
│  │  • GET /rooms                           │ │
│  └──────────────┬──────────────────────────┘ │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────────────┐    │
│  │  Room Creation & Management          │    │
│  │  • DailyRESTHelper (pipecat)         │    │
│  │  • LiveKit token generation          │    │
│  └──────────┬────────────┬──────────────┘    │
│             │            │                    │
│             ▼            ▼                    │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ Daily       │  │ LiveKit     │            │
│  │ Handler     │  │ Worker      │            │
│  │             │  │             │            │
│  │ • Dynamic   │  │ • Always    │            │
│  │   room join │  │   ready     │            │
│  │ • App msgs  │  │ • Data ch.  │            │
│  └──────┬──────┘  └──────┬──────┘            │
│         │                │                    │
│         └───────┬────────┘                    │
│                 ▼                             │
│         ┌───────────────┐                     │
│         │ Message       │                     │
│         │ Handler       │                     │
│         │ (Shared)      │                     │
│         └───────────────┘                     │
└───────────────────────────────────────────────┘
```
