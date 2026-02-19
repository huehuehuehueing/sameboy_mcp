# Pokemon Yellow ROM Patches & Tricks

Documented ROM patches for Pokemon Yellow (USA/Europe) using the SameBoy MCP `patch_rom` tool.

## Walk Through Walls

Bypasses all collision checks so the player can walk through any solid tile, NPC, or barrier.

### Background

Pokemon Yellow has **two collision gate paths** in the overworld movement loop (bank 0). Both must be patched:

1. **Normal path** (0x0394): `CollisionCheckOnLand` at `$0A1C`, gated by `JR nc` at 0x0397
2. **Alternate path** (0x03AE): Secondary collision check at `$0CCA`, gated by `JP c` at 0x03B1 (only taken when `[wMovementFlags]` == 2)

The collision function at `$0A1C` checks three things:
- Sprite collisions (NPCs, Pikachu)
- Tile pair collisions (forbidden tile combinations)
- Tile passability (`wTileInFrontOfPlayer` at 0xCFC5 via `IsTilePassable` at `$15C3`)

If any check fails, carry flag is set and movement is blocked.

### Patches

**Patch 1 — Normal collision gate (0x0397)**

Change `JR nc, $03B4` to unconditional `JR $03B4`:

| Address | Original | Patched | Instruction |
|---------|----------|---------|-------------|
| 0x0397  | 0x30     | 0x18    | `JR nc` -> `JR` (unconditional) |

```
; Before:
0394: CALL $0A1C      ; CollisionCheckOnLand
0397: JR nc, $03B4    ; only allow movement if no collision

; After:
0394: CALL $0A1C      ; CollisionCheckOnLand (still runs, result ignored)
0397: JR $03B4        ; always allow movement
```

**Patch 2 — Alternate collision gate (0x03B1-0x03B3)**

NOP out the 3-byte `JP c, $0242` that blocks movement:

| Address | Original | Patched | Instruction |
|---------|----------|---------|-------------|
| 0x03B1  | 0xDA     | 0x00    | `JP c` -> `NOP` |
| 0x03B2  | 0x42     | 0x00    | (operand) -> `NOP` |
| 0x03B3  | 0x02     | 0x00    | (operand) -> `NOP` |

```
; Before:
03AE: CALL $0CCA      ; secondary collision check
03B1: JP c, $0242      ; block movement if collision

; After:
03AE: CALL $0CCA      ; secondary collision check (still runs, result ignored)
03B1: NOP
03B2: NOP
03B3: NOP
```

**Optional Patch 3 — SCF inside collision function (0x0D08)**

NOP out the `SCF` (set carry flag) so the collision function can never report a collision:

| Address | Original | Patched | Instruction |
|---------|----------|---------|-------------|
| 0x0D08  | 0x37     | 0x00    | `SCF` -> `NOP` |

This is redundant if patches 1 and 2 are applied, but provides defense in depth.

### MCP Tool Commands

```python
# Patch 1: Normal collision gate
patch_rom(address=919, value=24)    # 0x0397: JR nc -> JR

# Patch 2: Alternate collision gate (3 NOPs)
patch_rom(address=945, value=0)     # 0x03B1: JP c -> NOP
patch_rom(address=946, value=0)     # 0x03B2: operand -> NOP
patch_rom(address=947, value=0)     # 0x03B3: operand -> NOP

# Patch 3 (optional): SCF in collision function
patch_rom(address=3336, value=0)    # 0x0D08: SCF -> NOP
```

### Notes

- Patches modify the in-memory ROM buffer only; the ROM file on disk is not changed.
- Patches persist until the ROM is reloaded.
- Warps still work normally since warp detection is separate from collision blocking.
- Wild grass encounters still trigger since they use a different code path.
- Save states made after patching will restore the patched ROM state.
