"""WebSocket API client for Remootio devices."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
import hmac as stdlib_hmac
import json
import os
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .const import ACTION_ID_MAX, CONNECT_TIMEOUT, LOGGER, PING_INTERVAL, WS_PORT
from .models import (
    ActionResponse,
    ActionType,
    DerivedState,
    DeviceInfo,
    Event,
    EventType,
    FrameType,
    GateState,
    RemootioAuthError,
    RemootioConnectionError,
    RemootioNoSensorError,
    SessionData,
)

_AES_BLOCK_BITS = 128


class RemootioClient:
    """Async WebSocket client for Remootio garage door openers."""

    def __init__(  # noqa: D107
        self,
        host: str,
        api_auth_key: str,
        api_secret_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = host
        self._api_auth_key_bytes = bytes.fromhex(api_auth_key)
        self._api_secret_key_bytes = bytes.fromhex(api_secret_key)
        self._session = session

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session_data: SessionData | None = None
        self._last_action_id: int = 0
        self._device_info: DeviceInfo | None = None
        self._gate_state: GateState | DerivedState = DerivedState.UNKNOWN
        self._last_t100ms: int = 0

        self._authenticated = False
        self._connected = False
        self._listeners: list[Callable[[], None]] = []
        self._ping_task: asyncio.Task[None] | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._connect_lock = asyncio.Lock()

        self._response_event = asyncio.Event()
        self._last_response: ActionResponse | None = None

    # -- Public properties --

    @property
    def connected(self) -> bool:
        """Return True when fully authenticated and receiving."""
        return self._connected

    @property
    def gate_state(self) -> GateState | DerivedState:
        """Return current gate state."""
        return self._gate_state

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info from SERVER_HELLO."""
        return self._device_info

    @property
    def has_sensor(self) -> bool:
        """Return True if the device has a status sensor installed."""
        return self._gate_state != GateState.NO_SENSOR

    # -- Public methods --

    async def connect(self) -> None:
        """Connect, authenticate, query initial state, and get device info.

        Raises RemootioConnectionError if the device is unreachable.
        Raises RemootioAuthError if authentication fails.
        """
        async with self._connect_lock:
            await self._connect()

    async def disconnect(self) -> None:
        """Disconnect and clean up background tasks."""
        async with self._connect_lock:
            await self._disconnect()

    async def trigger(self) -> None:
        """Send TRIGGER action (toggle relay)."""
        response = await self._send_action(ActionType.TRIGGER)
        self._update_state_from_response(response)

    async def open_door(self) -> None:
        """Send OPEN action. Requires sensor."""
        response = await self._send_action(ActionType.OPEN)
        if response.error_code == "ERR_NO_SENSOR":
            raise RemootioNoSensorError("OPEN requires a sensor")
        self._update_state_from_response(response)

    async def close_door(self) -> None:
        """Send CLOSE action. Requires sensor."""
        response = await self._send_action(ActionType.CLOSE)
        if response.error_code == "ERR_NO_SENSOR":
            raise RemootioNoSensorError("CLOSE requires a sensor")
        self._update_state_from_response(response)

    def register_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a state change callback. Returns an unregister callable."""
        self._listeners.append(callback)

        def unregister() -> None:
            self._listeners.remove(callback)

        return unregister

    # -- Connection lifecycle --

    async def _connect(self) -> None:
        """Establish WebSocket connection and authenticate."""
        try:
            self._ws = await self._session.ws_connect(
                f"ws://{self._host}:{WS_PORT}/",
                timeout=aiohttp.ClientWSTimeout(ws_close=CONNECT_TIMEOUT),
            )
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise RemootioConnectionError(f"Cannot connect to {self._host}:{WS_PORT}") from err

        try:
            await asyncio.wait_for(self._authenticate(), timeout=CONNECT_TIMEOUT)
        except TimeoutError as err:
            await self._disconnect()
            raise RemootioConnectionError("Authentication timed out") from err
        except RemootioAuthError:
            await self._disconnect()
            raise

        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _disconnect(self) -> None:
        """Close connection and cancel background tasks."""
        self._connected = False
        self._authenticated = False
        self._session_data = None

        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None

        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    # -- Authentication handshake --

    async def _authenticate(self) -> None:
        """Perform the full auth handshake.

        1. Send AUTH frame
        2. Receive CHALLENGE (encrypted with API Secret Key)
        3. Send QUERY action (encrypted with Session Key)
        4. Receive QUERY response
        5. Send HELLO
        6. Receive SERVER_HELLO
        """
        ws = self._ws
        if ws is None:
            raise RemootioConnectionError("Not connected")

        # Step 1: Send AUTH
        await ws.send_json({"type": FrameType.AUTH})

        # Step 2: Receive CHALLENGE
        msg = await self._receive_frame()
        if msg.get("type") != FrameType.ENCRYPTED:
            raise RemootioAuthError(f"Expected ENCRYPTED frame, got {msg.get('type')}")

        self._verify_mac(msg["data"], msg["mac"])
        challenge = self._decrypt(
            msg["data"]["iv"],
            msg["data"]["payload"],
            self._api_secret_key_bytes,
        )

        session_key_b64 = challenge["challenge"]["sessionKey"]
        initial_action_id = challenge["challenge"]["initialActionId"]
        self._session_data = SessionData(
            session_key=base64.b64decode(session_key_b64),
            initial_action_id=initial_action_id,
        )
        self._last_action_id = initial_action_id

        # Step 3: Send QUERY to verify session
        action_id = self._next_action_id()
        query_payload = {"action": {"type": ActionType.QUERY, "id": action_id}}
        await ws.send_json(self._build_encrypted_frame(query_payload))

        # Step 4: Receive QUERY response
        msg = await self._receive_frame()
        if msg.get("type") != FrameType.ENCRYPTED:
            raise RemootioAuthError(f"Expected ENCRYPTED response, got {msg.get('type')}")
        self._verify_mac(msg["data"], msg["mac"])
        response_data = self._decrypt(
            msg["data"]["iv"],
            msg["data"]["payload"],
            self._session_data.session_key,
        )

        if "response" in response_data:
            response = self._parse_response(response_data["response"])
            if response.state is not None:
                self._gate_state = response.state
                self._last_t100ms = response_data["response"].get("t100ms", 0)

        self._authenticated = True

        # Step 5: Send HELLO
        await ws.send_json({"type": FrameType.HELLO})

        # Step 6: Receive SERVER_HELLO
        msg = await self._receive_frame()
        if msg.get("type") != FrameType.SERVER_HELLO:
            raise RemootioAuthError(f"Expected SERVER_HELLO, got {msg.get('type')}")
        self._device_info = DeviceInfo(
            serial_number=msg["serialNumber"],
            api_version=msg["apiVersion"],
            remootio_version=msg["remootioVersion"],
        )

    async def _receive_frame(self) -> dict[str, Any]:
        """Receive and parse a single WebSocket JSON frame."""
        ws = self._ws
        if ws is None:
            raise RemootioConnectionError("Not connected")

        msg = await ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return json.loads(msg.data)
        if msg.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.ERROR,
        ):
            raise RemootioConnectionError("WebSocket closed during handshake")
        raise RemootioConnectionError(f"Unexpected message type: {msg.type}")

    # -- Action sending --

    async def _send_action(self, action_type: ActionType) -> ActionResponse:
        """Send an action and wait for the response."""
        if not self._connected or self._session_data is None or self._ws is None:
            raise RemootioConnectionError("Not connected")

        action_id = self._next_action_id()
        payload = {"action": {"type": action_type.value, "id": action_id}}
        frame = self._build_encrypted_frame(payload)

        self._response_event.clear()
        self._last_response = None
        await self._ws.send_json(frame)

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=10)
        except TimeoutError as err:
            raise RemootioConnectionError("Action response timed out") from err

        if self._last_response is None:
            raise RemootioConnectionError("No response received")
        return self._last_response

    def _next_action_id(self) -> int:
        """Increment and return the next action ID."""
        self._last_action_id = (self._last_action_id + 1) % ACTION_ID_MAX
        return self._last_action_id

    # -- Background loops --

    async def _receive_loop(self) -> None:
        """Read incoming WebSocket messages and dispatch them."""
        ws = self._ws
        if ws is None:
            return

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        self._handle_message(json.loads(msg.data))
                    except Exception:  # noqa: BLE001
                        LOGGER.exception("Error handling WebSocket message")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    LOGGER.error("WebSocket error: %s", ws.exception())
                    break
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error in receive loop")

        LOGGER.debug("WebSocket connection closed for %s", self._host)
        self._connected = False
        self._authenticated = False
        self._notify_listeners()

    async def _ping_loop(self) -> None:
        """Send PING frames to keep the connection alive."""
        try:
            while self._connected and self._ws is not None:
                await asyncio.sleep(PING_INTERVAL)
                if self._ws is not None and not self._ws.closed:
                    await self._ws.send_json({"type": FrameType.PING})
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            LOGGER.exception("Error in ping loop")

    # -- Message handling --

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """Dispatch an incoming message by type."""
        frame_type = msg.get("type")

        if frame_type == FrameType.ENCRYPTED:
            self._handle_encrypted(msg)
        elif frame_type == FrameType.PONG:
            pass
        elif frame_type == FrameType.ERROR:
            LOGGER.error("Remootio error: %s", msg.get("errorMessage", "unknown"))
        else:
            LOGGER.debug("Unhandled frame type: %s", frame_type)

    def _handle_encrypted(self, msg: dict[str, Any]) -> None:
        """Decrypt and dispatch an encrypted frame."""
        if self._session_data is None:
            LOGGER.warning("Received encrypted frame without session")
            return

        try:
            self._verify_mac(msg["data"], msg["mac"])
            payload = self._decrypt(
                msg["data"]["iv"],
                msg["data"]["payload"],
                self._session_data.session_key,
            )
        except RemootioAuthError:
            LOGGER.error("MAC verification failed on incoming frame")
            return
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to decrypt frame")
            return

        if "response" in payload:
            response = self._parse_response(payload["response"])
            self._last_response = response
            self._response_event.set()
        elif "event" in payload:
            event = self._parse_event(payload["event"])
            self._update_state_from_event(event)
            self._notify_listeners()

    # -- State machine --

    def _update_state_from_response(self, response: ActionResponse) -> None:
        """Update gate state based on an action response."""
        if response.relay_triggered:
            if self._gate_state in (DerivedState.OPENING, DerivedState.CLOSING):
                # Relay triggered while moving = stop. Sensor reads open (not fully closed).
                self._gate_state = GateState.OPEN
            elif self._gate_state == GateState.CLOSED:
                self._gate_state = DerivedState.OPENING
            elif self._gate_state == GateState.OPEN:
                self._gate_state = DerivedState.CLOSING
            self._notify_listeners()
        elif response.state is not None:
            self._gate_state = response.state
            self._notify_listeners()

    def _update_state_from_event(self, event: Event) -> None:
        """Update gate state from a push event."""
        if event.type != EventType.RESTART and event.t100ms <= self._last_t100ms:
            return
        self._last_t100ms = event.t100ms

        if event.type == EventType.STATE_CHANGE:
            if event.state is not None:
                self._gate_state = event.state
        elif event.type == EventType.RELAY_TRIGGER:
            if self._gate_state in (DerivedState.OPENING, DerivedState.CLOSING):
                # Relay triggered while moving = stop. Door is not closed.
                self._gate_state = GateState.OPEN
            elif self._gate_state == GateState.CLOSED:
                self._gate_state = DerivedState.OPENING
            elif self._gate_state == GateState.OPEN:
                self._gate_state = DerivedState.CLOSING
        elif event.type == EventType.RESTART:
            self._last_t100ms = 0

    # -- Parsing --

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> ActionResponse:
        """Parse a raw response dict into an ActionResponse."""
        state_str = data.get("state")
        state: GateState | None = None
        if state_str is not None:
            try:
                state = GateState(state_str)
            except ValueError:
                LOGGER.warning("Unknown state in response: %s", state_str)

        return ActionResponse(
            type=ActionType(data["type"]),
            id=data["id"],
            success=data.get("success", False),
            state=state,
            relay_triggered=data.get("relayTriggered", False),
            error_code=data.get("errorCode", ""),
        )

    @staticmethod
    def _parse_event(data: dict[str, Any]) -> Event:
        """Parse a raw event dict into an Event."""
        state_str = data.get("state")
        state: GateState | None = None
        if state_str is not None:
            try:
                state = GateState(state_str)
            except ValueError:
                LOGGER.warning("Unknown state in event: %s", state_str)

        return Event(
            cnt=data["cnt"],
            type=EventType(data["type"]),
            state=state,
            t100ms=data.get("t100ms", 0),
            data=data.get("data"),
        )

    # -- Encryption --

    @staticmethod
    def _decrypt(iv_b64: str, payload_b64: str, key: bytes) -> dict[str, Any]:
        """AES-CBC decrypt with PKCS7 unpadding, return parsed JSON."""
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(payload_b64)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = PKCS7(_AES_BLOCK_BITS).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        return json.loads(plaintext.decode("latin-1"))

    @staticmethod
    def _encrypt(payload: dict[str, Any], key: bytes) -> tuple[str, str]:
        """AES-CBC encrypt with PKCS7 padding. Returns (iv_b64, payload_b64)."""
        plaintext = json.dumps(payload, separators=(",", ":")).encode("latin-1")
        padder = PKCS7(_AES_BLOCK_BITS).padder()
        padded = padder.update(plaintext) + padder.finalize()
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(iv).decode(), base64.b64encode(ciphertext).decode()

    def _compute_mac(self, data: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 over compact JSON, return base64."""
        data_json = json.dumps(data, separators=(",", ":")).encode("latin-1")
        h = crypto_hmac.HMAC(self._api_auth_key_bytes, hashes.SHA256())
        h.update(data_json)
        return base64.b64encode(h.finalize()).decode()

    def _verify_mac(self, data: dict[str, Any], mac_b64: str) -> None:
        """Verify HMAC-SHA256 on a received frame. Raises RemootioAuthError."""
        expected = self._compute_mac(data)
        if not stdlib_hmac.compare_digest(expected.encode("ascii"), mac_b64.encode("ascii")):
            raise RemootioAuthError("MAC verification failed")

    def _build_encrypted_frame(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Encrypt payload with session key, compute MAC, return full frame."""
        if self._session_data is None:
            raise RemootioConnectionError("No session key available")
        iv_b64, payload_b64 = self._encrypt(payload, self._session_data.session_key)
        data = {"iv": iv_b64, "payload": payload_b64}
        mac = self._compute_mac(data)
        return {"type": FrameType.ENCRYPTED, "data": data, "mac": mac}

    # -- Listener notification --

    def _notify_listeners(self) -> None:
        """Notify all registered listeners of a state change."""
        for listener in self._listeners:
            try:
                listener()
            except Exception:  # noqa: BLE001
                LOGGER.exception("Error in state change listener")
