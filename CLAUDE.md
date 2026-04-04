# Integration: Remootio

## What This Does
Integrates Remootio smart garage door openers with Home Assistant via local WebSocket API.
Exposes: cover entity (garage door) with open/close/stop and real-time state push updates.
Supports Remootio 1 and Remootio 2 devices.

## API Details
- Protocol: WebSocket (local network only, no cloud relay)
- Connection URL: `ws://<host>:8080/`
- Auth: API Auth Key (64-char hex) + API Secret Key (64-char hex), obtained from Remootio mobile app
- Encryption: AES-128-CBC with PKCS7 padding + HMAC-SHA256 for MAC verification
- String encoding: Latin-1
- Max concurrent connections: 1
- API versions: v1 (fw 1.00-2.20), v2 (fw 2.21+), v3 (fw 2.24+)
- Docs: https://github.com/remootio/remootio-api-documentation
- iot_class: local_push

### mDNS Discovery
- Service type: `_remootio._tcp`
- Instance name: Device serial number
- Hostname format: `remootio_<serial_number>.local:8080`

### Connection & Authentication Flow

1. Client opens WebSocket to `ws://<host>:8080/`
2. Client sends `{"type":"AUTH"}`
3. Device responds with ENCRYPTED frame containing CHALLENGE (encrypted with API Secret Key)
   - Decrypted payload contains `sessionKey` (base64) and `initialActionId` (int)
4. Client sends encrypted QUERY action (using Session Key) with `id = initialActionId + 1`
5. Device responds with encrypted QUERY response containing current state
6. Client sends `{"type":"HELLO"}` to complete handshake
7. Device responds with `SERVER_HELLO` containing `apiVersion`, `serialNumber`, `remootioVersion`
8. Connection is now fully established; client must send PING every 60-90 seconds

### Encryption Details

**Key usage:**
- **API Secret Key** (64-char hex): Decrypts the initial CHALLENGE frame (before session is established)
- **API Session Key** (base64, from CHALLENGE): Encrypts/decrypts all frames after authentication
- **API Auth Key** (64-char hex): Used for HMAC-SHA256 MAC on ALL encrypted frames (both pre and post auth)

**Encrypted frame structure:**
```json
{
    "type": "ENCRYPTED",
    "data": {
        "iv": "<base64>",
        "payload": "<base64>"
    },
    "mac": "<base64>"
}
```

**Encryption process:**
1. JSON-serialize the payload, convert to Latin-1 bytes
2. PKCS7-pad to AES block size (16 bytes)
3. Generate random 16-byte IV
4. AES-CBC encrypt with session key (or secret key for challenge)
5. Base64-encode IV and encrypted payload
6. JSON-serialize `{"iv":"...","payload":"..."}` with compact separators (no spaces)
7. HMAC-SHA256 over that JSON string (Latin-1 bytes) using API Auth Key
8. Base64-encode the MAC

**Decryption process:**
1. Verify HMAC-SHA256 MAC over the `data` field JSON (compact, no spaces)
2. Base64-decode IV and payload
3. AES-CBC decrypt with appropriate key (secret key pre-auth, session key post-auth)
4. Remove PKCS7 padding
5. Parse JSON from Latin-1 string

### Action ID

- Formula: `(lastActionId + 1) % 0x7FFFFFFF`
- Must increment sequentially from `initialActionId`
- Invalid sequence causes authentication error and disconnect

### Endpoints (Frame Types)

| Direction | Frame Type | Description |
|-----------|-----------|-------------|
| C->D | `AUTH` | Initiate authentication |
| D->C | `ENCRYPTED` (CHALLENGE) | Session key + initial action ID |
| C->D | `ENCRYPTED` (action) | Send command (QUERY/TRIGGER/OPEN/CLOSE/RESTART) |
| D->C | `ENCRYPTED` (response) | Command response with state |
| D->C | `ENCRYPTED` (event) | Push event (StateChange, RelayTrigger, etc.) |
| C->D | `HELLO` | Request device info |
| D->C | `SERVER_HELLO` | Device info (serial, API version, device type) |
| C->D | `PING` | Keepalive |
| D->C | `PONG` | Keepalive response |
| D->C | `ERROR` | Error notification |

### Commands (Actions)

| Action | Description | Duration? | Sensor Required? |
|--------|-------------|-----------|-----------------|
| QUERY | Get current state | No | No |
| TRIGGER | Toggle relay (open if closed, close if open) | Yes (v3+) | No |
| OPEN | Open if closed, no-op if open | Yes (v3+) | Yes |
| CLOSE | Close if open, no-op if closed | Yes (v3+) | Yes |
| TRIGGER_SECONDARY | Trigger secondary relay (Remootio 2 only) | Yes (v3+) | No |
| RESTART | Restart device | No | No |

**Action request format:**
```json
{"action": {"type": "QUERY", "id": 808411244}}
```

**Action request with duration (v3+, minutes):**
```json
{"action": {"type": "TRIGGER", "id": 808411244, "duration": 5}}
```

**Action response format:**
```json
{
    "response": {
        "type": "QUERY",
        "id": 808411244,
        "success": true,
        "state": "closed",
        "t100ms": 3354,
        "relayTriggered": false,
        "errorCode": ""
    }
}
```

### Error Codes (in action responses)

| Error Code | Meaning |
|-----------|---------|
| `ERR_RELAY_BUSY` | Relay is already active |
| `ERR_INVALID_REQUEST` | Invalid request (e.g. TRIGGER_SECONDARY on Remootio 1) |
| `ERR_NO_SENSOR` | OPEN/CLOSE requires sensor but none installed |

### Connection-Level Error Messages

| Error Message | Meaning |
|--------------|---------|
| `json error` | JSON parsing failed |
| `input error` | Invalid frame values |
| `internal error` | Device internal error |
| `connection timeout` | No frame received for 120 seconds |
| `authentication timeout` | Auth not completed within 30 seconds |
| `authentication error` | Auth flow failure (bad keys or action ID) |
| `already authenticated` | AUTH frame sent while already authenticated |

### Events (Push Messages)

| Event Type | Description | Has Key Data? |
|-----------|-------------|---------------|
| StateChange | Door state changed | No |
| RelayTrigger | Primary relay was triggered | Yes |
| SecondaryRelayTrigger | Secondary relay triggered (Remootio 2) | Yes |
| OutputHeldActive | Output held active (duration mode) | Yes |
| SecondaryOutputHeldActive | Secondary output held active | Yes |
| Connected | Bluetooth/WiFi connection established | Yes |
| LeftOpen | Door left open alert | No (has timeOpen100ms) |
| Restart | Device restarted (cnt resets to 0) | No |
| ManualButtonPushed | Physical button pressed | No |
| ManualButtonEnabled | Manual button enabled | No |
| ManualButtonDisabled | Manual button disabled | No |
| DoorbellPushed | Doorbell button pressed | No |
| DoorbellEnabled | Doorbell enabled | No |
| DoorbellDisabled | Doorbell disabled | No |
| SensorEnabled | Status sensor enabled | No |
| SensorFlipped | Sensor logic reversed | No |
| SensorDisabled | Sensor disabled | No |
| KeyManagement | Key added/removed/modified | Yes (extended) |
| Output1Activated | Output 1 activated | No |
| Output1Deactivated | Output 1 deactivated | No |
| Output2Activated | Output 2 activated | No |
| Output2Deactivated | Output 2 deactivated | No |

**Event format:**
```json
{
    "event": {
        "cnt": 72,
        "type": "StateChange",
        "state": "open",
        "t100ms": 18342
    }
}
```

**Event with key data:**
```json
{
    "event": {
        "cnt": 311,
        "type": "RelayTrigger",
        "state": "closed",
        "t100ms": 12346,
        "data": {
            "keyNr": 5,
            "keyType": "unique key",
            "via": "wifi"
        }
    }
}
```

### State Model

| State Value | Meaning |
|------------|---------|
| `open` | Door/gate is open |
| `closed` | Door/gate is closed |
| `no sensor` | No sensor installed (state unknown) |

**Derived states (client-side only, not from API):**
- `opening` - Inferred when OPEN action triggers relay or RelayTrigger event fires while closed
- `closing` - Inferred when CLOSE action triggers relay or RelayTrigger event fires while open
- `unknown` - Initial state before first QUERY response

### Device Info (from SERVER_HELLO)

| Field | Example | Notes |
|-------|---------|-------|
| `apiVersion` | 3 | Integer: 1, 2, or 3 |
| `serialNumber` | `"ABC123DEF456"` | Unique device identifier |
| `remootioVersion` | `"remootio-2"` | `"remootio-1"` or `"remootio-2"` |
| `message` | `"This is the Remootio Websocket API"` | Static string |

### Timing & Keepalive

| Parameter | Value |
|-----------|-------|
| PING interval | 60 seconds recommended |
| Connection timeout | 120 seconds of inactivity (device disconnects) |
| Auth timeout | 30 seconds to complete auth flow |
| Max connections | 1 concurrent WebSocket connection |
| `t100ms` field | Device uptime in 100ms units (divide by 10 for seconds) |

## Entities

| Platform | Entity | Source | Notes |
|----------|--------|--------|-------|
| cover | Garage Door | WebSocket state/events | CoverDeviceClass.GARAGE, supports open/close/stop |
| binary_sensor | Sensor Installed | QUERY response state | True if state != "no sensor" |
| sensor | Device Uptime | `t100ms` from responses | Optional diagnostic sensor |
| event | Doorbell Pressed | DoorbellPushed event | Optional, if doorbell is configured |

## Known Issues / Gotchas

### Critical
- **Single connection limit**: Device supports only 1 concurrent WebSocket connection. If HA connects, the Remootio app cannot control via WiFi simultaneously.
- **API key format**: Both API Auth Key and API Secret Key are 64-character uppercase hex strings. The app generates them; user must copy them exactly.
- **Session key changes per connection**: The session key is ephemeral, generated fresh each time AUTH is performed. Cannot be cached across reconnects.
- **Action ID must increment**: Using an out-of-sequence action ID causes authentication error and disconnect.
- **Action ID wraps at 0x7FFFFFFF**: Must use modulo arithmetic.

### Encryption
- **Key selection matters**: API Secret Key decrypts ONLY the initial CHALLENGE. All subsequent frames use the session key. The API Auth Key is used for HMAC on ALL frames.
- **MAC is over compact JSON**: The HMAC is computed over `{"iv":"...","payload":"..."}` with no spaces after separators. Using pretty-printed JSON will fail MAC verification.
- **Latin-1 encoding**: All string-to-bytes conversions use Latin-1, not UTF-8.
- **PKCS7 padding**: Standard AES-CBC padding; must handle correctly on both encrypt and decrypt.

### State Machine
- **"opening"/"closing" are inferred**: The API never sends these states. They are derived client-side:
  - After OPEN action with `relayTriggered=true`: state becomes "opening"
  - After CLOSE action with `relayTriggered=true`: state becomes "closing"
  - RelayTrigger event while "closed": infer "opening"
  - RelayTrigger event while "open": infer "closing"
  - StateChange event reports the final state ("open" or "closed")
- **"no sensor" state**: OPEN and CLOSE actions return `ERR_NO_SENSOR`. Only TRIGGER works without a sensor.
- **Uptime-based event dedup**: Events include `t100ms` (device uptime). Events with `t100ms <= last_known_uptime` are stale (from before this connection) and should be ignored, EXCEPT Restart events.

### Connection Management
- **Auto-reconnect required**: Device may disconnect at any time (timeout, restart, network issues). Client must handle reconnection with full re-authentication.
- **No firmware version in API**: The API provides `remootioVersion` (hardware model) and `apiVersion` but NOT the firmware version string.
- **HELLO must come after AUTH**: The HELLO/SERVER_HELLO exchange happens after successful authentication.

### Existing Library
- **aioremootio** (PyPI): Existing async Python client by Gergo Gabor Ilyes-Veisz. Apache 2.0 licensed. Consider wrapping this rather than reimplementing the crypto. However, it depends on `async-class` and `pycryptodome` which adds dependencies. It also has some design quirks (mutable default args, heavy use of locks).

## Quick Reference
- **Domain:** `remootio`
- **Class prefix:** `Remootio`
- **Main code:** `custom_components/remootio/`
- **Validate:** `script/check` (type-check + lint + spell)
- **Test:** `script/test`
- **Run HA:** `./script/develop`

## Current Status
- [x] WebSocket API client with typed models
- [x] Config flow (host, API key, API secret)
- [x] Coordinator (WebSocket push-based)
- [x] Cover platform (garage door)
- [ ] Tests (written, not yet run in devcontainer)
- [x] Options flow for credential updates
- [ ] Diagnostics support
