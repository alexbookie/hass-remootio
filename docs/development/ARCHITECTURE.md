# Architecture Overview

Technical architecture of the Remootio custom component for Home Assistant.

## Directory Structure

```text
custom_components/remootio/
├── __init__.py          # Integration setup and unload
├── manifest.json        # Integration metadata
├── const.py             # Constants (domain, timing, config keys)
├── models.py            # Typed dataclasses and enums for the API protocol
├── api.py               # WebSocket client with encryption and state machine
├── coordinator.py       # Push-based DataUpdateCoordinator[None]
├── config_flow.py       # Config flow (user, reauth, reconfigure, options)
├── cover.py             # Garage door cover entity
├── strings.json         # UI strings
└── translations/
    └── en.json          # English translations
```

## Core Components

### API Client (`api.py`)

The core of the integration. Handles the full WebSocket lifecycle:

- **Connection**: WebSocket to `ws://<host>:8080/`
- **Encryption**: AES-256-CBC + PKCS7 padding + HMAC-SHA256 MAC verification
- **Auth handshake**: AUTH → CHALLENGE → QUERY → HELLO → SERVER_HELLO
- **State machine**: Tracks gate state with client-side inference for opening/closing
- **Background tasks**: Receive loop (dispatches events/responses) and ping loop (keepalive every 60s)

Key class: `RemootioClient`

### Coordinator (`coordinator.py`)

Push-based `DataUpdateCoordinator[None]` — no polling interval.

- Entities are notified via `async_set_updated_data(None)` when the WebSocket client fires callbacks
- Entities read state from `coordinator.client.gate_state`, not `coordinator.data`
- Handles reconnection via `Debouncer` (5s cooldown) on disconnect
- Auth failures during reconnect trigger reauth flow

Key class: `RemootioCoordinator`

### Config Flow (`config_flow.py`)

Flat module with:

- `RemootioConfigFlow`: user setup, reauth, reconfigure
- `RemootioOptionsFlow`: credential updates
- Validation: temporary client performs full handshake, extracts serial for unique ID

### Cover Entity (`cover.py`)

`RemootioCover(CoordinatorEntity, CoverEntity)` with:

- `device_class`: GARAGE
- Dynamic `supported_features` based on current state
- Falls back to TRIGGER when no sensor installed
- Availability tied to WebSocket connection state

## Data Flow

```text
┌─────────────────┐
│  Remootio Device│ ← WebSocket (local, encrypted)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RemootioClient  │ ← Decrypts frames, manages state machine
└────────┬────────┘
         │ callback
         ▼
┌─────────────────┐
│  Coordinator    │ ← async_set_updated_data(None)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cover Entity   │ ← Reads state from client, sends commands
└─────────────────┘
```

## Key Design Decisions

### Push-based, not polling

The Remootio WebSocket API pushes state changes in real-time. The coordinator has no `update_interval` — all updates come from WebSocket events.

### Own API client, not aioremootio

Built a custom client to avoid the `pycryptodome` and `async-class` dependencies. Uses `cryptography` (already in HA) and standard `aiohttp` WebSocket.

### Client-side state inference

The API only reports `open`, `closed`, and `no sensor`. The client infers `opening` and `closing` from relay trigger events. After a stop (relay trigger while moving), state resolves to `open` since the sensor reads "not closed."

### Dynamic supported features

Cover buttons change based on state — Open when closed, Close when open, Stop when moving. This prevents sending relay pulses at inappropriate times.
