# Installation Guide

This guide covers building and installing the SameBoy MCP Server.

## Prerequisites

### System Requirements

- **OS**: Linux, macOS, or Windows (WSL recommended)
- **Python**: 3.10 or later
- **Compiler**: Clang (recommended) or GCC
- **Build Tools**: Make

### Installing Dependencies

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install build-essential clang python3 python3-pip python3-venv
```

#### macOS
```bash
xcode-select --install
brew install python3
```

#### Arch Linux
```bash
sudo pacman -S base-devel clang python python-pip
```

## Building libsameboy

The MCP server requires the SameBoy core library built as a shared library.

### 1. Navigate to SameBoy Source
```bash
cd sameboy_src/SameBoy-1.0.2
```

### 2. Build the Library
```bash
# Release build (recommended)
make lib CONF=release

# Debug build (for development)
make lib CONF=debug
```

### 3. Verify Build
```bash
ls -la build/lib/
# Should show:
#   libsameboy.so   (Linux)
#   libsameboy.dylib (macOS)
#   libsameboy.a    (static library)
```

The shared library will be at:
- Linux: `build/lib/libsameboy.so`
- macOS: `build/lib/libsameboy.dylib`

## Installing Python Dependencies

### Using pip
```bash
pip install mcp cffi pillow
```

### Optional: Live Display Support
For the real-time display window feature:
```bash
pip install pysdl2 pysdl2-dll
```

### Using a Virtual Environment (Recommended)
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install mcp cffi pillow

# Optional: Live display support
pip install pysdl2 pysdl2-dll
```

### Using the Package
```bash
# From the project directory
pip install -e sameboy_mcp/

# With live display support
pip install -e "sameboy_mcp/[display]"
```

## Configuration

### MCP Server Configuration

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project settings):

```json
{
  "mcpServers": {
    "sameboy": {
      "command": "python",
      "args": [
        "-m", "sameboy_mcp.server",
        "--lib", "/absolute/path/to/libsameboy.so"
      ],
      "cwd": "/path/to/project_sameboy",
      "env": {
        "PYTHONPATH": "/path/to/project_sameboy"
      }
    }
  }
}
```

### With a Default ROM
```json
{
  "mcpServers": {
    "sameboy": {
      "command": "python",
      "args": [
        "-m", "sameboy_mcp.server",
        "--lib", "/path/to/libsameboy.so",
        "--rom", "/path/to/game.gb",
        "--model", "CGB_E"
      ],
      "cwd": "/path/to/project_sameboy"
    }
  }
}
```

## Verifying Installation

### Test Library Loading
```bash
cd /path/to/project_sameboy
python3 -c "
from sameboy_mcp.emulator.bindings import load_library
lib = load_library('sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so')
print('Library loaded successfully!')
"
```

### Test Emulator Initialization
```bash
python3 -c "
from sameboy_mcp.emulator.core import SameBoyEmulator
emu = SameBoyEmulator('sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so')
emu.init('CGB_E')
print(f'Emulator initialized: {emu.get_status()}')
emu.free()
"
```

### Test ROM Loading
```bash
python3 -c "
from sameboy_mcp.emulator.core import SameBoyEmulator
emu = SameBoyEmulator('sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so')
emu.init('CGB_E')
emu.load_rom('roms/tetris2/Tetris 2 (USA).gb')
print(f'ROM: {emu.rom_title}')
for _ in range(60):
    emu.run_frame()
print(f'Ran 60 frames')
emu.free()
"
```

## Troubleshooting

### "Library not found" Error
- Ensure libsameboy.so was built: `ls sameboy_src/SameBoy-1.0.2/build/lib/`
- Use absolute path to the library
- On Linux, you may need: `export LD_LIBRARY_PATH=/path/to/build/lib:$LD_LIBRARY_PATH`

### "No module named 'mcp'" Error
```bash
pip install mcp
```

### "cffi" Import Errors
```bash
pip install --upgrade cffi
```

### Build Errors
- Ensure clang is installed: `clang --version`
- Try with GCC: `make lib CONF=release CC=gcc`
- Check for missing headers: `sudo apt install build-essential`

### Permission Denied
```bash
chmod +x sameboy_src/SameBoy-1.0.2/build/lib/libsameboy.so
```

## Platform-Specific Notes

### Linux
The shared library is `libsameboy.so`. No additional configuration needed.

### macOS
The shared library is `libsameboy.dylib`. You may need to allow it in System Preferences > Security if blocked.

### Windows (WSL)
Use Windows Subsystem for Linux. Build and run inside WSL for best compatibility.

## Next Steps

- Read the [API Reference](API.md) for available tools
- Try the [Examples](EXAMPLES.md) to get started
- Review the [Architecture](ARCHITECTURE.md) for technical details
