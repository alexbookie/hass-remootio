# Changelog

## v0.2.0 (2026-07-12)

### Fixed
- Stop spurious re-auth prompts on transient reconnect failures. Transient
  handshake problems (connection/authentication timeouts, protocol errors,
  unexpected frames) are now classified as retryable connection errors instead
  of auth failures — only a genuine authentication error triggers HA's re-auth
  flow, and only after several consecutive failures.
- A wrong API Secret Key now raises a proper auth error instead of silently
  killing the reconnect task.
- Stray pushed events during the handshake no longer desync the connection flow.
- The WebSocket connect timeout is now enforced with `asyncio.timeout` instead of
  being passed as aiohttp's close-handshake timeout (which never limited connect
  time).

### Changed
- Reconnects now use exponential backoff (5s up to 120s) instead of a fixed 5s
  retry, avoiding races with the device's single-connection window.

### Internal
- Added tests for handshake frame classification and the reconnect/re-auth policy.
- CI and dev tooling dependency updates (dependabot).

## v0.1.1 (2026-04-04)

### Changed
- Updated README and documentation to accurately describe the integration.
- Removed template boilerplate from all docs.
- Dependency updates (actions/cache, setup-uv, pytest-homeassistant-custom-component).

## v0.1.0 (2026-04-04)

### Added
- Initial release: Remootio garage door/gate integration via local WebSocket API.
- Config flow with host, API Auth Key, and API Secret Key.
- Push-based coordinator with real-time state updates.
- Cover entity (garage door) with open/close/stop and inferred
  opening/closing states.
- Options flow for credential updates.
