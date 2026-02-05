# Examples

Practical examples of using the SameBoy MCP Server with Claude.

## Basic Usage

### Loading and Running a Game

```
User: Load Super Mario Land and run it for a few seconds

Claude: I'll load the ROM and run it.

[Uses load_rom tool with path]
[Uses run_frames tool with count=300 (5 seconds at 60fps)]
[Uses capture_screen tool]

The game is now running. I can see Mario on the title screen.
```

### Taking a Screenshot

```
User: Show me what's on screen

Claude: [Uses capture_screen tool]

Here's the current screen. I can see [describes what's visible].
```

### Reading Game Memory

```
User: What's in the first 16 bytes of work RAM?

Claude: [Uses read_memory tool with address=0xC000, length=16]

The first 16 bytes of work RAM (0xC000-0xC00F) contain:
00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
```

## Game Analysis

### Finding the Player's Health

```
User: Help me find where Pokemon Yellow stores the player's HP

Claude: I'll use memory monitoring to find HP. First, let me take a snapshot,
then we'll do something that changes HP and compare.

[Uses take_memory_snapshot tool]

Now enter a battle and take some damage, then tell me.

User: Done, I took damage

Claude: [Uses compare_memory_snapshot tool]

I found several memory locations that changed. The ones that decreased by
a small amount are likely HP candidates:
- 0xD16C: changed from 45 to 38 (decreased by 7)
- 0xD16D: probably the high byte

Let me verify by reading that address:
[Uses read_memory tool with address=0xD16C, length=2]

The value at 0xD16C-0xD16D is 0x0026 (38 in decimal), which matches your
current HP. This is likely the player's first Pokemon's current HP.
```

### Monitoring a Variable

```
User: Watch that HP address and tell me when it changes

Claude: [Uses monitor_memory tool with addresses=[0xD16C, 0xD16D]]

I'm now monitoring addresses 0xD16C-0xD16D. Play the game and I'll
track any changes.

[After some gameplay]
[Uses get_memory_changes tool]

HP changed at frame 15234:
- 0xD16C: 0x26 → 0x1E (38 → 30, took 8 damage)

And again at frame 15890:
- 0xD16C: 0x1E → 0x2D (30 → 45, healed!)
```

## Debugging

### Setting Breakpoints

```
User: Set a breakpoint at the start of the game loop

Claude: Based on my analysis, the main game loop likely starts around 0x0150.
[Uses set_breakpoint tool with address=0x0150]

Breakpoint set at 0x0150. Now when I run the game, it will pause when
execution reaches this address.

[Uses resume tool]
[Uses step_frame tool repeatedly until breakpoint_hit=true]

The breakpoint was hit. Let me show you the current state:
[Uses get_registers tool]

PC is at 0x0150, registers are: A=0x01, BC=0x0013, ...
```

### Tracing Execution

```
User: Show me what instructions run during one frame

Claude: [Uses enable_trace tool with enabled=true]
[Uses step_frame tool]
[Uses get_trace tool with count=50]

Here are the last 50 instructions executed this frame:

0x0150: NOP
0x0151: LD A, (HL)
0x0152: INC HL
0x0153: CP $FF
0x0154: JR NZ, $0151
...

I can see a loop reading memory until it hits 0xFF.
```

### Disassembling Code

```
User: Disassemble the code at the current PC

Claude: [Uses get_registers tool to get PC]
[Uses disassemble tool with address=current_pc, count=20]

Disassembly at 0x0150:
```asm
0x0150: NOP
0x0151: LD A, (HL)      ; Load byte from HL into A
0x0152: INC HL          ; Move to next byte
0x0153: CP $FF          ; Compare A with 0xFF
0x0154: JR NZ, $0151    ; Loop if not 0xFF
0x0156: RET             ; Return from subroutine
```

This looks like a string copy routine that reads until a 0xFF terminator.
```

## Save States

### Creating Checkpoints

```
User: Save the game state before I try this boss fight

Claude: [Uses save_state tool with name="before_boss"]

Saved state "before_boss" at frame 45678 (state_id: a1b2c3d4).
You can now attempt the boss fight. If you want to retry, I can restore
this state.

User: I died, restore the save

Claude: [Uses load_state tool with state_id="a1b2c3d4"]

Restored to frame 45678, right before the boss fight. Try again!
```

### Exploring Different Paths

```
User: I want to explore both paths in this dungeon

Claude: [Uses save_state tool with name="fork_in_road"]

Saved at the fork. Let's go left first.
[Uses press_key tool with key="left"]
[Explores left path...]

Now let me restore and try right:
[Uses load_state tool]
[Uses press_key tool with key="right"]
[Explores right path...]

The left path has a treasure chest, the right path leads to the exit.
```

## Input Automation

### Navigating Menus

```
User: Select the second option in the menu

Claude: [Uses press_key tool with key="down", frames=10]
[Uses press_key tool with key="a", frames=5]

Selected the second option.
```

### Complex Input Sequences

```
User: Do the Konami code

Claude: [Uses press_keys sequence]
up, up, down, down, left, right, left, right, b, a

[Uses press_key for each in sequence with appropriate timing]

Entered the Konami code!
```

### Holding Buttons

```
User: Hold right and A to run and jump

Claude: [Uses press_keys tool with keys=["right", "a"], frames=30]

Held right+A for 30 frames (half a second).
```

## Advanced Analysis

### Finding All Instances of a Value

```
User: Find all memory locations containing the value 99

Claude: [Uses find_value tool with value=99, region="ram"]

Found 5 locations containing value 99:
- 0xC100
- 0xC234
- 0xC567
- 0xD100
- 0xD234

These could be lives, score digits, or other game values.
```

### Tracking Score Changes

```
User: Help me find the score in Tetris

Claude: I'll watch for changes as you score points.

[Uses take_memory_snapshot]

Now clear a line.

User: Done

[Uses compare_memory_snapshot]

Several locations changed. Let me analyze:
- 0xC0A0-0xC0A2: Increased significantly (likely score in BCD)

Let me read those bytes:
[Uses read_memory with address=0xC0A0, length=3]

Value: 0x00 0x01 0x00 = Score of 100 in BCD format!

Your score is stored at 0xC0A0-0xC0A2 in Binary Coded Decimal.
Each byte represents two decimal digits.
```

### Analyzing Sprite Positions

```
User: Where is Mario on screen?

Claude: [Uses get_sprites tool]

Found 4 sprites on screen. The main character sprite is likely:
- Sprite 0: X=80, Y=120, Tile=0x42

Mario is at pixel position (80, 120), which is roughly center-left
of the screen. The tile ID 0x42 suggests this is a walking frame.

[Uses capture_screen for visual confirmation]

Confirmed - Mario is standing in the middle of the platform.
```

## Vision Analysis

### Describing the Screen

```
User: What's happening in the game?

Claude: [Uses capture_screen tool]

Looking at the screen, I can see:
- This is the title screen of Pokemon Yellow
- Pikachu is displayed in the center
- "PRESS START" text is blinking at the bottom
- The Nintendo copyright notice is visible

The game is waiting for input to start.
```

### Reading In-Game Text

```
User: What does the dialog box say?

Claude: [Uses capture_screen tool]

The dialog box shows:
"PROF. OAK: Hello there!
Welcome to the world
of POKEMON!"

This is the introduction sequence where Professor Oak explains
the game world.
```

## Tips and Best Practices

1. **Use save states liberally** - They're fast and let you explore without risk

2. **Combine tools** - Take a screenshot after each significant action

3. **Monitor known addresses** - Once you find a variable, monitor it for insights

4. **Use step_frame for precision** - When timing matters, step frame by frame

5. **Check registers after breakpoints** - They often contain important context

6. **Compare snapshots before/after** - Easiest way to find game variables

7. **Read memory in context** - Nearby bytes often relate to each other
