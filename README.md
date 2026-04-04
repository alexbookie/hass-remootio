# Remootio

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

Home Assistant integration for [Remootio](https://www.remootio.com/) smart garage door openers. Controls your garage door over the local network via WebSocket — no cloud required.

## Features

- **Local WebSocket API**: Direct communication with your Remootio device — no cloud dependency
- **Real-time state updates**: Push-based updates via WebSocket (no polling)
- **Garage door control**: Open, close, and stop your garage door
- **Smart button states**: Only relevant actions shown (e.g. Stop only while door is moving)
- **Auto-reconnect**: Automatic reconnection on connection loss
- **Credential management**: Update API keys via options flow or reauth

**Entities created:**

Platform | Entity | Description
-- | -- | --
`cover` | Garage Door | Open/close/stop with real-time state

## Supported Devices

- Remootio 1
- Remootio 2

## Prerequisites

- Remootio device with firmware 2.21+ (API v2 or v3)
- API Auth Key and API Secret Key from the Remootio mobile app
- Device and Home Assistant on the same local network
- [HACS](https://hacs.xyz/) installed

### Getting Your API Keys

1. Open the Remootio app on your phone
2. Select your device
3. Go to **Settings** > **API**
4. Enable the API if not already enabled
5. Copy the **API Auth Key** (64-character hex string)
6. Copy the **API Secret Key** (64-character hex string)

> **Note:** Remootio only supports one concurrent WebSocket connection. While Home Assistant is connected, the Remootio app cannot control the device via WiFi (Bluetooth still works).

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu > **Custom repositories**
3. Add `https://github.com/alexbookie/hass-remootio` with category **Integration**
4. Find "Remootio" in the integration list and click **Download**
5. **Restart Home Assistant**

### Manual Installation

1. Download the latest release from the [releases page][releases]
2. Copy `custom_components/remootio/` to your Home Assistant `custom_components/` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **Remootio**
3. Enter:
   - **Host**: IP address or hostname of your Remootio device
   - **API Auth Key**: 64-character hex key from the Remootio app
   - **API Secret Key**: 64-character hex key from the Remootio app
4. Click **Submit**

The integration will connect to your device, verify the credentials, and create the garage door entity.

### Updating Credentials

If your API keys change:

- **Options flow**: Go to the integration > **Configure** > enter new keys
- **Reauth**: If credentials expire, Home Assistant will prompt you automatically

## Troubleshooting

### Connection Issues

- Verify the device IP address is correct and reachable from Home Assistant
- Ensure the device is on the same network (Remootio uses local WebSocket only)
- Check that no other WebSocket client is connected (only 1 connection allowed)
- The Remootio app's WiFi control uses the same connection — close it if needed

### Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.remootio: debug
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/alexbookie/hass-remootio.svg?style=for-the-badge
[commits]: https://github.com/alexbookie/hass-remootio/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/alexbookie/hass-remootio.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40alexbookie-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/alexbookie/hass-remootio.svg?style=for-the-badge
[releases]: https://github.com/alexbookie/hass-remootio/releases
[user_profile]: https://github.com/alexbookie
