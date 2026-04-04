# Getting Started with Remootio

This guide covers installation and setup of the Remootio integration for Home Assistant.

## Prerequisites

- Home Assistant 2025.12.3 or newer
- HACS (Home Assistant Community Store) installed
- Remootio device (Remootio 1 or Remootio 2) with firmware 2.21+
- API Auth Key and API Secret Key from the Remootio mobile app
- Device on the same local network as Home Assistant

## Getting Your API Keys

1. Open the Remootio app on your phone
2. Select your device
3. Go to **Settings** > **API**
4. Enable the API if not already enabled
5. Copy the **API Auth Key** (64-character hex string)
6. Copy the **API Secret Key** (64-character hex string)

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/alexbookie/hass-remootio`
6. Set category to "Integration"
7. Click "Add"
8. Find "Remootio" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/alexbookie/hass-remootio/releases)
2. Copy `custom_components/remootio/` to your Home Assistant `custom_components/` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Remootio"
4. Enter:
   - **Host**: IP address or hostname of your Remootio device
   - **API Auth Key**: 64-character hex key from the Remootio app
   - **API Secret Key**: 64-character hex key from the Remootio app
5. Click **Submit**

The integration connects to your device via WebSocket, authenticates, and creates a garage door cover entity.

## What Gets Created

### Device

- **Remootio {serial}**: Your garage door opener
  - Model: remootio-1 or remootio-2
  - Software version: API version

### Entities

- **Cover (Garage Door)**: Open, close, and stop your garage door
  - Shows real-time state: Open, Closed, Opening, Closing
  - Buttons dynamically change based on state (e.g. Stop only shown while moving)

## Important Notes

- **Single connection**: Remootio supports only one WebSocket connection at a time. While Home Assistant is connected, the Remootio app cannot control via WiFi (Bluetooth still works).
- **Local only**: The integration communicates directly with the device on your local network. No cloud or internet connection is required.
- **Sensor required for directional control**: If no door sensor is installed, only the toggle (trigger) command is available. With a sensor, separate open/close commands are used.

## Dashboard Example

```yaml
type: entities
title: Garage Door
entities:
  - entity: cover.remootio_abc123def456_cover
```

## Troubleshooting

### Connection Failed

- Verify the host IP address is correct and the device is reachable
- Ensure no other WebSocket client is connected (close the Remootio app's WiFi connection)
- Check that the API is enabled in the Remootio app

### Authentication Error

- Verify both API keys are exactly 64 characters and copied correctly
- Re-enable the API in the Remootio app to generate new keys if needed

### Debug Logging

```yaml
logger:
  default: warning
  logs:
    custom_components.remootio: debug
```

## Next Steps

- See [CONFIGURATION.md](./CONFIGURATION.md) for options and credential management
- Report issues at [GitHub Issues](https://github.com/alexbookie/hass-remootio/issues)
