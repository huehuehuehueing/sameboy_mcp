# SameBoy MCP Server

A Model Context Protocol (MCP) server that integrates the SameBoy Game Boy/Game Boy Color emulator with AI agents like Claude. This enables automated game analysis, reverse engineering, and computer vision tasks on Game Boy games.

## Overview

The SameBoy MCP Server provides a comprehensive set of tools for AI agents to interact with Game Boy games:

- **Memory Inspection** - Read and write any memory address
- **Screen Capture** - Get screenshots as PNG for vision models
- **CPU Control** - View registers, disassemble code, set breakpoints
- **Save States** - Save and restore game state instantly
- **Input Simulation** - Press buttons programmatically
- **Memory Monitoring** - Track memory changes to identify game variables

## Quick Start

```bash
# 1. Build libsameboy
cd sameboy_src/SameBoy-1.0.2
make lib CONF=release

# 2. Install Python dependencies
pip install mcp cffi pillow

# 3. Run the server
python -m sameboy_mcp.server \
    --lib sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so \
    --rom roms/supermarioland/Super\ Mario\ Land\ \(World\)\ \(Rev\ 1\).gb
```

## Documentation

- [Installation Guide](INSTALLATION.md) - Detailed setup instructions
- [API Reference](API.md) - Complete tool documentation
- [Architecture](ARCHITECTURE.md) - Technical implementation details
- [Examples](EXAMPLES.md) - Usage examples and tutorials

## Use Cases

### Game Analysis
Use Claude to automatically analyze game mechanics by watching memory changes as gameplay progresses.

### Reverse Engineering
Set breakpoints, trace execution, and disassemble code to understand how games work internally.

### Automated Testing
Write test scenarios that verify game behavior using save states and input simulation.

### Computer Vision Research
Capture game screens for training or testing vision models on pixel art and game UI.

### Speedrun Route Finding
Use save states and memory monitoring to explore game states and find optimal paths.

## Supported Games

The server supports all Game Boy and Game Boy Color games that SameBoy can run:
- Original Game Boy (DMG) games
- Game Boy Color (CGB) games
- Super Game Boy (SGB) enhanced games

## Requirements

- Python 3.10+
- Clang or GCC compiler
- Make build system

## License

This MCP server is provided for educational and research purposes. SameBoy is licensed under the MIT license. Game ROMs must be legally obtained.

## Contributing

Contributions are welcome. Please see the [Architecture](ARCHITECTURE.md) document for technical details on how the system works.
