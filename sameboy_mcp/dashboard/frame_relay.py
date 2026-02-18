"""Frame relay: vblank callback -> rate-limited JPEG -> EventBus."""

import asyncio
import io
import time

from .events import EventBus, Event, EventType


class FrameRelay:
    """Bridges emulator vblank (emu thread) to dashboard EventBus (async).

    Called from the emulator's vblank callback at ~60fps. Rate-limits to
    ~10fps, converts ARGB pixels to JPEG, and publishes to the EventBus
    via loop.call_soon_threadsafe().
    """

    def __init__(self, event_bus: EventBus, loop: asyncio.AbstractEventLoop,
                 target_fps: float = 10.0, jpeg_quality: int = 80) -> None:
        self._event_bus = event_bus
        self._loop = loop
        self._min_interval = 1.0 / target_fps
        self._jpeg_quality = jpeg_quality
        self._last_send_time = 0.0
        self._frame_skip = max(1, int(60 / target_fps))
        self._frame_counter = 0

    def on_vblank(self, pixels: bytes, width: int, height: int) -> None:
        """Called from emulator thread on each vblank.

        Rate-limits and converts to JPEG, then publishes to EventBus
        on the asyncio event loop thread.
        """
        self._frame_counter = (self._frame_counter + 1) % 600  # Prevent unbounded growth
        if self._frame_counter % self._frame_skip != 0:
            return

        now = time.monotonic()
        if now - self._last_send_time < self._min_interval:
            return
        self._last_send_time = now

        if self._event_bus.subscriber_count == 0:
            return

        try:
            jpeg_data = self._pixels_to_jpeg(pixels, width, height)
        except Exception:
            return

        event = Event(type=EventType.FRAME, data=jpeg_data)
        self._loop.call_soon_threadsafe(self._event_bus.publish, event)

    def _pixels_to_jpeg(self, pixels: bytes, width: int, height: int) -> bytes:
        """Convert ARGB pixel data to JPEG bytes.

        SameBoy stores pixels as little-endian 0xAARRGGBB (BGRA in memory).
        Uses PIL channel split/merge for fast batch conversion (not per-pixel loop).
        """
        from PIL import Image

        # Load as RGBA (PIL reads bytes as R,G,B,A but memory is B,G,R,A)
        img = Image.frombytes("RGBA", (width, height), pixels)
        b, g, r, a = img.split()
        img = Image.merge("RGB", (r, g, b))

        # Scale 2x for dashboard (320x288)
        img = img.resize((width * 2, height * 2), resample=Image.NEAREST)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self._jpeg_quality)
        return buf.getvalue()
