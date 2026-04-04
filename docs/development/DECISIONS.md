# Design Decisions

## Own WebSocket Client vs aioremootio

**Decision:** Build a custom `RemootioClient` instead of wrapping `aioremootio`.

**Rationale:**
- `aioremootio` depends on `pycryptodome` and `async-class` — unnecessary dependencies
- `cryptography` is already bundled with Home Assistant
- Custom client uses standard `aiohttp` WebSocket (HA convention)
- Full control over state machine and reconnection logic

## Push-based Coordinator (no polling)

**Decision:** Use `DataUpdateCoordinator[None]` with no `update_interval`.

**Rationale:**
- Remootio pushes state changes via WebSocket in real-time
- Polling would be redundant and wasteful (device only supports 1 connection)
- Follows the Shelly RPC coordinator pattern for push-based integrations
- Entities read state from the client, not `coordinator.data`

## Client-side State Inference

**Decision:** Infer `opening`/`closing` states on the client side.

**Rationale:**
- The Remootio API only reports `open`, `closed`, and `no sensor`
- Garage door openers need transitional states for proper UX
- `opening` is inferred when relay triggers from `closed` (brief — sensor flips to `open` almost immediately)
- `closing` is inferred when relay triggers from `open` (held until sensor confirms `closed`)
- Relay trigger during a transitional state = stop → resolves to `open`

## Dynamic Supported Features

**Decision:** `supported_features` is a property, not a class attribute.

**Rationale:**
- Remootio has a single relay — it's the same physical action regardless of direction
- Showing all three buttons (open/close/stop) at once is misleading
- Dynamic features prevent sending relay pulses at inappropriate times
- Stop is only relevant while the door is moving

## Flat Module Structure

**Decision:** Single files instead of packages (e.g. `coordinator.py` not `coordinator/`).

**Rationale:**
- Integration is focused — one device type, one entity platform
- Each module is under 500 lines
- Avoids unnecessary abstraction layers from the blueprint template
- Easier to navigate and maintain
