# Unified Echo Agent

A single deployment that runs both Daily and LiveKit echo agents concurrently.

## Features

- **Dual Platform Support**: Runs Daily and LiveKit handlers in parallel
- **Shared Logic**: Common message handling for consistent behavior
- **Flexible Configuration**: Enable/disable platforms via environment variables
- **Production Ready**: Proper error handling, logging, and lifecycle management

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
# Enable Daily (optional)
DAILY_ROOM_URL=https://your-domain.daily.co/room-name

# Enable LiveKit (optional)
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Optional: Custom agent names
DAILY_AGENT_NAME=unified-daily-echo
LIVEKIT_AGENT_NAME=unified-livekit-echo

# Optional: Logging
LOG_LEVEL=INFO
```

## Usage

```bash
# Run the unified agent
uv run python main.py

# Or with pip
python main.py
```

The agent will:
1. Check which platforms are configured
2. Start enabled platform handlers concurrently
3. Listen for ping messages on both platforms
4. Respond with pong messages containing timing information

## Platform-Specific Behavior

### Daily
- Uses Daily's app-message API
- Joins room directly via room URL
- Synchronous event handlers

### LiveKit
- Uses WebRTC data channels
- Worker-based architecture (auto-scales)
- Requires API credentials for authentication

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

Deploy to AWS, GCP, or any platform supporting Python applications:

```bash
# Using Docker (example)
docker build -t unified-echo-agent .
docker run --env-file .env unified-echo-agent

# Using uv in production
uv run --no-dev python main.py
```

## Architecture

```
┌─────────────────────────────────────┐
│   Unified Echo Agent (Python)       │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ Daily        │  │ LiveKit     │ │
│  │ Handler      │  │ Handler     │ │
│  │              │  │             │ │
│  │ - Joins room │  │ - Worker    │ │
│  │ - App msgs   │  │ - Data ch.  │ │
│  └──────┬───────┘  └──────┬──────┘ │
│         │                 │         │
│         └────┬────────────┘         │
│              │                      │
│      ┌───────▼────────┐             │
│      │ MessageHandler │             │
│      │ (Shared Logic) │             │
│      └────────────────┘             │
└─────────────────────────────────────┘
```
