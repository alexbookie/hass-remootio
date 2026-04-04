"""Tests for the Remootio WebSocket API client."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.remootio.api import RemootioClient
from custom_components.remootio.models import (
    ActionType,
    DerivedState,
    EventType,
    GateState,
    RemootioAuthError,
    RemootioConnectionError,
)

TEST_AUTH_KEY = "aa" * 32  # 64-char hex -> 32 bytes
TEST_SECRET_KEY = "bb" * 32  # 64-char hex -> 32 bytes


@pytest.fixture
def client() -> RemootioClient:
    """Create a RemootioClient with a mocked session."""
    session = MagicMock()
    return RemootioClient(
        host="192.168.1.100",
        api_auth_key=TEST_AUTH_KEY,
        api_secret_key=TEST_SECRET_KEY,
        session=session,
    )


# -- Encryption tests --


class TestEncryption:
    """Test encryption and MAC operations."""

    def test_encrypt_decrypt_roundtrip(self, client: RemootioClient) -> None:
        """Encrypted data should decrypt back to the original payload."""
        key = bytes.fromhex(TEST_SECRET_KEY)
        payload = {"action": {"type": "QUERY", "id": 12345}}

        iv_b64, encrypted_b64 = RemootioClient._encrypt(payload, key)
        result = RemootioClient._decrypt(iv_b64, encrypted_b64, key)

        assert result == payload

    def test_encrypt_produces_different_iv_each_time(self, client: RemootioClient) -> None:
        """Each encryption should use a random IV."""
        key = bytes.fromhex(TEST_SECRET_KEY)
        payload = {"test": "data"}

        iv1, _ = RemootioClient._encrypt(payload, key)
        iv2, _ = RemootioClient._encrypt(payload, key)

        assert iv1 != iv2

    def test_mac_computation_deterministic(self, client: RemootioClient) -> None:
        """MAC for same data should be identical."""
        data = {"iv": "dGVzdA==", "payload": "dGVzdA=="}

        mac1 = client._compute_mac(data)
        mac2 = client._compute_mac(data)

        assert mac1 == mac2

    def test_mac_verification_passes_on_valid(self, client: RemootioClient) -> None:
        """Valid MAC should not raise."""
        data = {"iv": "dGVzdA==", "payload": "dGVzdA=="}
        mac = client._compute_mac(data)

        # Should not raise
        client._verify_mac(data, mac)

    def test_mac_verification_fails_on_tampered(self, client: RemootioClient) -> None:
        """Tampered MAC should raise RemootioAuthError."""
        data = {"iv": "dGVzdA==", "payload": "dGVzdA=="}

        with pytest.raises(RemootioAuthError, match="MAC verification failed"):
            client._verify_mac(data, "invalid_mac_base64==")

    def test_mac_uses_compact_json(self, client: RemootioClient) -> None:
        """MAC should be computed over compact JSON (no spaces)."""
        data = {"iv": "abc", "payload": "def"}
        mac = client._compute_mac(data)

        # Compute expected MAC manually over compact JSON
        import hashlib
        import hmac

        compact = json.dumps(data, separators=(",", ":")).encode("latin-1")
        expected = base64.b64encode(hmac.new(bytes.fromhex(TEST_AUTH_KEY), compact, hashlib.sha256).digest()).decode()

        assert mac == expected

    def test_build_encrypted_frame_structure(self, client: RemootioClient) -> None:
        """Encrypted frame should have correct structure."""
        from custom_components.remootio.models import SessionData

        client._session_data = SessionData(
            session_key=bytes.fromhex(TEST_SECRET_KEY),
            initial_action_id=100,
        )

        payload = {"action": {"type": "QUERY", "id": 101}}
        frame = client._build_encrypted_frame(payload)

        assert frame["type"] == "ENCRYPTED"
        assert "iv" in frame["data"]
        assert "payload" in frame["data"]
        assert "mac" in frame


# -- Action ID tests --


class TestActionId:
    """Test action ID sequencing."""

    def test_action_id_increments(self, client: RemootioClient) -> None:
        """Action ID should increment by 1."""
        client._last_action_id = 100

        assert client._next_action_id() == 101
        assert client._next_action_id() == 102

    def test_action_id_wraps(self, client: RemootioClient) -> None:
        """Action ID should wrap at 0x7FFFFFFF."""
        client._last_action_id = 0x7FFFFFFE

        assert client._next_action_id() == 0x7FFFFFFF
        assert client._next_action_id() == 0  # Wraps


# -- State machine tests --


class TestStateMachine:
    """Test gate state inference logic."""

    def test_state_change_event_updates_state(self, client: RemootioClient) -> None:
        """StateChange event should set gate state directly."""
        from custom_components.remootio.models import Event

        client._gate_state = GateState.CLOSED
        client._last_t100ms = 0

        event = Event(cnt=1, type=EventType.STATE_CHANGE, state=GateState.OPEN, t100ms=100)
        client._update_state_from_event(event)

        assert client._gate_state == GateState.OPEN

    def test_relay_trigger_from_closed_sets_opening(self, client: RemootioClient) -> None:
        """RelayTrigger while closed should infer opening."""
        from custom_components.remootio.models import Event

        client._gate_state = GateState.CLOSED
        client._last_t100ms = 0

        event = Event(cnt=1, type=EventType.RELAY_TRIGGER, state=None, t100ms=100)
        client._update_state_from_event(event)

        assert client._gate_state == DerivedState.OPENING

    def test_relay_trigger_from_open_sets_closing(self, client: RemootioClient) -> None:
        """RelayTrigger while open should infer closing."""
        from custom_components.remootio.models import Event

        client._gate_state = GateState.OPEN
        client._last_t100ms = 0

        event = Event(cnt=1, type=EventType.RELAY_TRIGGER, state=None, t100ms=100)
        client._update_state_from_event(event)

        assert client._gate_state == DerivedState.CLOSING

    def test_stale_event_ignored(self, client: RemootioClient) -> None:
        """Events with t100ms <= last known should be ignored."""
        from custom_components.remootio.models import Event

        client._gate_state = GateState.CLOSED
        client._last_t100ms = 200

        event = Event(cnt=1, type=EventType.STATE_CHANGE, state=GateState.OPEN, t100ms=100)
        client._update_state_from_event(event)

        assert client._gate_state == GateState.CLOSED  # Not changed

    def test_restart_event_resets_uptime(self, client: RemootioClient) -> None:
        """Restart event should reset t100ms counter."""
        from custom_components.remootio.models import Event

        client._last_t100ms = 50000

        event = Event(cnt=1, type=EventType.RESTART, state=None, t100ms=0)
        client._update_state_from_event(event)

        assert client._last_t100ms == 0

    def test_trigger_response_opening_from_closed(self, client: RemootioClient) -> None:
        """TRIGGER response with relayTriggered while closed should set opening."""
        from custom_components.remootio.models import ActionResponse

        client._gate_state = GateState.CLOSED

        response = ActionResponse(
            type=ActionType.TRIGGER,
            id=1,
            success=True,
            state=GateState.CLOSED,
            relay_triggered=True,
            error_code="",
        )
        client._update_state_from_response(response)

        assert client._gate_state == DerivedState.OPENING

    def test_trigger_response_closing_from_open(self, client: RemootioClient) -> None:
        """TRIGGER response with relayTriggered while open should set closing."""
        from custom_components.remootio.models import ActionResponse

        client._gate_state = GateState.OPEN

        response = ActionResponse(
            type=ActionType.TRIGGER,
            id=1,
            success=True,
            state=GateState.OPEN,
            relay_triggered=True,
            error_code="",
        )
        client._update_state_from_response(response)

        assert client._gate_state == DerivedState.CLOSING

    def test_query_response_sets_state_directly(self, client: RemootioClient) -> None:
        """QUERY response should set state without transition inference."""
        from custom_components.remootio.models import ActionResponse

        client._gate_state = DerivedState.UNKNOWN

        response = ActionResponse(
            type=ActionType.QUERY,
            id=1,
            success=True,
            state=GateState.OPEN,
            relay_triggered=False,
            error_code="",
        )
        client._update_state_from_response(response)

        assert client._gate_state == GateState.OPEN


# -- Parsing tests --


class TestParsing:
    """Test response and event parsing."""

    def test_parse_response(self, client: RemootioClient) -> None:
        """Should parse a valid response dict."""
        data = {
            "type": "QUERY",
            "id": 808411244,
            "success": True,
            "state": "closed",
            "t100ms": 3354,
            "relayTriggered": False,
            "errorCode": "",
        }
        response = RemootioClient._parse_response(data)

        assert response.type == ActionType.QUERY
        assert response.id == 808411244
        assert response.success is True
        assert response.state == GateState.CLOSED
        assert response.relay_triggered is False
        assert response.error_code == ""

    def test_parse_event(self, client: RemootioClient) -> None:
        """Should parse a valid event dict."""
        data = {
            "cnt": 72,
            "type": "StateChange",
            "state": "open",
            "t100ms": 18342,
        }
        event = RemootioClient._parse_event(data)

        assert event.cnt == 72
        assert event.type == EventType.STATE_CHANGE
        assert event.state == GateState.OPEN
        assert event.t100ms == 18342

    def test_parse_response_no_sensor_state(self, client: RemootioClient) -> None:
        """Should handle 'no sensor' state string."""
        data = {
            "type": "QUERY",
            "id": 1,
            "success": True,
            "state": "no sensor",
            "relayTriggered": False,
            "errorCode": "",
        }
        response = RemootioClient._parse_response(data)
        assert response.state == GateState.NO_SENSOR


# -- Connection tests --


class TestConnection:
    """Test connection lifecycle."""

    @pytest.mark.usefixtures("client")
    async def test_connect_failure_raises(self) -> None:
        """Connection failure should raise RemootioConnectionError."""
        import aiohttp

        session = AsyncMock()
        session.ws_connect = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))

        client = RemootioClient(
            host="192.168.1.100",
            api_auth_key=TEST_AUTH_KEY,
            api_secret_key=TEST_SECRET_KEY,
            session=session,
        )

        with pytest.raises(RemootioConnectionError, match="Cannot connect"):
            await client.connect()

    async def test_disconnect_cleans_up(self, client: RemootioClient) -> None:
        """Disconnect should cancel tasks and close websocket."""
        client._connected = True
        mock_ws = AsyncMock()
        mock_ws.closed = False
        client._ws = mock_ws
        client._ping_task = MagicMock()
        client._receive_task = MagicMock()

        await client._disconnect()

        assert client._connected is False
        assert client._ws is None
        client._ping_task.cancel.assert_called_once()
        client._receive_task.cancel.assert_called_once()
        mock_ws.close.assert_awaited_once()

    def test_has_sensor_true_when_closed(self, client: RemootioClient) -> None:
        """has_sensor should be True when state is closed."""
        client._gate_state = GateState.CLOSED
        assert client.has_sensor is True

    def test_has_sensor_false_when_no_sensor(self, client: RemootioClient) -> None:
        """has_sensor should be False when state is no sensor."""
        client._gate_state = GateState.NO_SENSOR
        assert client.has_sensor is False

    def test_register_and_unregister_listener(self, client: RemootioClient) -> None:
        """Listener registration and unregistration should work."""
        callback = MagicMock()
        unregister = client.register_listener(callback)

        assert callback in client._listeners

        unregister()
        assert callback not in client._listeners
