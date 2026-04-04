# Integration: Remootio

## What This Does
Integrates Remootio smart garage door openers with Home Assistant via local WebSocket API.
Exposes: cover entity (garage door) with open/close/stop and real-time state updates.

## API Details
- Protocol: WebSocket (local network, not cloud)
- Default port: 8080 (ws://<host>:8080/)
- Auth: API key + API secret (obtained from Remootio mobile app)
- Encryption: AES-128-CBC + HMAC-SHA256
- Docs: https://documents.remootio.com/docs/WebsocketsAPI.pdf
- iot_class: local_push

## Entities
| Platform | Entity         | Source                    |
|----------|---------------|---------------------------|
| cover    | Garage Door   | WebSocket state/events    |

## Known Issues / Gotchas
- WebSocket API uses encrypted frames (AES-128-CBC) — not plain JSON
- API key and secret must be enabled in the Remootio app settings
- Device must be on same local network (no cloud relay)
- The API has a session-based auth flow (AUTH frame exchange)

## Quick Reference
- **Domain:** `remootio`
- **Class prefix:** `Remootio`
- **Main code:** `custom_components/remootio/`
- **Validate:** `script/check` (type-check + lint + spell)
- **Test:** `script/test`
- **Run HA:** `./script/develop`

## Current Status
- [ ] WebSocket API client with typed models
- [ ] Config flow (host, API key, API secret)
- [ ] Coordinator (WebSocket push-based)
- [ ] Cover platform (garage door)
- [ ] Tests
- [ ] Options flow for credential updates
- [ ] Diagnostics support
