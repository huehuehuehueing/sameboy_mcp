# Copyright (c) 2025 Larry H (l.gr [at] dartmouth [dot] edu)
# SPDX-License-Identifier: MIT
"""SDL2 audio output for Game Boy emulator."""

import threading
import array
from collections import deque

# Check if SDL2 is available
_sdl2_available = False
try:
    import sdl2
    import sdl2.ext
    import ctypes
    _sdl2_available = True
except ImportError:
    pass


def is_available() -> bool:
    """Check if SDL2 audio is available."""
    return _sdl2_available


# Audio constants
SAMPLE_RATE = 48000  # Standard audio sample rate
BUFFER_SIZE = 2048   # Samples per buffer (larger for stability)
RING_BUFFER_SIZE = 16384  # Total samples in ring buffer


class AudioPlayer:
    """
    SDL2-based audio player for Game Boy audio.

    Uses a ring buffer to collect samples from the emulator's audio callback
    and plays them through SDL2's audio subsystem.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """
        Initialize the audio player.

        Args:
            sample_rate: Audio sample rate in Hz (default 48000)
        """
        if not _sdl2_available:
            raise RuntimeError("SDL2 is not available. Install with: pip install pysdl2 pysdl2-dll")

        self._sample_rate = sample_rate
        self._device_id = 0
        self._running = False
        self._lock = threading.Lock()

        # Ring buffer for audio samples (stereo interleaved: L, R, L, R, ...)
        self._buffer = array.array('h')  # Signed 16-bit integers
        self._buffer_maxlen = RING_BUFFER_SIZE * 2  # Stereo

        # Keep callback reference alive
        self._callback_ref = None

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._sample_rate

    @property
    def is_running(self) -> bool:
        """Check if audio is playing."""
        return self._running

    def start(self) -> bool:
        """
        Start audio playback.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        # Initialize SDL audio subsystem
        if sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO) < 0:
            return False

        # Create the callback
        def audio_callback(userdata, stream, length):
            # length is in bytes, we need samples (2 bytes per sample, 2 channels)
            samples_needed = length // 2  # Number of int16 values needed

            with self._lock:
                available = len(self._buffer)
                to_copy = min(available, samples_needed)

                if to_copy > 0:
                    # Copy available samples
                    data = self._buffer[:to_copy]
                    # Remove copied samples
                    del self._buffer[:to_copy]
                else:
                    data = array.array('h')

            # Fill the rest with silence if needed
            if to_copy < samples_needed:
                silence = array.array('h', [0] * (samples_needed - to_copy))
                data.extend(silence)

            # Copy to stream
            ctypes.memmove(stream, data.buffer_info()[0], length)

        # Store callback reference
        self._callback_ref = sdl2.SDL_AudioCallback(audio_callback)

        # Create audio spec with all required parameters
        wanted = sdl2.SDL_AudioSpec(
            freq=self._sample_rate,
            aformat=sdl2.AUDIO_S16SYS,  # Signed 16-bit native endian
            channels=2,  # Stereo
            samples=BUFFER_SIZE,
            callback=self._callback_ref,
            userdata=None
        )

        obtained = sdl2.SDL_AudioSpec(0, 0, 0, 0)

        # Open audio device
        self._device_id = sdl2.SDL_OpenAudioDevice(
            None,  # Default device
            0,     # Not capture
            wanted,
            ctypes.byref(obtained),
            sdl2.SDL_AUDIO_ALLOW_FREQUENCY_CHANGE
        )

        if self._device_id == 0:
            error = sdl2.SDL_GetError()
            print(f"SDL audio error: {error.decode() if error else 'unknown'}")
            return False

        # Update sample rate if changed
        self._sample_rate = obtained.freq

        # Start playback (0 = unpause)
        sdl2.SDL_PauseAudioDevice(self._device_id, 0)
        self._running = True

        return True

    def stop(self) -> None:
        """Stop audio playback."""
        if not self._running:
            return

        self._running = False

        if self._device_id:
            sdl2.SDL_PauseAudioDevice(self._device_id, 1)
            sdl2.SDL_CloseAudioDevice(self._device_id)
            self._device_id = 0

        with self._lock:
            self._buffer = array.array('h')

    def push_sample(self, left: int, right: int) -> None:
        """
        Push a stereo sample to the audio buffer.

        Args:
            left: Left channel sample (int16)
            right: Right channel sample (int16)
        """
        with self._lock:
            # Prevent buffer from growing too large
            if len(self._buffer) < self._buffer_maxlen:
                self._buffer.append(left)
                self._buffer.append(right)

    def get_buffer_level(self) -> float:
        """
        Get the current buffer fill level.

        Returns:
            Fill level from 0.0 (empty) to 1.0 (full)
        """
        with self._lock:
            return len(self._buffer) / self._buffer_maxlen


class AudioHandler:
    """
    Handles audio integration between SameBoy and SDL2.

    This class sets up the audio callback from SameBoy and routes
    samples to the SDL2 audio player.
    """

    def __init__(self, lib, gb, sample_rate: int = SAMPLE_RATE):
        """
        Initialize the audio handler.

        Args:
            lib: The loaded libsameboy library
            gb: The GB_gameboy_t pointer
            sample_rate: Desired sample rate
        """
        from .bindings import ffi

        self._lib = lib
        self._gb = gb
        self._ffi = ffi
        self._player: AudioPlayer | None = None
        self._sample_callback = None
        self._enabled = False

        # Set sample rate on emulator
        lib.GB_set_sample_rate(gb, sample_rate)
        lib.GB_set_highpass_filter_mode(gb, 1)  # GB_HIGHPASS_ACCURATE

    def enable(self) -> bool:
        """
        Enable audio playback.

        Returns:
            True if enabled successfully
        """
        if self._enabled:
            return True

        if not is_available():
            return False

        # Create player
        sample_rate = self._lib.GB_get_sample_rate(self._gb)
        self._player = AudioPlayer(sample_rate)

        if not self._player.start():
            self._player = None
            return False

        # Set up sample callback
        @self._ffi.callback("GB_sample_callback_t")
        def sample_callback(gb, sample):
            if self._player and self._player.is_running:
                self._player.push_sample(sample.left, sample.right)

        self._sample_callback = sample_callback
        self._lib.GB_apu_set_sample_callback(self._gb, self._sample_callback)

        self._enabled = True
        return True

    def disable(self) -> None:
        """Disable audio playback."""
        if not self._enabled:
            return

        # Remove callback first
        self._lib.GB_apu_set_sample_callback(self._gb, self._ffi.NULL)

        # Stop player
        if self._player:
            self._player.stop()
            self._player = None

        self._sample_callback = None
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if audio is enabled."""
        return self._enabled

    def set_channel_muted(self, channel: int, muted: bool) -> None:
        """
        Mute or unmute an audio channel.

        Args:
            channel: Channel index (0=Square1, 1=Square2, 2=Wave, 3=Noise)
            muted: Whether to mute
        """
        if 0 <= channel < 4:
            self._lib.GB_set_channel_muted(self._gb, channel, muted)

    def is_channel_muted(self, channel: int) -> bool:
        """Check if a channel is muted."""
        if 0 <= channel < 4:
            return self._lib.GB_is_channel_muted(self._gb, channel)
        return False
