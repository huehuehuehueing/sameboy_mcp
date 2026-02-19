"""SameBoy Web Dashboard — live emulator view over WebSocket."""

import asyncio
import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..emulator.thread import EmulatorThread, CommandType
from .events import EventBus, Event, EventType, DashboardEventSink
from .frame_relay import FrameRelay

logger = logging.getLogger("sameboy-dashboard")

STATIC_DIR = Path(__file__).parent / "static"


class DashboardServer:
    """WebSocket-based dashboard server for SameBoy emulator.

    Can be mounted on an existing Starlette app (SSE mode) or run
    standalone (stdio mode).
    """

    def __init__(self, emu_thread: EmulatorThread) -> None:
        self._emu_thread = emu_thread
        self._event_bus = EventBus()
        self._frame_relay: FrameRelay | None = None
        self._snapshot_task: asyncio.Task | None = None
        self._agent_sink: DashboardEventSink | None = None
        self._snapshot_hooks: list = []
        self._last_agent_actions: list[dict] | None = None
        self._panel_registry: list[dict] | None = None
        self._last_panel_data: dict[str, dict] = {}

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    def create_agent_sink(self) -> DashboardEventSink:
        """Create an AgentEventSink for the Pokemon agent to publish events."""
        loop = asyncio.get_running_loop()
        self._agent_sink = DashboardEventSink(self._event_bus, loop)
        return self._agent_sink

    def register_panels(self, panels: list[dict]) -> None:
        """Register plugin panels and broadcast to connected clients."""
        self._panel_registry = panels
        self._event_bus.publish(Event(
            type=EventType.PANEL_REGISTRY,
            data={"panels": panels},
        ))

    def register_snapshot_hook(self, hook) -> None:
        """Register a plugin hook called during each snapshot poll.

        Args:
            hook: Callable(emu_thread) -> dict | None.  The returned dict
                  is sent to the dashboard as ``game_state``.
        """
        self._snapshot_hooks.append(hook)

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start the dashboard (frame relay + snapshot loop).

        Must be called from an async context or with a running loop.
        """
        if loop is None:
            loop = asyncio.get_running_loop()

        # Set up frame relay on the emulator
        self._frame_relay = FrameRelay(self._event_bus, loop)
        self._emu_thread.emulator.set_dashboard_frame_relay(self._frame_relay)

        # Start the snapshot polling loop
        self._snapshot_task = loop.create_task(self._snapshot_loop())
        logger.info("Dashboard started")

    async def stop(self) -> None:
        """Stop the dashboard."""
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        self._emu_thread.emulator.set_dashboard_frame_relay(None)
        logger.info("Dashboard stopped")

    def mount(self, app: Starlette) -> None:
        """Mount dashboard routes onto an existing Starlette app."""
        # Insert in reverse priority order (insert(0) pushes previous items down).
        # Final order: [WebSocketRoute, Route, Mount, ...existing...]
        app.routes.insert(0, Mount("/dashboard/", app=StaticFiles(directory=str(STATIC_DIR), html=True)))
        app.routes.insert(0, Route("/dashboard", self._redirect_to_index))
        app.routes.insert(0, WebSocketRoute("/dashboard/ws", self._ws_endpoint))

    def create_app(self) -> Starlette:
        """Create a standalone Starlette app for the dashboard."""
        routes = [
            WebSocketRoute("/dashboard/ws", self._ws_endpoint),
            Route("/dashboard", self._redirect_to_index),
            Mount("/dashboard/", app=StaticFiles(directory=str(STATIC_DIR), html=True)),
            Route("/", self._redirect_to_dashboard),
        ]
        return Starlette(routes=routes, on_startup=[self._on_startup])

    async def _on_startup(self) -> None:
        """Startup hook for standalone mode."""
        self.start()

    async def _redirect_to_index(self, request: Request) -> RedirectResponse:
        return RedirectResponse(url="/dashboard/index.html")

    async def _redirect_to_dashboard(self, request: Request) -> RedirectResponse:
        return RedirectResponse(url="/dashboard/index.html")

    async def _ws_endpoint(self, websocket: WebSocket) -> None:
        """Handle a WebSocket connection."""
        await websocket.accept()
        sub_id, queue = await self._event_bus.subscribe()
        logger.info(f"Dashboard client connected (sub_id={sub_id})")

        sender_task = asyncio.create_task(self._ws_sender(websocket, queue))
        receiver_task = asyncio.create_task(self._ws_receiver(websocket))

        try:
            done, pending = await asyncio.wait(
                [sender_task, receiver_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        except Exception:
            pass
        finally:
            await self._event_bus.unsubscribe(sub_id)
            sender_task.cancel()
            receiver_task.cancel()
            # Await cancelled tasks to ensure cleanup
            for task in [sender_task, receiver_task]:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            logger.info(f"Dashboard client disconnected (sub_id={sub_id})")

    async def _ws_sender(self, websocket: WebSocket, queue: asyncio.Queue[Event]) -> None:
        """Forward events from the EventBus to the WebSocket client."""
        try:
            # Replay cached state for late-joining clients
            if self._last_agent_actions is not None:
                await websocket.send_text(json.dumps({
                    "type": "agent_actions",
                    "data": {"actions": self._last_agent_actions},
                }))
            if self._panel_registry is not None:
                await websocket.send_text(json.dumps({
                    "type": "panel_registry",
                    "data": {"panels": self._panel_registry},
                }))
            for panel_data in self._last_panel_data.values():
                await websocket.send_text(json.dumps({
                    "type": "panel_data",
                    "data": panel_data,
                }))

            while True:
                event = await queue.get()
                if event.type == EventType.FRAME:
                    await websocket.send_bytes(event.data)
                else:
                    # Cache for late-joining clients
                    if event.type == EventType.AGENT_ACTIONS and "actions" in (event.data or {}):
                        self._last_agent_actions = event.data["actions"]
                    elif event.type == EventType.PANEL_REGISTRY and "panels" in (event.data or {}):
                        self._panel_registry = event.data["panels"]
                    elif event.type == EventType.PANEL_DATA and "panel_id" in (event.data or {}):
                        self._last_panel_data[event.data["panel_id"]] = event.data
                    msg = {
                        "type": event.type.name.lower(),
                        "data": event.data,
                        "timestamp": event.timestamp,
                    }
                    await websocket.send_text(json.dumps(msg))
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"WS sender error: {e}")

    async def _ws_receiver(self, websocket: WebSocket) -> None:
        """Handle incoming messages from the WebSocket client."""
        try:
            while True:
                text = await websocket.receive_text()
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                if msg_type == "press_key":
                    key = msg.get("key", "")
                    await self._handle_key_press(key)
                elif msg_type == "inject_prompt":
                    text_val = msg.get("text", "")
                    if text_val:
                        self._event_bus.publish(Event(
                            type=EventType.LLM_MESSAGE,
                            data={"role": "injection", "content": text_val},
                        ))
                        if self._agent_sink:
                            self._agent_sink.add_injection(text_val)
                        logger.info(f"Prompt injection: {text_val[:80]}")
                elif msg_type == "agent_action":
                    action_id = msg.get("action_id", "")
                    if action_id:
                        # Same-process agent
                        if self._agent_sink:
                            self._agent_sink.add_action({"action_id": action_id})
                        # Remote agent: broadcast via EventBus so _ws_sender
                        # forwards to remote agent's WS connection
                        self._event_bus.publish(Event(
                            type=EventType.AGENT_ACTIONS,
                            data={"trigger": action_id},
                        ))
                elif msg_type == "agent_event":
                    # Forwarded from RemoteDashboardEventSink (agent process)
                    event_type_name = msg.get("event_type", "").upper()
                    data = msg.get("data", {})
                    try:
                        et = EventType[event_type_name]
                        self._event_bus.publish(Event(type=et, data=data))
                    except KeyError:
                        pass
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"WS receiver error: {e}")

    async def _handle_key_press(self, key: str) -> None:
        """Forward a key press to the emulator (non-blocking)."""
        valid_keys = {"a", "b", "start", "select", "up", "down", "left", "right"}
        if key.lower() in valid_keys:
            try:
                await asyncio.to_thread(
                    self._emu_thread.send_command,
                    CommandType.PRESS_KEY,
                    {"key": key.lower(), "frames": 4},
                    1.0,
                )
            except Exception as e:
                logger.debug(f"Key press error: {e}")

    def _take_snapshot(self) -> dict | None:
        """Take a snapshot (runs in a worker thread to avoid blocking)."""
        result = self._emu_thread.send_command(
            CommandType.DASHBOARD_SNAPSHOT, None, 1.0,
        )
        if result and not result.get("error"):
            for hook in self._snapshot_hooks:
                try:
                    extra = hook(self._emu_thread)
                    if extra:
                        result["game_state"] = extra
                except Exception:
                    pass
            return result
        return None

    async def _snapshot_loop(self) -> None:
        """Poll emulator state at ~5Hz and publish snapshots (non-blocking)."""
        while True:
            try:
                result = await asyncio.to_thread(self._take_snapshot)
                if result:
                    self._event_bus.publish(Event(
                        type=EventType.SNAPSHOT,
                        data=result,
                    ))
            except Exception:
                pass
            await asyncio.sleep(0.2)
