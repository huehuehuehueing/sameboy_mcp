# SameBoy MCP Server

A Model Context Protocol (MCP) server that provides AI agents with full access to Game Boy and Game Boy Color emulation via the [SameBoy](https://sameboy.github.io/) emulator.

![SameBoy MCP in action: Surfing Pikachu, VRAM text injection, and multi-game support](docs/screenshots/collage.png)

## Features

- **Memory Inspection**: Read/write any memory address, monitor changes, compare snapshots
- **CPU Control**: Access registers, set breakpoints, trace execution, disassemble code
- **Display**: Capture screenshots, get sprite/OAM data, **live display window**
- **Save States**: Create, load, and manage save states
- **Input Simulation**: Press buttons, hold keys, simulate input sequences
- **Debugging**: Breakpoints, execution tracing, memory monitoring

## Quick Start

### Prerequisites

- Python 3.10+
- Built libsameboy shared library (see [Installation](docs/INSTALLATION.md))

### Installation

```bash
# Install core dependencies
pip install mcp cffi pillow

# Optional: Live display support
pip install pysdl2 pysdl2-dll

# Build libsameboy
cd sameboy_src/SameBoy-1.0.2
make lib CONF=release
```

### Usage

```bash
# Run the MCP server
python -m sameboy_mcp.server --lib path/to/libsameboy.so --rom path/to/game.gb
```

### MCP Configuration

Add to your Claude Code settings:

```json
{
  "mcpServers": {
    "sameboy": {
      "command": "python",
      "args": ["-m", "sameboy_mcp.server", "--lib", "/path/to/libsameboy.so"],
      "cwd": "/path/to/project_sameboy"
    }
  }
}
```

## Live Display

Watch the emulator in real-time with the SDL2 display window:

```python
# Enable live display via MCP tool
await enable_live_display(scale=2)

# Run emulation - frames appear in window
await run_frames(600)

# Close when done
await disable_live_display()
```

**Controls:**
- Arrow keys: D-pad
- Z: A button
- X: B button
- Enter: Start
- Shift: Select

## Dashboard

The server includes a built-in web dashboard for real-time monitoring of emulator state, game data, and agent activity.

![Dashboard showing live emulator screen, ASCII map, screen text decode, and game state](docs/screenshots/dashboard.png)

```bash
# Start the server with dashboard enabled
python -m sameboy_mcp.server \
  --lib path/to/libsameboy.so \
  --rom path/to/game.gb \
  --plugin examples.pokemon_agent.mcp_plugin \
  --dashboard --dashboard-port 31337
```

Open `http://localhost:31337` in a browser. The dashboard provides:

- **Live Screen** -- Emulator video feed streamed as JPEG frames at ~10fps via WebSocket
- **Game State** -- Map name, player coordinates, party count, badges, money (updated at 5Hz from a plugin snapshot hook)
- **ASCII Map** -- Collision grid with player position, warps, NPCs, and items, rendered from ROM blockset data. Updates on map changes and on every `render_ascii_map` tool call
- **Screen Text** -- Decoded tile map text (Gen 1 character encoding → readable strings). Updates on every `decode_screen_text`, `press_and_read`, or `wait_and_read` tool call
- **Controls** -- On-screen D-pad and buttons for manual input
- **Agent Log** -- Real-time stream of agent actions and tool calls

The dashboard is driven by an EventBus that receives data from three sources: the emulator's VBlank callback (frames), a 5Hz snapshot loop (game state + plugin hooks), and MCP tool calls (panel data pushed synchronously when tools execute). Plugins register custom panels via `dashboard.register_panels()` and push data via `PANEL_DATA` events. Late-joining WebSocket clients receive cached state for all panels on connect.

The dashboard is optional -- the server and all MCP tools work identically without it.

## Documentation

### Reference

- [Installation Guide](docs/INSTALLATION.md)
- [API Reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Examples](docs/EXAMPLES.md)
- [Testing](docs/TESTING.md)

### Pokemon Yellow Agent

Technical deep-dives into the Pokemon Yellow MCP agent and its subsystems:

- [RAM Vision](docs/RAM_VISION.md) — Reading game screens from memory instead of screenshots, plus the ASCII map renderer
- [The Nro of Pokemon](docs/THE_NRO_OF_POKEMON.md) — Map/tile/block hierarchy, collision, warps, sprites, and the rendering pipeline
- [Grab Da Potion](docs/GRAB_DA_POTION.md) — Complete MCP workflow: withdrawing an item from the PC using only RAM-based text decoding
- [Where Am I Bro](docs/WHERE_AM_I_BRO.md) — Finding and reading signs by memory address lookup

### Walkthrough

- [Don't Be a Menace to Pallet Town](docs/ADVENTURE_AHH_TIME.md) — A full adventure walkthrough demonstrating inventory hacking, Pokemon injection, warp table hijacking, and VRAM text injection through MCP tools

## Example Use Cases

- **Game Analysis**: Find where games store health, score, position
- **Reverse Engineering**: Trace code execution, disassemble routines
- **Automated Testing**: Script input sequences, verify game state
- **AI Game Playing**: Let AI agents observe and interact with games
- **ROM Hacking**: Modify memory, test patches in real-time

## Project Structure

```
project_sameboy/
├── sameboy_mcp/               # MCP server implementation
│   ├── emulator/              # libsameboy wrapper
│   │   ├── bindings.py        # cffi declarations
│   │   ├── core.py            # Emulator class
│   │   ├── thread.py          # Background execution
│   │   └── display.py         # SDL2 live display
│   ├── dashboard/             # Web dashboard (WebSocket + static HTML/JS)
│   │   ├── __init__.py        # DashboardServer, snapshot loop, panel registry
│   │   ├── events.py          # EventBus, Event types, AgentEventSink
│   │   ├── frame_relay.py     # VBlank → JPEG frame rate limiter
│   │   └── static/            # Frontend (dashboard.js, index.html, styles)
│   ├── tools/                 # MCP tool modules
│   └── server.py              # MCP entry point (supports --plugin, --dashboard)
├── examples/
│   └── pokemon_agent/         # Pokemon Yellow AI agent
│       ├── mcp_plugin.py      # Game-specific MCP tools (text decoder, ASCII map)
│       ├── main.py            # Agent entry point
│       ├── memory_map.py      # WRAM addresses & character encoding
│       ├── game_state.py      # State reading & mode detection
│       ├── routines.py        # BFS pathfinding & game interaction
│       ├── area_analyzer.py   # MCP-driven area analysis
│       └── saved_states/      # Pre-captured game states
├── sameboy_src/               # SameBoy source code
└── docs/                      # Documentation & walkthroughs
```

## Contributors

- **Larry H** (Dartmouth College) - Primary author
- **Way Barrios** (@waybarrios) - AI Wizard

## License

This project is licensed under the MIT License.

The SameBoy emulator is developed by [Lior Halphon](https://github.com/LIJI32/SameBoy) and is licensed under the MIT License.

## Acknowledgments

- [SameBoy](https://sameboy.github.io/) - Accurate Game Boy/GBC emulator
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI agent integration protocol
- [PySDL2](https://pysdl2.readthedocs.io/) - SDL2 bindings for Python
