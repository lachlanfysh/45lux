<!--
Migrated from CLAUDE.md for Codex on 2026-06-13.
Treat legacy references to Claude as prior-agent workflow notes unless they
specifically mention Claude CLI/auth. Keep this file in sync with CLAUDE.md
while both agent stacks are in use.
-->

# 45lux

## Setup
pip install -e ~/Projects/skidl

## Circuit Design
Use SKiDL (Python circuit-as-code). See ~/Projects/skidl for source.

## Full Pipeline: Schematic → Layout → PCB

After building a circuit, generate BOTH schematic and PCB layout. Don't stop at `generate_schematic()`.

```python
from skidl import *

# 1. Build circuit with @subcircuit for hierarchy
@subcircuit
def my_block(vcc, gnd, sig):
    u = Part("Device", "R", value="10k", footprint="Resistor_SMD:R_0805_2012Metric")
    c = Part("Device", "C", value="100nF", footprint="Capacitor_SMD:C_0805_2012Metric")
    u[1] += sig
    u[2] += vcc
    c[1] += vcc  # decap: 100nF between VCC and GND
    c[2] += gnd

with Circuit() as ckt:
    vcc, gnd, sig = Net("VCC"), Net("GND"), Net("SIG")
    my_block(vcc, gnd, sig)

# 2. Generate schematic
ckt.generate_schematic(auto_stub=True)

# 3. Generate PCB layout
from skidl.layout import (
    extract_groups, place_parts, write_kicad_pcb, validate,
    LayoutConstraints, BoardOutline, derive_outline,
    load_footprint_bboxes,
)

groups = extract_groups(ckt)
fp_names = {getattr(p, "foot", "") for p in ckt.parts if getattr(p, "foot", "")}
fp_bboxes = load_footprint_bboxes(fp_names, [])  # uses KICAD9_FOOTPRINT_DIR env

constraints = LayoutConstraints(
    fixed=[],  # or FixedPosition("U1", 50.0, 50.0) for human-placed parts
    zones=[],
    keepouts=[],
    outline=BoardOutline(100.0, 80.0),  # optional — derived if omitted
)

placed = place_parts(groups, constraints, fp_bboxes)
outline = constraints.outline or derive_outline(placed, fp_bboxes)

result = validate(placed, ckt, fp_bboxes, outline=outline)
print(result.summary())  # LOUDLY flags overlaps

write_kicad_pcb(placed, ckt, fp_lib_dirs=[], output_path="board.kicad_pcb",
                outline=outline)
```

## Conventions the Layout Engine Relies On

- **Decoupling caps**: value must match `100nF` or `0.1uF` (regex `^(100n|0\.1u)`), with pins on a VCC-like net AND a GND-like net. These get auto-placed 1.5mm from their parent IC.
- **Grid layout**: subcircuits with ≥20 parts trigger automatic grid placement. Structure large sensor arrays as a single subcircuit to get grid layout, not split across multiple small ones.
- **Power nets**: names matching VCC/VDD/VBUS/+3.3V etc are recognised as power; GND/VSS/AGND etc as ground.
- **Hierarchy**: use `@subcircuit` to group related parts. The layout engine places parts within the same subcircuit near each other.

## Human-in-the-Loop Workflow

For real boards, the typical flow is:
1. Generate initial PCB with layout engine
2. Open in KiCad, manually place ICs/connectors/switches
3. Re-read positions: `read_placed_positions("board.kicad_pcb")`
4. Feed as `FixedPosition` constraints, re-run placer for passives
5. Validate, adjust, repeat
