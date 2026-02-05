# Architecture

Technical documentation for the SameBoy MCP Server implementation.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           AI Agent (Claude)                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ MCP Protocol (JSON-RPC over stdio)
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          MCP Server (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   server.py  │  │   tools/*    │  │   State Cache            │  │
│  │  (Entry pt)  │  │  (28 tools)  │  │   (Save states)          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                           │                                         │
│                           │ Command Queue                           │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    EmulatorThread                             │  │
│  │  • Runs emulation loop in background                         │  │
│  │  • Processes commands from queue                             │  │
│  │  • Returns results via response queues                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│                           │ cffi calls                              │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    SameBoyEmulator                            │  │
│  │  • Wraps libsameboy functions                                │  │
│  │  • Manages callbacks                                         │  │
│  │  • Provides high-level Python API                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ cffi ABI mode
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       libsameboy.so (C Library)                     │
│  • Core Game Boy/GBC emulation                                      │
│  • CPU, PPU, APU, Memory, Timers                                   │
│  • Debugger, Save States, Rewind                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. MCP Server (`server.py`)

The entry point that:
- Initializes the emulator with specified model
- Registers all tool modules
- Starts the emulator thread
- Runs the MCP protocol handler on stdio

```python
async def run_server(lib_path, rom_path, model):
    server, emulator, emu_thread = create_server(lib_path, rom_path, model)
    emu_thread.start()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, ...)
```

### 2. Emulator Thread (`thread.py`)

Manages background emulation with thread-safe command processing:

```python
class EmulatorThread:
    def _run_loop(self):
        while not self._stop_flag.is_set():
            self._process_commands()

            if state == EmulatorState.RUNNING:
                self.emulator.run_frame()
                # Frame timing for ~60fps
            elif state == EmulatorState.PAUSED:
                time.sleep(0.01)
```

**Command Pattern:**
- Commands are enqueued from MCP tool handlers
- Each command has a response queue for synchronous waiting
- Thread-safe via Python's Queue

### 3. Emulator Wrapper (`core.py`)

High-level Python wrapper around libsameboy:

```python
class SameBoyEmulator:
    def __init__(self, lib_path):
        self.lib = load_library(lib_path)
        self._pixel_buffer = ffi.new("uint32_t[...]")
        self._callbacks = {}

    def init(self, model):
        self.gb = self.lib.GB_alloc()
        self.lib.GB_init(self.gb, MODEL_MAP[model])
        self._setup_callbacks()
```

**Callback Management:**
Callbacks are stored in `self._callbacks` to prevent garbage collection:

```python
@ffi.callback("void(GB_gameboy_t*, uint16_t, uint8_t)")
def execution_cb(gb, address, opcode):
    if self._trace_enabled:
        self._execution_trace.append(...)
    if address in self._breakpoints:
        self._breakpoint_hit = True

self._callbacks["execution"] = execution_cb
self.lib.GB_set_execution_callback(self.gb, execution_cb)
```

### 4. cffi Bindings (`bindings.py`)

Declares C types and functions for cffi ABI mode:

```python
ffi = FFI()
ffi.cdef("""
    typedef struct GB_gameboy_s GB_gameboy_t;
    typedef enum { GB_MODEL_DMG_B = 0x002, ... } GB_model_t;

    GB_gameboy_t *GB_alloc(void);
    GB_gameboy_t *GB_init(GB_gameboy_t *gb, GB_model_t model);
    unsigned GB_run(GB_gameboy_t *gb);
    uint8_t GB_safe_read_memory(GB_gameboy_t *gb, uint16_t addr);
    ...
""")

lib = ffi.dlopen("/path/to/libsameboy.so")
```

## Threading Model

```
Main Thread                    Emulator Thread
────────────                   ───────────────
MCP tool called
    │
    ├─► Command enqueued ─────► Command dequeued
    │                               │
    │   (waiting)                   ├─► Execute on emulator
    │                               │
    │   ◄───── Response ────────────┘
    │
Tool returns
```

**Key Design Decisions:**

1. **Single Emulator Thread**: All emulator operations happen on one thread to avoid synchronization issues with libsameboy's internal state.

2. **Synchronous Command/Response**: MCP tools wait for responses, making the API appear synchronous to callers.

3. **Frame-Rate Limiting**: When running, the thread sleeps to maintain ~60fps. This prevents CPU spinning while allowing responsive command processing.

## Memory Model

### Address Space
```
0x0000 ┌───────────────────────┐
       │ ROM Bank 0 (16KB)     │
0x4000 ├───────────────────────┤
       │ ROM Bank N (16KB)     │  ← Switchable
0x8000 ├───────────────────────┤
       │ Video RAM (8KB)       │
0xA000 ├───────────────────────┤
       │ Cartridge RAM (8KB)   │  ← If present
0xC000 ├───────────────────────┤
       │ Work RAM (8KB)        │  ← Main game state
0xE000 ├───────────────────────┤
       │ Echo RAM              │
0xFE00 ├───────────────────────┤
       │ OAM (160 bytes)       │  ← Sprite attributes
0xFEA0 ├───────────────────────┤
       │ Unusable              │
0xFF00 ├───────────────────────┤
       │ I/O Registers         │  ← Hardware control
0xFF80 ├───────────────────────┤
       │ High RAM (127 bytes)  │  ← Fast access
0xFFFF └───────────────────────┘
       │ Interrupt Enable      │
```

### Memory Access

- **`GB_safe_read_memory`**: Reads without side effects (used by tools)
- **`GB_read_memory`**: May trigger hardware behavior
- **`GB_write_memory`**: Standard write
- **`GB_get_direct_access`**: Direct pointer to memory regions

## Save State Format

SameBoy uses the BESS (Binary Save State Standard) format:

```
┌─────────────────────────────────┐
│ Header                          │
│   Magic: 'SAME' or 'S4ME'       │
│   Version: struct version       │
├─────────────────────────────────┤
│ Core State                      │
│   Registers (AF, BC, DE, HL,    │
│              SP, PC)            │
│   IME, Interrupt Enable         │
│   Flags (halted, stopped, etc.) │
├─────────────────────────────────┤
│ DMA/HDMA State                  │
├─────────────────────────────────┤
│ MBC State                       │
│   ROM/RAM bank numbers          │
│   MBC-specific state            │
├─────────────────────────────────┤
│ HRAM + I/O Registers            │
├─────────────────────────────────┤
│ Timing State                    │
│   DIV counter, TIMA state       │
│   PPU timing                    │
├─────────────────────────────────┤
│ APU State                       │
│   Channel registers and state   │
├─────────────────────────────────┤
│ Video State                     │
│   VRAM, OAM, Palettes           │
│   PPU internal state            │
├─────────────────────────────────┤
│ Accessory State (if present)    │
│   Printer, Workboy              │
└─────────────────────────────────┘
```

## Callback Hooks

libsameboy provides several callback hooks used by the MCP server:

| Callback | Purpose | MCP Usage |
|----------|---------|-----------|
| `vblank_callback` | Called each frame (vblank) | Frame counting |
| `execution_callback` | Called for each instruction | Tracing, breakpoints |
| `write_memory_callback` | Called before memory writes | Memory monitoring |
| `log_callback` | Receives log messages | Disassembly capture |
| `rgb_encode_callback` | Pixel format conversion | Screen capture |

## Tool Modules

Each tool module registers tools with the MCP server:

```python
def register_memory_tools(server: Server, emu_thread: EmulatorThread):
    @server.tool()
    async def read_memory(address: int, length: int = 1) -> dict:
        result = emu_thread.send_command(CommandType.READ_MEMORY_RANGE, {
            "start": address,
            "length": length
        })
        return {"hex": result["data"].hex(), ...}
```

**Tool Categories:**
- `memory.py` - Memory read/write
- `cpu.py` - Registers, disassembly
- `display.py` - Screenshots, sprites
- `state.py` - Save states
- `debug.py` - Breakpoints, tracing
- `control.py` - Execution control, input
- `monitor.py` - Memory monitoring

## Performance Considerations

1. **Execution Callback**: Called for every instruction (~4M/second). Keep processing minimal.

2. **Memory Monitoring**: Uses write callback with address set lookup. O(1) per write.

3. **Screen Capture**: Converts ARGB to PNG using PIL. ~5-10ms per frame.

4. **Save States**: ~80KB per state, serialization is fast (<1ms).

5. **Command Latency**: Queue operations add ~1ms overhead.

## Error Handling

Errors are returned in tool responses:

```json
{
  "error": "Failed to load ROM: file not found"
}
```

The emulator thread catches exceptions and returns them via the response queue:

```python
try:
    result = self._execute_command(cmd)
except Exception as e:
    result = {"error": str(e)}
cmd.response_queue.put(result)
```

## Future Improvements

1. **Audio Output**: Add audio sample callback for sound analysis
2. **Link Cable**: Support two emulator instances communicating
3. **Cheats**: Expose cheat system via MCP tools
4. **Rewind**: Expose rewind buffer for time manipulation
5. **Symbol Loading**: Load .sym files for address labeling
