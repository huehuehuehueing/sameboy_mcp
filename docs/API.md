# API Reference

Complete documentation for all MCP tools provided by the SameBoy MCP Server.

## Table of Contents

- [ROM Management](#rom-management)
- [Memory Tools](#memory-tools)
- [CPU Tools](#cpu-tools)
- [Display Tools](#display-tools)
- [Control Tools](#control-tools)
- [Save State Tools](#save-state-tools)
- [Debug Tools](#debug-tools)
- [Memory Monitoring Tools](#memory-monitoring-tools)

---

## ROM Management

### `load_rom`
Load a Game Boy ROM file.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `path` | string | Path to the ROM file (.gb or .gbc) |

**Returns:**
```json
{
  "success": true,
  "path": "/path/to/game.gb",
  "title": "GAME TITLE"
}
```

### `load_boot_rom`
Load a Game Boy boot ROM (optional, for accurate boot sequence).

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `path` | string | Path to the boot ROM file |

**Returns:**
```json
{
  "success": true,
  "path": "/path/to/boot.bin"
}
```

### `get_status`
Get current emulator status.

**Parameters:** None

**Returns:**
```json
{
  "state": "PAUSED",
  "rom_loaded": true,
  "rom_title": "POKEMON YELLOW",
  "frame_count": 1234,
  "is_cgb": true,
  "trace_enabled": false,
  "breakpoint_count": 0,
  "monitored_addresses": 0
}
```

### `help`
Get information about available tools.

**Parameters:** None

**Returns:** Dictionary of tool categories and descriptions.

---

## Memory Tools

### `read_memory`
Read bytes from Game Boy memory.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `address` | int | required | Memory address (0x0000-0xFFFF) |
| `length` | int | 1 | Number of bytes to read (max 256) |

**Returns:**
```json
{
  "address": "0xC000",
  "length": 16,
  "hex": "0102030405060708090a0b0c0d0e0f10",
  "bytes": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
}
```

**Memory Map Reference:**
| Range | Description |
|-------|-------------|
| 0x0000-0x3FFF | ROM Bank 0 |
| 0x4000-0x7FFF | ROM Bank N (switchable) |
| 0x8000-0x9FFF | Video RAM |
| 0xA000-0xBFFF | Cartridge RAM |
| 0xC000-0xDFFF | Work RAM |
| 0xE000-0xFDFF | Echo RAM |
| 0xFE00-0xFE9F | OAM (Sprite data) |
| 0xFF00-0xFF7F | I/O Registers |
| 0xFF80-0xFFFE | High RAM |
| 0xFFFF | Interrupt Enable |

### `write_memory`
Write a byte to Game Boy memory.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `address` | int | Memory address (0x0000-0xFFFF) |
| `value` | int | Byte value to write (0x00-0xFF) |

**Returns:**
```json
{
  "success": true,
  "address": "0xC100",
  "value": "0x42"
}
```

### `read_memory_region`
Read an entire memory region.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `region` | string | Region name: rom, ram, vram, oam, hram, cart_ram, io |

**Returns:**
```json
{
  "region": "ram",
  "size": 8192,
  "bank": 0,
  "data_base64": "base64encodeddata..."
}
```

---

## CPU Tools

### `get_registers`
Get current CPU register values.

**Parameters:** None

**Returns:**
```json
{
  "16-bit": {
    "AF": "0x01B0",
    "BC": "0x0013",
    "DE": "0x00D8",
    "HL": "0x014D",
    "SP": "0xFFFE",
    "PC": "0x0100"
  },
  "8-bit": {
    "A": "0x01",
    "F": "0xB0",
    "B": "0x00",
    "C": "0x13",
    "D": "0x00",
    "E": "0xD8",
    "H": "0x01",
    "L": "0x4D"
  },
  "flags": {
    "Z": true,
    "N": false,
    "H": true,
    "C": true
  },
  "raw": {
    "AF": 432,
    "BC": 19,
    "DE": 216,
    "HL": 333,
    "SP": 65534,
    "PC": 256
  }
}
```

**Flag Meanings:**
- **Z** (Zero): Set if result is zero
- **N** (Subtract): Set if last operation was subtraction
- **H** (Half Carry): Set if carry from bit 3
- **C** (Carry): Set if carry from bit 7

### `disassemble`
Disassemble instructions at an address.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `address` | int | current PC | Starting address |
| `count` | int | 10 | Number of instructions (max 50) |

**Returns:**
```json
{
  "address": "0x0150",
  "count": 10,
  "disassembly": "0x0150: NOP\n0x0151: JP $0150\n..."
}
```

---

## Display Tools

### `capture_screen`
Capture the current screen.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `format` | string | "png" | Image format: "png" or "raw" |

**Returns:**
```json
{
  "width": 160,
  "height": 144,
  "format": "png",
  "data_base64": "iVBORw0KGgo..."
}
```

**Notes:**
- PNG format is recommended for AI vision models
- Raw format returns ARGB32 pixel data
- Screen size is 160x144 (256x224 with SGB border)

### `get_sprites`
Get information about all sprites (OAM entries).

**Parameters:** None

**Returns:**
```json
{
  "count": 10,
  "sprites": [
    {
      "index": 0,
      "x": 80,
      "y": 72,
      "tile": 42,
      "flags": 0,
      "oam_address": "0xFE00",
      "obscured": false
    }
  ]
}
```

**Sprite Flags:**
- Bit 7: Priority (0=above BG, 1=behind BG colors 1-3)
- Bit 6: Y flip
- Bit 5: X flip
- Bit 4: Palette (DMG only)
- Bits 0-2: Palette (CGB only)

### `get_screen_info`
Get current screen dimensions and frame info.

**Parameters:** None

**Returns:**
```json
{
  "width": 160,
  "height": 144,
  "frame_count": 5432
}
```

---

## Control Tools

### `pause`
Pause emulation.

**Returns:**
```json
{
  "success": true,
  "state": "paused"
}
```

### `resume`
Resume emulation.

**Returns:**
```json
{
  "success": true,
  "state": "running"
}
```

### `step_frame`
Execute one frame and pause.

**Returns:**
```json
{
  "success": true,
  "frame": 1235,
  "breakpoint_hit": false
}
```

### `step_instruction`
Execute one CPU instruction.

**Returns:**
```json
{
  "success": true,
  "cycles": 4,
  "breakpoint_hit": false
}
```

### `reset`
Reset the emulator.

**Returns:**
```json
{
  "success": true
}
```

### `press_key`
Press a joypad button for a number of frames.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `key` | string | required | Button name |
| `frames` | int | 1 | Frames to hold (max 600) |

**Valid Keys:** `a`, `b`, `start`, `select`, `up`, `down`, `left`, `right`

**Returns:**
```json
{
  "success": true,
  "key": "a",
  "frames": 1
}
```

### `press_keys`
Press multiple buttons simultaneously.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `keys` | list[str] | required | List of button names |
| `frames` | int | 1 | Frames to hold |

**Returns:**
```json
{
  "success": true,
  "keys": ["a", "right"],
  "frames": 1
}
```

### `set_key`
Set a button state without advancing frames.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `key` | string | Button name |
| `pressed` | bool | Whether pressed |

### `run_frames`
Run emulation for multiple frames.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `count` | int | required | Frames to run (max 3600) |

**Returns:**
```json
{
  "success": true,
  "frames_requested": 100,
  "frames_run": 100,
  "breakpoint_hit": false
}
```

### `set_turbo`
Enable or disable turbo mode (fast-forward).

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `enabled` | bool | required | Enable turbo |
| `no_frame_skip` | bool | false | Render all frames |

---

## Save State Tools

### `save_state`
Save the current emulator state.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | string | null | Optional name |

**Returns:**
```json
{
  "state_id": "a1b2c3d4",
  "name": "before_boss",
  "size_bytes": 83444,
  "frame": 12345
}
```

### `load_state`
Load a previously saved state.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `state_id` | string | ID from save_state |

**Returns:**
```json
{
  "success": true,
  "state_id": "a1b2c3d4",
  "name": "before_boss",
  "restored_from_frame": 12345
}
```

### `list_states`
List all saved states.

**Returns:**
```json
{
  "count": 3,
  "states": [
    {
      "state_id": "a1b2c3d4",
      "name": "before_boss",
      "frame": 12345,
      "size_bytes": 83444,
      "timestamp": 1707100000.0
    }
  ]
}
```

### `delete_state`
Delete a saved state.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `state_id` | string | ID to delete |

### `export_state`
Export a state as base64 for external storage.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `state_id` | string | ID to export |

**Returns:**
```json
{
  "state_id": "a1b2c3d4",
  "name": "before_boss",
  "frame": 12345,
  "size_bytes": 83444,
  "data_base64": "base64data..."
}
```

### `import_state`
Import a state from base64 data.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `data_base64` | string | required | Base64 state data |
| `name` | string | null | Optional name |

---

## Debug Tools

### `set_breakpoint`
Set a breakpoint at an address.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `address` | int | required | Address (0x0000-0xFFFF) |
| `enabled` | bool | true | Active state |

**Returns:**
```json
{
  "success": true,
  "address": "0x0150",
  "enabled": true
}
```

### `remove_breakpoint`
Remove a breakpoint.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `address` | int | Address to remove |

### `list_breakpoints`
List all breakpoints.

**Returns:**
```json
{
  "count": 2,
  "breakpoints": [
    {
      "address": "0x0150",
      "enabled": true,
      "hit_count": 5
    }
  ]
}
```

### `clear_breakpoints`
Clear all breakpoints.

### `enable_trace`
Enable or disable execution tracing.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `enabled` | bool | true | Enable tracing |
| `limit` | int | 10000 | Max entries to keep |

**Returns:**
```json
{
  "success": true,
  "trace_enabled": true,
  "limit": 10000
}
```

### `get_trace`
Get recent execution trace entries.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `count` | int | 100 | Entries to retrieve |

**Returns:**
```json
{
  "count": 100,
  "trace": [
    {
      "address": "0x0150",
      "opcode": "0x00",
      "frame": 1234
    }
  ]
}
```

### `clear_trace`
Clear the execution trace buffer.

---

## Memory Monitoring Tools

### `monitor_memory`
Start monitoring memory addresses for changes.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `addresses` | list[int] | Addresses to monitor (max 256) |

**Returns:**
```json
{
  "success": true,
  "addresses_added": 5,
  "addresses": ["0xC000", "0xC001", "0xC002", "0xC003", "0xC004"]
}
```

### `stop_monitor`
Stop monitoring addresses.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `addresses` | list[int] | null | Specific addresses (null = all) |

### `get_memory_changes`
Get detected memory changes.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `since_frame` | int | null | Only after this frame |

**Returns:**
```json
{
  "count": 3,
  "since_frame": 1000,
  "changes": [
    {
      "address": "0xC000",
      "old_value": "0x42",
      "new_value": "0x43",
      "frame": 1005
    }
  ]
}
```

### `clear_memory_changes`
Clear the memory change log.

### `take_memory_snapshot`
Take a snapshot of current RAM state.

**Returns:**
```json
{
  "success": true,
  "note": "Snapshot taken. Use compare_memory_snapshot to find changes."
}
```

### `compare_memory_snapshot`
Compare current RAM with previous snapshot.

**Returns:**
```json
{
  "change_count": 42,
  "changes": {
    "0xC100": {"old": 5, "new": 4},
    "0xC200": {"old": 100, "new": 99}
  }
}
```

### `find_value`
Search memory for a specific value.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `value` | int | required | Value to find |
| `size` | int | 1 | Size: 1, 2, or 4 bytes |
| `region` | string | "ram" | Region: ram, hram, all |

**Returns:**
```json
{
  "value": 99,
  "size": 1,
  "region": "ram",
  "match_count": 5,
  "matches": ["0xC100", "0xC234", "0xC567", "0xC890", "0xCABC"],
  "truncated": false
}
```
