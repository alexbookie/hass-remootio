# GitHub Copilot Instructions

## Project Identity

- **Domain:** `remootio`
- **Title:** Remootio
- **Class prefix:** `Remootio`
- **Main code:** `custom_components/remootio/`
- **Validate:** `script/check` (type-check + lint-check + spell-check)
- **Start HA:** `./script/develop`

## Architecture

**This is a push-based WebSocket integration (iot_class: local_push), not a polling integration.**

**Module structure (flat, no packages):**

- `api.py` — WebSocket client with AES-256-CBC encryption, auth handshake, state machine
- `coordinator.py` — Push-based `DataUpdateCoordinator[None]` (no update_interval)
- `config_flow.py` — Config flow (user, reauth, reconfigure) + options flow
- `cover.py` — Garage door cover entity with dynamic supported features
- `models.py` — Typed dataclasses and enums for the API protocol
- `const.py` — Constants (domain, timing, config keys)

**Data flow:** Device (WebSocket) → RemootioClient → Coordinator (callback) → Cover Entity

**Key patterns:**

- Entity reads state from `coordinator.client.gate_state`, not `coordinator.data`
- `supported_features` is a dynamic property, not a class attribute
- State inference: opening/closing are client-side derived states
- Single relay device — open/close/stop all send relay pulses with gating logic

## Code Quality

- Python 3.13+, strict typing, async/await
- 120 char lines, double quotes, full type hints
- Run `script/check` before considering any task complete

## Workflow

1. Small, focused changes
2. Run `script/check` to validate
3. Conventional commits format
