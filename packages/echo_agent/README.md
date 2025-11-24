# Echo Agent

FastAPI-powered echo agent with on-demand room creation for Daily and LiveKit platforms. Part of the [Voice RTC Benchmark](../../README.md) project.

> For installation, deployment, and architecture overview, see the [main README](../../README.md).

## Quick Start

```bash
# Start Daily echo agent (default port 8000)
uv run python main.py --platform daily

# Start LiveKit echo agent (default port 8001)
uv run python main.py --platform livekit

# Custom port
uv run python main.py --platform daily --port 9000
```

## API Endpoints

### `POST /connect`

Creates temporary rooms for the specified platform and returns credentials.

**Response (Daily):**
```json
{
  "daily": {
    "room_url": "https://domain.daily.co/benchmark-1234567890",
    "expires_at": 1234567890.0
  },
  "livekit": null
}
```

**Response (LiveKit):**
```json
{
  "daily": null,
  "livekit": {
    "server_url": "wss://project.livekit.cloud",
    "room_name": "benchmark-1234567890",
    "token": "eyJhbGc...",
    "expires_at": 1234567890.0
  }
}
```

### `POST /disconnect`

Disconnects from a specific room.

**Request:**
```json
{
  "room_name": "benchmark-1234567890"
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
- Uses Daily's app-message API for ping-pong protocol
- Default port: **8000**

### LiveKit
- Generates access tokens with room grants
- Rooms auto-create when first participant joins
- Worker handles all rooms dynamically
- Uses WebRTC data channels for ping-pong protocol
- Default port: **8001**

## Message Format

The echo agent implements a ping-pong protocol for latency measurement:

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

The timestamps allow the client to calculate:
- **Round-trip latency**: `(now - client_timestamp)`
- **One-way latency estimate**: `(server_receive_time - client_timestamp)`
- **Server processing time**: `(server_send_time - server_receive_time)`

## Configuration

Environment variables (see `.env.example`):

```bash
# Daily API Key (for creating rooms)
DAILY_API_KEY=your-daily-api-key-here

# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Optional
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```
