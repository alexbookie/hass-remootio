# Configuration Reference

This document describes all configuration options for the Remootio integration.

## Initial Setup

These options are configured during initial setup via the Home Assistant UI.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| **Host** | string | Yes | IP address or hostname of the Remootio device |
| **API Auth Key** | string | Yes | 64-character hex authentication key from the Remootio app |
| **API Secret Key** | string | Yes | 64-character hex secret key from the Remootio app |

## Options Flow

After setup, you can update API credentials:

1. Go to **Settings** > **Devices & Services**
2. Find "Remootio"
3. Click **Configure**
4. Enter new API Auth Key and/or API Secret Key
5. Click **Submit**

The integration will validate the new credentials and reload.

## Reconfiguration

To change the host address or all credentials:

1. Go to **Settings** > **Devices & Services**
2. Find "Remootio"
3. Click the three dots menu > **Reconfigure**
4. Update host and/or credentials
5. Click **Submit**

## Reauthentication

If credentials become invalid, Home Assistant will prompt automatically:

1. Look for **"Action Required"** on the integration card
2. Click **Reconfigure**
3. Enter updated API keys
4. Click **Submit**

## Cover Entity Behavior

The garage door cover entity shows dynamic buttons based on state:

| Door State | Available Actions | Notes |
|-----------|-------------------|-------|
| Closed | Open | Door is fully down |
| Open | Close | Door is not fully down (includes partially open) |
| Opening | Stop | Brief transitional state as door lifts |
| Closing | Stop | Shown until door reaches fully closed |
| Unknown | Open, Close | No sensor installed or initial state |

### State Details

- **Closed**: The door sensor confirms the door is fully down
- **Open**: The door sensor reads "not closed" — this includes fully open, partially open, and stopped mid-travel
- **Opening**: Inferred when the relay triggers from a closed state (very brief — sensor flips to "open" almost immediately)
- **Closing**: Inferred when the relay triggers from an open state (shown until door reaches bottom)
- **Stop**: Triggers the relay while the door is moving, which stops the motor

### Without a Door Sensor

If no sensor is installed on the Remootio device, the integration uses the TRIGGER command (relay toggle) for all actions. The door state will show as Unknown since there's no sensor feedback.

## Network Requirements

- Remootio uses a local WebSocket connection on port 8080
- The device must be on the same network as Home Assistant
- No cloud or internet connection is required
- Only one WebSocket connection is supported at a time

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.remootio: debug
```

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) - Installation and initial setup
- [GitHub Issues](https://github.com/alexbookie/hass-remootio/issues) - Report problems
