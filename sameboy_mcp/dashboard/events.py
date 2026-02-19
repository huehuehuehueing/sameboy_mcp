"""Dashboard event system - async pub/sub with per-client queues."""

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable


class EventType(Enum):
    """Types of events the dashboard can receive."""
    FRAME = auto()           # Binary JPEG frame
    SNAPSHOT = auto()        # CPU registers + disassembly + status
    AGENT_STATE = auto()     # Game state from agent
    LLM_MESSAGE = auto()     # LLM conversation message
    LLM_TOOL_CALL = auto()   # LLM tool call
    AGENT_DECISION = auto()  # Agent decision
    PANEL_DATA = auto()      # Plugin panel data
    PANEL_REGISTRY = auto()  # Panel registration
    AGENT_ACTIONS = auto()   # Agent-registered action buttons


@dataclass
class Event:
    """A dashboard event."""
    type: EventType
    data: Any
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Async pub/sub with per-client queues.

    Each subscriber gets its own asyncio.Queue. Events are published
    to all subscribers via put_nowait; full queues drop events silently
    to avoid backpressure blocking the emulator or snapshot loop.
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, asyncio.Queue[Event]] = {}
        self._next_id = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, maxsize: int = 100) -> tuple[int, asyncio.Queue[Event]]:
        """Subscribe to events. Returns (subscriber_id, queue)."""
        async with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
            self._subscribers[sub_id] = queue
            return sub_id, queue

    async def unsubscribe(self, sub_id: int) -> None:
        """Remove a subscriber."""
        async with self._lock:
            self._subscribers.pop(sub_id, None)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers (non-blocking, drops on full)."""
        for queue in self._subscribers.values():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop event for slow clients

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# ── Agent Event Sink ─────────────────────────────────

@runtime_checkable
class AgentEventSink(Protocol):
    """Protocol for agent -> dashboard event publishing."""

    def emit_llm_message(self, role: str, content: str) -> None: ...
    def emit_tool_call(self, name: str, args: dict, result: Any = None) -> None: ...
    def emit_decision(self, decision: dict) -> None: ...
    def emit_state(self, state: dict) -> None: ...
    def get_pending_injections(self) -> list[str]: ...
    def emit_action_registry(self, actions: list[dict]) -> None: ...
    def get_pending_actions(self) -> list[dict]: ...
    def emit_panel_data(self, panel_id: str, content: Any, panel_type: str = "") -> None: ...
    def emit_panel_registry(self, panels: list[dict]) -> None: ...


class DashboardEventSink:
    """Concrete AgentEventSink that publishes to an EventBus.

    Thread-safe: the agent runs in its own async context, while the
    EventBus lives on the dashboard's event loop. We use
    loop.call_soon_threadsafe for publishing, and a threading.Lock
    for the injection queue (dashboard WS receiver writes, agent reads).
    """

    def __init__(self, event_bus: EventBus, loop: asyncio.AbstractEventLoop) -> None:
        self._event_bus = event_bus
        self._loop = loop
        self._injection_lock = threading.Lock()
        self._injection_queue: deque[str] = deque(maxlen=50)
        self._action_lock = threading.Lock()
        self._action_queue: deque[dict] = deque(maxlen=50)

    def _publish(self, event: Event) -> None:
        """Publish an event, thread-safe."""
        try:
            self._loop.call_soon_threadsafe(self._event_bus.publish, event)
        except RuntimeError:
            pass  # Loop closed

    def emit_llm_message(self, role: str, content: str) -> None:
        self._publish(Event(
            type=EventType.LLM_MESSAGE,
            data={"role": role, "content": content},
        ))

    def emit_tool_call(self, name: str, args: dict, result: Any = None) -> None:
        self._publish(Event(
            type=EventType.LLM_TOOL_CALL,
            data={"name": name, "args": args, "result": result},
        ))

    def emit_decision(self, decision: dict) -> None:
        self._publish(Event(
            type=EventType.AGENT_DECISION,
            data=decision,
        ))

    def emit_state(self, state: dict) -> None:
        self._publish(Event(
            type=EventType.AGENT_STATE,
            data=state,
        ))

    def get_pending_injections(self) -> list[str]:
        with self._injection_lock:
            items = list(self._injection_queue)
            self._injection_queue.clear()
            return items

    def add_injection(self, text: str) -> None:
        """Called from the dashboard WS receiver to queue a prompt injection."""
        with self._injection_lock:
            self._injection_queue.append(text)

    def emit_action_registry(self, actions: list[dict]) -> None:
        self._publish(Event(
            type=EventType.AGENT_ACTIONS,
            data={"actions": actions},
        ))

    def get_pending_actions(self) -> list[dict]:
        with self._action_lock:
            items = list(self._action_queue)
            self._action_queue.clear()
            return items

    def add_action(self, action: dict) -> None:
        """Called from the dashboard WS receiver to queue an agent action."""
        with self._action_lock:
            self._action_queue.append(action)

    def emit_panel_data(self, panel_id: str, content: Any, panel_type: str = "") -> None:
        self._publish(Event(
            type=EventType.PANEL_DATA,
            data={"panel_id": panel_id, "content": content, "type": panel_type},
        ))

    def emit_panel_registry(self, panels: list[dict]) -> None:
        self._publish(Event(
            type=EventType.PANEL_REGISTRY,
            data={"panels": panels},
        ))


class RemoteDashboardEventSink:
    """AgentEventSink that publishes to a remote dashboard over WebSocket.

    Used by the Pokemon agent (separate process) to send events to
    the dashboard server. Connects as a WebSocket client and sends
    JSON events. Also receives prompt injections from the dashboard.
    """

    def __init__(self, ws_url: str) -> None:
        self._ws_url = ws_url
        self._ws = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._injection_lock = threading.Lock()
        self._injection_queue: deque[str] = deque(maxlen=50)
        self._action_lock = threading.Lock()
        self._action_queue: deque[dict] = deque(maxlen=50)
        self._connected = False
        self._receive_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Connect to the dashboard WebSocket."""
        try:
            import websockets
            self._loop = asyncio.get_running_loop()
            self._ws = await websockets.connect(self._ws_url)
            self._connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            return True
        except Exception as e:
            print(f"  [dashboard-sink] connect failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the dashboard WebSocket."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            await self._ws.close()
        self._connected = False

    async def _receive_loop(self) -> None:
        """Receive prompt injections and action triggers from the dashboard."""
        try:
            async for message in self._ws:
                if isinstance(message, str):
                    try:
                        msg = json.loads(message)
                        if msg.get("type") == "llm_message":
                            data = msg.get("data", {})
                            if data.get("role") == "injection":
                                with self._injection_lock:
                                    self._injection_queue.append(data.get("content", ""))
                        elif msg.get("type") == "agent_actions":
                            data = msg.get("data", {})
                            if "trigger" in data:
                                with self._action_lock:
                                    self._action_queue.append({"action_id": data["trigger"]})
                    except json.JSONDecodeError:
                        pass
        except Exception:
            self._connected = False

    async def _send(self, msg: dict) -> None:
        """Send a JSON message over WebSocket."""
        if self._ws and self._connected:
            try:
                await self._ws.send(json.dumps(msg))
            except Exception:
                self._connected = False

    def _schedule_send(self, msg: dict) -> None:
        """Schedule a send on the event loop (thread-safe via call_soon_threadsafe)."""
        if not self._loop or not self._connected:
            return
        try:
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self._send(msg)
            )
        except RuntimeError:
            pass

    def emit_llm_message(self, role: str, content: str) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "llm_message",
            "data": {"role": role, "content": content},
        })

    def emit_tool_call(self, name: str, args: dict, result: Any = None) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "llm_tool_call",
            "data": {"name": name, "args": args, "result": result},
        })

    def emit_decision(self, decision: dict) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "agent_decision",
            "data": decision,
        })

    def emit_state(self, state: dict) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "agent_state",
            "data": state,
        })

    def emit_action_registry(self, actions: list[dict]) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "agent_actions",
            "data": {"actions": actions},
        })

    def emit_panel_data(self, panel_id: str, content: Any, panel_type: str = "") -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "panel_data",
            "data": {"panel_id": panel_id, "content": content, "type": panel_type},
        })

    def emit_panel_registry(self, panels: list[dict]) -> None:
        self._schedule_send({
            "type": "agent_event",
            "event_type": "panel_registry",
            "data": {"panels": panels},
        })

    def get_pending_actions(self) -> list[dict]:
        with self._action_lock:
            items = list(self._action_queue)
            self._action_queue.clear()
            return items

    def get_pending_injections(self) -> list[str]:
        with self._injection_lock:
            items = list(self._injection_queue)
            self._injection_queue.clear()
            return items
