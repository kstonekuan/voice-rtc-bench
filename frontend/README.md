# Voice RTC Benchmark Frontend

Beautiful, real-time benchmarking dashboard for comparing Daily and LiveKit WebRTC latency.

## Features

- **Split-screen comparison** of Daily vs LiveKit performance
- **Real-time latency visualization** as benchmarks run
- **Comprehensive statistics**: Mean, P50, P95, P99, jitter, packet loss
- **Head-to-head comparison** with automatic winner detection
- **Brutalist technical aesthetic** with monospace fonts and scan-line effects

## Quick Start

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Start Development Server

```bash
pnpm dev
```

### 3. Configure Benchmarks

In the UI, enter:

- **Daily Room URL**: Your Daily.co room URL (e.g., `https://your-domain.daily.co/room-name`)
- **LiveKit Server URL**: Your LiveKit server WebSocket URL (e.g., `wss://your-project.livekit.cloud`)
- **LiveKit Token**: A valid LiveKit access token for the room
- **Iterations**: Number of ping-pong messages to send (default: 100)
- **Timeout**: Maximum wait time for responses in milliseconds (default: 5000)

### 4. Run Benchmarks

1. Make sure both echo agents are running (see `agents/` directory)
2. Click "Run Benchmark" to start both tests simultaneously
3. Watch real-time results as they stream in
4. View head-to-head comparison when complete

## Architecture

This is a pure client-side React application that:

1. Connects directly to Daily and LiveKit rooms via their browser SDKs
2. Sends ping messages via data channels
3. Measures round-trip time when receiving pong responses
4. Calculates comprehensive statistics
5. Displays results in a stunning technical interface

## Scripts

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm preview` - Preview production build
- `pnpm typecheck` - Run TypeScript type checking
- `pnpm lint` - Lint code with Biome
- `pnpm format` - Format code with Biome

## Design Philosophy

The UI embraces a **"Technical Performance Lab"** aesthetic:

- **Brutalist minimalism** with precision focus
- **Monospace typography** (Azeret Mono) for technical authenticity
- **Platform-specific accent colors**: Cyan for Daily, Lime for LiveKit
- **Scan-line effects** and subtle noise texture for "monitoring equipment" feel
- **Real-time data visualization** with animated progress indicators
- **No-nonsense information hierarchy**

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Daily SDK** (`@daily-co/daily-js`) - Daily.co WebRTC
- **LiveKit SDK** (`livekit-client`) - LiveKit WebRTC
- **Biome** - Linting and formatting

## What This Measures

This benchmark measures **network transport baseline latency** using WebRTC data channels:

- **Round-Trip Time (RTT)**: Time for message to travel client → server → client
- **Jitter**: Variation in latency between consecutive messages
- **Packet Loss**: Percentage of messages that timed out
- **Percentiles**: P50 (median), P95, P99 for understanding distribution

**Important Note**: This represents the network "speed limit" - actual voice AI latency will be higher due to:
- Audio codec overhead (5-20ms)
- Jitter buffers (20-200ms)
- STT/LLM/TTS processing time

## License

MIT
