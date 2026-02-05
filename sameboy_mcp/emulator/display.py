"""SDL2-based live display window for the emulator."""

import threading
import ctypes
from typing import Optional, Callable
from queue import Queue, Empty

try:
    import sdl2
    import sdl2.ext
    SDL2_AVAILABLE = True
except ImportError:
    SDL2_AVAILABLE = False


class LiveDisplay:
    """SDL2 window for displaying emulator frames in real-time."""

    # Display scaling options
    SCALE_1X = 1
    SCALE_2X = 2
    SCALE_3X = 3
    SCALE_4X = 4

    def __init__(self, width: int = 160, height: int = 144, scale: int = 2, title: str = "SameBoy MCP"):
        """
        Initialize the live display.

        Args:
            width: Base screen width (160 for GB, 256 for SGB)
            height: Base screen height (144 for GB, 224 for SGB)
            scale: Display scaling factor (1-4)
            title: Window title
        """
        if not SDL2_AVAILABLE:
            raise RuntimeError("PySDL2 is not installed. Install with: pip install pysdl2 pysdl2-dll")

        self.width = width
        self.height = height
        self.scale = scale
        self.title = title

        self._window: Optional[sdl2.SDL_Window] = None
        self._renderer: Optional[sdl2.SDL_Renderer] = None
        self._texture: Optional[sdl2.SDL_Texture] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_queue: Queue = Queue(maxsize=2)  # Buffer up to 2 frames

        self._lock = threading.Lock()
        self._initialized = False

        # Callback for input events
        self._input_callback: Optional[Callable[[str, bool], None]] = None

    def start(self) -> None:
        """Start the display window in a separate thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._display_loop, daemon=True)
        self._thread.start()

        # Wait for initialization
        while not self._initialized and self._running:
            pass

    def stop(self) -> None:
        """Stop the display window."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def update_frame(self, pixels: bytes) -> None:
        """
        Update the display with a new frame.

        Args:
            pixels: Raw ARGB pixel data (width * height * 4 bytes)
        """
        if not self._running:
            return

        # Drop old frames if queue is full (prevents lag)
        try:
            self._frame_queue.put_nowait(pixels)
        except:
            try:
                self._frame_queue.get_nowait()
                self._frame_queue.put_nowait(pixels)
            except:
                pass

    def set_input_callback(self, callback: Callable[[str, bool], None]) -> None:
        """
        Set callback for keyboard input events.

        Args:
            callback: Function called with (key_name, pressed) for each input event
        """
        self._input_callback = callback

    def resize(self, width: int, height: int) -> None:
        """Resize the display for different screen modes (e.g., SGB)."""
        with self._lock:
            if width != self.width or height != self.height:
                self.width = width
                self.height = height
                # Texture will be recreated on next frame

    def _display_loop(self) -> None:
        """Main display loop running in separate thread."""
        # Initialize SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) < 0:
            print(f"SDL initialization failed: {sdl2.SDL_GetError()}")
            self._running = False
            return

        # Create window
        self._window = sdl2.SDL_CreateWindow(
            self.title.encode('utf-8'),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            self.width * self.scale,
            self.height * self.scale,
            sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_RESIZABLE
        )

        if not self._window:
            print(f"Window creation failed: {sdl2.SDL_GetError()}")
            sdl2.SDL_Quit()
            self._running = False
            return

        # Create renderer
        self._renderer = sdl2.SDL_CreateRenderer(
            self._window, -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
        )

        if not self._renderer:
            print(f"Renderer creation failed: {sdl2.SDL_GetError()}")
            sdl2.SDL_DestroyWindow(self._window)
            sdl2.SDL_Quit()
            self._running = False
            return

        # Set scaling quality
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"nearest")

        # Create texture
        self._create_texture()

        self._initialized = True

        # Main loop
        event = sdl2.SDL_Event()
        while self._running:
            # Handle events
            while sdl2.SDL_PollEvent(ctypes.byref(event)):
                self._handle_event(event)

            # Update texture with new frame if available
            try:
                pixels = self._frame_queue.get_nowait()
                self._update_texture(pixels)
            except Empty:
                pass

            # Render
            sdl2.SDL_RenderClear(self._renderer)
            sdl2.SDL_RenderCopy(self._renderer, self._texture, None, None)
            sdl2.SDL_RenderPresent(self._renderer)

            # Small delay to prevent CPU spinning
            sdl2.SDL_Delay(1)

        # Cleanup
        if self._texture:
            sdl2.SDL_DestroyTexture(self._texture)
        if self._renderer:
            sdl2.SDL_DestroyRenderer(self._renderer)
        if self._window:
            sdl2.SDL_DestroyWindow(self._window)
        sdl2.SDL_Quit()
        self._initialized = False

    def _create_texture(self) -> None:
        """Create or recreate the texture for the current dimensions."""
        if self._texture:
            sdl2.SDL_DestroyTexture(self._texture)

        self._texture = sdl2.SDL_CreateTexture(
            self._renderer,
            sdl2.SDL_PIXELFORMAT_ARGB8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.width,
            self.height
        )

    def _update_texture(self, pixels: bytes) -> None:
        """Update the texture with new pixel data."""
        if not self._texture:
            return

        # Check if we need to resize
        expected_size = self.width * self.height * 4
        if len(pixels) != expected_size:
            return

        # Update texture
        sdl2.SDL_UpdateTexture(
            self._texture,
            None,
            pixels,
            self.width * 4
        )

    def _handle_event(self, event: sdl2.SDL_Event) -> None:
        """Handle SDL events."""
        if event.type == sdl2.SDL_QUIT:
            self._running = False
            return

        if event.type == sdl2.SDL_WINDOWEVENT:
            if event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
                self._running = False
            return

        # Handle keyboard input
        if event.type in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            pressed = event.type == sdl2.SDL_KEYDOWN
            key = self._sdl_key_to_gb_key(event.key.keysym.sym)
            if key and self._input_callback:
                self._input_callback(key, pressed)

    def _sdl_key_to_gb_key(self, sdl_key: int) -> Optional[str]:
        """Convert SDL key code to Game Boy button name."""
        key_map = {
            sdl2.SDLK_RIGHT: "right",
            sdl2.SDLK_LEFT: "left",
            sdl2.SDLK_UP: "up",
            sdl2.SDLK_DOWN: "down",
            sdl2.SDLK_z: "a",
            sdl2.SDLK_x: "b",
            sdl2.SDLK_RETURN: "start",
            sdl2.SDLK_RSHIFT: "select",
            sdl2.SDLK_LSHIFT: "select",
            sdl2.SDLK_BACKSPACE: "select",
        }
        return key_map.get(sdl_key)

    @property
    def is_running(self) -> bool:
        """Check if the display is running."""
        return self._running and self._initialized


def is_available() -> bool:
    """Check if live display is available (SDL2 installed)."""
    return SDL2_AVAILABLE
