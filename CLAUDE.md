# Walkie-Textie

ESP32-S3 + WIO-SX1262 LoRa firmware (Rust/Embassy). The PCB design lives in
`hardware-design/`.

## Flashing gotchas (espflash)

- `espflash.toml` names the silent-bootloader binary under
  `bootloader/build/`, which is GITIGNORED. On a fresh clone that path does
  not exist and espflash fails with a misleading "Error while connecting to
  device" (no missing-file error, and it happens after the chip info prints).
  Build the bootloader first, comment the override out, or run espflash from
  outside the repo directory (the config is read from the working directory).
- USB CDC frames must never end on a full 64-byte packet: bulk transfers
  only complete on a short packet, so `src/usb/cdc_io.rs` caps writes at 63
  bytes. A response whose COBS-encoded size landed exactly on the boundary
  sat undelivered in the host's CDC driver until unrelated bytes flushed it
  (found and hardware-verified on the LoRaMqttHub fork, which shares this
  file).

## LoRa bandwidth is 125 kHz, changed on 10 November 2026

`src/config.rs` used to set a 250 kHz LoRa bandwidth with SF11 as the default,
in a sub-band that is 250 kHz wide (869.4 to 869.65 MHz). EN 300 220-2 V3.3.1
wants the 99% occupied bandwidth, at the widest spreading factor the host can
select, inside the sub-band at every temperature. A model of the signal
(`hardware-design/v3/kicad/tools/lora_spectrum.py`, printed by `check_rf.py`
on every board build) gave 247 to 250 kHz at SF11 and 262 kHz at SF7, so the
radio was not going to pass.

It is now 125 kHz with SF10 as the default. SF10 at 125 kHz has the symbol
time and sensitivity of SF11 at 250 kHz and about nine tenths of its bit rate.
The model gives 124 to 133 kHz across SF7 to SF12, 58 kHz or more clear on
each side. The transmit timeout in `src/lora/driver.rs` now follows the
packet's time on air (`transmit_timeout_ms` in `src/lora/airtime.rs`), because
a 255-byte packet at SF12 in 125 kHz is on air for 14 seconds and the old
fixed wait was 10.

- The change was made without a board. Host tests and both ESP32-S3 builds
  pass. The hardware integration tests have not been run on it, and nothing
  about the occupied bandwidth has been measured.
- A radio built before the change cannot hear one built after. Flash every
  radio together.
- The hub fork (`~/RustroverProjects/walkie-textie-hub-firmware`) still has
  SF11 at 250 kHz and the fixed 10 second wait. It needs the same change
  before it can talk to these radios.
- The owner did not ask for this change by name. It follows the fallback
  written into `walkie-textie-flutter/docs/COMPLIANCE.md` (T1). To go back,
  restore `SPREADING_FACTOR` and `BANDWIDTH_KHZ` in `src/config.rs` and the
  defaults in the tests and in `integration_tests/src/protocol.rs`.

## Soil sensor board (`hardware-design/v3`)

The LoRa soil sensor is a second board that keeps this firmware's pin map for
the radio SPI and control lines, the LED and USB. It is not built yet: the
PCB_V3 drop of 6 September 2026 is under review
(`hardware-design/v3/PCB_V3/PCB_V3-design-review.pdf`). What differs for
firmware on PCB_V3:

- I2C to the Adafruit STEMMA soil sensor (address 0x36) is SDA GPIO2, SCL
  GPIO1. The brief suggested GPIO5/GPIO6; the designer moved them.
- A TPL5111 timer switches the whole 3.3 V rail, so every wake is a cold boot:
  read the sensor, transmit, then signal DONE on GPIO4 to cut power. PCB_V3
  wires DONE straight to GPIO4, so a low-to-high edge powers off. The review
  asks for the brief's MMBT3904 stage, which inverts it (drive GPIO4 high, then
  low). Check which one the built board has before writing the DONE code. With
  USB attached the rail stays on whatever DONE does, and the firmware has no
  way to tell USB from battery power.
- PCB_V3 fits a Vollgo SX1262S8S+T-X1, not the Wio-SX1262. It does not bring
  out DIO2 or DIO3, has an RXE pin on GPIO38 (not driven by this firmware and
  not pulled on PCB_V3), and its datasheet contradicts itself on TCXO versus
  crystal, so `configure_tcxo` and `configure_dio2_rf_switch` may be wrong for
  it. The review asks for the Wio module back.
- GPIO35-GPIO37 belong to the octal PSRAM on the N8R8 module. Never use them.

`hardware-design/v3/kicad/` holds our own KiCad version of that board with the
review applied (V3.1, made 10 November 2026, not built and not sent to the
designer). The owner means to use it as a general LoRa node for I2C sensors.
For firmware it differs from PCB_V3 like this:

- DONE goes through the MMBT3904 stage: drive GPIO4 high, then low, to cut
  power. TP2 is a test pad on GPIO4, ahead of the base resistor: touch it to
  3.3 V and let go to make the edge by hand while the firmware leaves GPIO4
  as an input.
- A TLV803S supervisor (U13) holds EN low while the 3.3 V rail is under 2.93 V
  and for about 200 ms after it recovers, so every boot starts 200 ms later
  than on the radio board. It only catches a rail that dips. Firmware for the
  soil sensor should still enable the brownout detector and a watchdog.
- The LoRa module is the Wio-SX1262, wired as on the radio board, so
  `configure_tcxo` and `configure_dio2_rf_switch` apply unchanged.
- The module's RF_SW pin is on GPIO38 with a 10 kohm pull-up, and this
  firmware never drives GPIO38. High enables the module's receive path.
  Seeed's datasheet for the module has the pin low while transmitting and
  asleep, so on this board it is high where Seeed has it low, and on the
  Seeed kit it floats. Whether that costs transmit power has to be measured
  on the first board (`hardware-design/v3/kicad/README.md`). Driving
  GPIO38 high to receive and low otherwise would settle it on both boards.
- I2C stays on SDA GPIO2 and SCL GPIO1, each through 100 ohms to the
  connector, and the pin map for SPI, the LED and USB is unchanged.
  `hardware-design/v3/kicad/tools/check_firmware.py` reads the pins from
  `src/main.rs` and fails the board build if one stops reaching its part, so
  a pin change here needs the board data changed with it.
- The radio firmware never signals DONE, so on batteries the timer would cut
  its power for 50 ms every 15 minutes. R37, a 0 ohm link marked ALWAYS ON,
  holds the rail up for that use. JLCPCB fits it in the default order
  (`fab/BOM.csv`) and leaves it out in the `timed` order, which is the one
  for firmware that signals DONE. With USB attached the rail stays up anyway.
- Plugging USB in or pulling it out while the board runs from its battery
  leaves the converter without a supply for some microseconds, on the
  capacitors at its input. On a nearly flat battery with a radio
  transmitting that can reset the ESP32 (a model's worst case, not a
  measurement), so firmware must not assume it keeps running through a
  change of supply.

## The first radio board is archived

The sections from here on were written for the first radio board (MESHTASTIC
NODE) and its scripted KiCad rebuild. On 10 November 2026 its files moved to
`hardware-design/archive/`, and its scripts have not been run since. Where the
text below says `tools/`, `kicad/` or `Production Files/` without a full path,
read `hardware-design/archive/tools/`,
`hardware-design/archive/v1-production/kicad/` and
`hardware-design/archive/v1-production/Production Files/`. The scripts still
expect the old places. The board being worked on is `hardware-design/v3/kicad`
(above, and `hardware-design/CLAUDE.md`). The notes on installing and driving
KiCad apply to both.

## Hardware diagrams

`hardware-design/archive/diagrams/` holds generated views of the v1 board:

- `component-placement.png` - every part drawn to scale at its real X/Y from the
  pick-and-place file. Generated by `hardware-design/archive/tools/placement_diagram.py`
  (matplotlib). Mermaid cannot represent physical placement, so this view stays a
  rendered PNG.
- `block-diagram.mmd` / `.png` - functional blocks and how they connect (Mermaid).
- `component-overview.mmd` / `.png` - all parts grouped by subsystem (Mermaid).

The `.mmd` files are the source of truth for the last two and render natively on
GitHub; `hardware-design/archive/diagrams/README.md` displays all three.

When the hardware design changes (updated Gerbers, BOM, pick-and-place, or a new
board revision), regenerate the diagrams so they stay in sync:

```bash
# spatial placement (matplotlib)
python3 hardware-design/archive/tools/placement_diagram.py

# mermaid diagrams -> PNG (needs: npm install -g @mermaid-js/mermaid-cli)
cd hardware-design/archive/diagrams
mmdc -i block-diagram.mmd -o block-diagram.png -p ../tools/puppeteer-config.json -b white -s 2
mmdc -i component-overview.mmd -o component-overview.png -p ../tools/puppeteer-config.json -b white -s 2
```

The block-diagram nets and the component-overview passive groupings are inferred
from the BOM, not extracted from a schematic - review them when components change.

IMPORTANT: after regenerating, open each rendered image and check it thoroughly
for readability before considering the update done - no overlapping or clipped
boxes, no truncated or unreadable labels, arrows/edges legible and not tangled,
colours still distinguishable, and the content still correct. Fix the `.mmd` or
the script and re-render until it reads cleanly.

## Component datasheets

`hardware-design/datasheets/` holds datasheets for the main components and a
`SUMMARY.md` of the key specs. Keep both in sync when parts change.

## Working on the KiCad hardware design

KiCad 9 or newer is required (`kicad-cli`, GUI editors, bundled ngspice); KiCad 7
is too old - it cannot open v9 files or run the CLI checks. This machine runs the
KiCad 10 AppImage from `~/.local/bin`, with `kicad-cli` and `kicad` wrapper
scripts there that dispatch into it, so `kicad-cli ...` works directly on PATH.
See `hardware-design/archive/README.md` for tool setup.

Since 9 November 2026 the machine also has KiCad 10.0.8 from the KiCad PPA
under `/usr/bin`, with its symbol and footprint libraries in
`/usr/share/kicad`. That install is the one whose `pcbnew` Python module
`/usr/bin/python3` can import, which scripts that edit boards need (the
soil-sensor tools in `hardware-design/v3/kicad/tools` use it). A KiCad MCP
server is registered with Claude Code as `kicad` (launcher
`~/.local/bin/kicad-mcp`); it edits board and schematic files through the same
module, with no KiCad window open.

An editable KiCad project of the first radio board exists at
`hardware-design/archive/v1-production/kicad/MESHTASTIC_NODE/`, rebuilt from datasheet reference
circuits, the Seeed Wio-SX1262 KiCad files and the firmware pin map using the
programmatic workflow below (never a Gerber import - that is netless copper, not a
real design). Current state:

- The schematic (`MESHTASTIC_NODE.kicad_sch`) is fully captured and ERC-clean
  (0 violations); `tools/verify_nets.py` confirms every firmware net is present.
- The board (`MESHTASTIC_NODE.kicad_pcb`) is **4-layer** (F.Cu / In1.Cu / In2.Cu /
  B.Cu, matching the as-built board), fully placed, **routed and poured**:
  freerouting routes the signals, `tools/finish_route.py` closes the last few, and
  `tools/pour.py` floods the ground/power planes plus a stitching-via field
  (including a paddle via field that grounds the ESP32 exposed pad). DRC is clean
  (0 errors, 0 warnings, 0 unconnected, parity-clean).
- The original 4-layer manufacturing outputs still live under
  `hardware-design/archive/v1-production/Production Files/` and are the as-built reference.

The full pipeline was one command - `python3 hardware-design/archive/tools/build_all.py` -
which regenerates the schematic, the board, the route, the pour and the fab
package (`kicad/fab/`, with `gerbers.zip` + `BOM.csv` + `CPL.csv` for PCBWay) and
gates each stage on ERC / placement / DRC. Edit `tools/build_schematic.py` (nets)
or `tools/placement.py` (part positions) and re-run it. The RF/antenna path is
resolved: AE1 (board U.FL) is the ESP32 2.4 GHz Bluetooth antenna via the
L2/C15/L1 match, and LoRa uses the Wio module's own onboard IPEX. The Production
Files remain the zero-effort route if you just want the original board made again.

How to use the tools when working on the design:

- The `.kicad_sch` / `.kicad_pcb` files are plain-text S-expressions. Make small,
  targeted edits and keep everything in git so a bad edit is one `git checkout`
  away. For structural changes prefer a parser (`kiutils`) over freehand edits to
  avoid breaking net back-references.
- Validate after every edit. This doubles as a corruption check, since a broken
  file fails to load:

  ```bash
  kicad-cli sch erc --format json --exit-code-violations -o /tmp/erc.json design.kicad_sch
  kicad-cli pcb drc --format json --schematic-parity --exit-code-violations -o /tmp/drc.json design.kicad_pcb
  ```

  A non-zero exit or a load failure means revert and make a smaller edit.
- Render to review without the GUI - export SVG, then rasterise to PNG so the
  image can be opened and visually checked:

  ```bash
  kicad-cli pcb export svg --output /tmp/pcb.svg design.kicad_pcb
  kicad-cli sch export svg --output /tmp/ design.kicad_sch
  uvx cairosvg /tmp/pcb.svg -o /tmp/pcb.png -s 2
  ```

  For a photorealistic 3D check use `kicad-cli pcb render` (needs Xvfb headless).
- Simulate only specific analog sub-circuits (LDO, RF matching) with the ngspice
  that ships in KiCad; the MCU has no SPICE model. DRC/ERC are the main electrical
  pre-fab gates.
- To eyeball the existing Gerbers without any source, render with gerbonara (see
  README) - a visual/manufacturing check only, not an electrical one.
- Other useful outputs: `kicad-cli sch export bom`, `sch export netlist`,
  `pcb export gerbers` / `drill` / `pos` / `step`.

After any layout or BOM change, regenerate the diagrams and run the readability
check above.

## PCB design best practices (apply during any review or redesign)

Use this as the review checklist. It is tailored to this board (4-layer ESP32-S3
+ Wio-SX1262 LoRa, USB-C, LDO, 40 MHz crystal, U.FL). Each rule has its reason.
The editable board is 4-layer (F.Cu / In1.Cu GND / In2.Cu +3V3 / B.Cu), matching
the as-built board, so the inner planes give it a proper ground reference.

Stackup and ground (4-layer)
- Signals route on F.Cu and B.Cu; In1.Cu is a ground plane and In2.Cu a +3V3
  plane (both also flooded with ground fill in the gaps). Keep the ground plane
  unbroken under the USB pair, the RF trace and the crystal - return current must
  flow directly beneath the signal on the adjacent plane.
- The autorouter spills some signals onto the inner layers on this dense board, so
  `tools/pour.py` re-floods ground in the gaps and stitches all four layers with a
  dense via field; exposed pads (the ESP32 paddle) get their own via field into
  the planes (`finish_route`/`pour` handle this automatically).
- Stitch the ground layers with vias densely around the RF section, the antenna
  and the whole board edge to contain fields and tie the planes together.
- Controlled impedance (USB 90 ohm differential, RF 50 ohm) depends on trace
  geometry over the real board thickness - compute widths against the chosen
  2-layer stackup rather than assuming a thin 4-layer prepreg.

Power and decoupling
- One bypass cap (100 nF) per power pin, placed right at the pin with its plane
  via as close as possible; a small pin->cap->via loop is what makes decoupling
  work. Map the nine 100 nF parts to specific supply pins.
- Provide bulk capacitance (10 uF / 2.2 uF) at the LDO output and near the MCU and
  radio for current transients (LoRa TX and Wi-Fi bursts draw sudden current).
- Size power pours/tracks for peak current, not average; avoid thin necks. The LDO
  is 1 A but TX + RF spikes are higher instantaneously.

RF and antenna (SX1262 + U.FL)
- Route the RF trace as a short, straight 50 ohm controlled-impedance line over an
  unbroken bottom ground pour, with nothing crossing underneath.
- Flood ground around the RF trace (coplanar), via-fence both sides, and keep a
  ground keepout/clearance around the antenna and U.FL. Place the U.FL at the
  board edge; route no signals under the RF/antenna area.
- The Wio module already integrates matching, a TCXO and a DC-DC and has its own
  IPEX - resolve whether the board's AE1 / L1 / L2 / C15 path is actually used and
  remove any stub RF path (settle this once the schematic exists).

USB 2.0
- Route D+/D- as a 90 ohm differential pair, length-matched, short and direct,
  over continuous ground, with no stubs.
- Place the USBLC6 ESD device right at the USB-C connector, upstream of the MCU, so
  it clamps before the data lines fan out.

Crystal (40 MHz)
- Keep the crystal and its two load caps at the MCU oscillator pins with short,
  symmetric traces; guard the area with ground and route nothing under it (clocks
  are both sensitive and noisy).

ESP32-S3 specifics
- Honour the strapping pins (IO0/BOOT, IO45, IO46, IO3): correct pulls and no
  conflicting loads, or the part will not boot. Verify what SW1/SW2 are tied to
  (likely BOOT and EN/RESET) and that EN has its RC.
- Decouple each VDD/VDD3P3 pin and keep the SPI flash (U4) traces short. Keep
  digital/LDO/clock noise away from the RF section.

Thermal
- Put thermal vias under the LDO and under the MCU QFN exposed pad into the bottom
  ground pour; the exposed pad is the main ground and heat path.

DFM / manufacturability
- Encode the fab's minimum clearance / track / annular-ring rules as KiCad net
  classes and design rules, then let DRC enforce them. The project already sets
  min clearance 0.13 mm and min track width 0.1565 mm, with Default / Power / RF
  net classes (RF: 0.3 mm track, 0.25 mm clearance); assign nets to those classes
  during layout.
- Use symmetric pads and equal thermal relief on 0603 parts to avoid tombstoning
  during reflow; keep parts off the board edge and respect courtyards.
- No silkscreen over pads; designators readable and not hidden under parts.

Assembly aids and EMC
- Pin-1 / polarity markers on all polarised parts; add fiducials and mounting
  holes with keepout.
- Minimise current-loop areas to lower radiated emissions; keep ESD/TVS paths to
  ground short and direct.

Always run `kicad-cli pcb drc --schematic-parity` and `kicad-cli sch erc` before
calling a change done, and fix violations rather than waiving them.

References to consult: Espressif ESP32-S3 Hardware Design Guidelines
(https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/),
Semtech SX1262 reference design AN1200.40
(https://cdn-reichelt.de/documents/datenblatt/A200/SX1262REFERENCE.pdf),
Seeed Wio-SX1262 wiki (https://wiki.seeedstudio.com/wio_sx1262/), and the
IPC-2221 (generic design) / IPC-7351 (land patterns) standards.

## Generating a schematic programmatically (proven workflow)

This is the tested process behind
`hardware-design/archive/v1-production/kicad/MESHTASTIC_NODE`. The
generator is `hardware-design/archive/tools/build_schematic.py` and verification is
`tools/verify_nets.py`. Connectivity is expressed by placing a global label on
every pin (no drawn wires) - ERC treats same-named labels as one net.

Prerequisites: KiCad 9+ (`kicad-cli`), `kiutils` (`pip install kiutils`), and the
symbol libraries under `hardware-design/archive/v1-production/kicad/libs/`.

### 1. Source the symbols (format matters)

kiutils reads the monolithic `.kicad_sym` format. KiCad 10 ships a new SHARDED
format (`Lib.kicad_symdir/Symbol.kicad_sym`) that kiutils cannot parse, so vendor
the KiCad 8 libraries - kicad-cli 10 still reads 8-format symbols:

```bash
git clone --depth 1 --branch 8.0.2 \
  https://gitlab.com/kicad/libraries/kicad-symbols.git kicad/libs/kicad-symbols
```

Plus the Espressif library (ESP32-S3) and any vendor parts. Most footprint names
in the BOM are already standard KiCad libraries. When a stock symbol is missing
(adjustable TLV75901, the Wio module) borrow a donor symbol with the right pin
count and relabel it.

### 2. Build the schematic (kiutils)

Per component: embed its symbol once in `libSymbols`, add a `SchematicSymbol`
instance, then for every pin add a `GlobalLabel` at the pin's connection point;
unused pins get a `NoConnect`. For an unrotated instance at (X, Y) the pin
connection point is:

    abs = (X + pin.position.X,  Y - pin.position.Y)

(symbol Y is up, schematic Y is down - hence the minus). Each power rail needs
exactly one driver: a regulator output pin typed `power_out` drives its rail;
rails with no such pin (here +5V and GND) get a `PWR_FLAG`.

### 3. Gotchas (each cost a debug cycle here)

- `Schematic.create_new()` leaves `uuid` empty; set `sch.uuid = str(uuid.uuid4())`
  or the file fails to load.
- Renaming a symbol's `entryName` REQUIRES renaming its unit sub-symbols too, or
  the schematic silently "fails to load":

  ```python
  sym.entryName = "TLV75901"
  for u in sym.units:
      u.entryName = "TLV75901"
  ```

- Pin ELECTRICAL TYPES must match the real part, not the donor. Relabelling a
  pin's NAME is not enough - a borrowed LDO whose pin 2 was `power_in` (GND) but
  is now FB triggers `power_pin_not_driven`. Set the type:

  ```python
  types = {"1": "power_out", "2": "passive", "3": "power_in",
           "4": "input", "6": "power_in"}     # OUT/FB/GND/EN/_/IN
  pin.electricalType = types[pin.number]
  ```

- One power driver per net. Two `power_out` pins on a rail give
  `pin_to_pin: Power output and Power output are connected`. The ESP32-S3
  `VDD_SPI` pin is a `power_out`; it is left No-Connect here so it does not clash
  with the LDO output on +3V3.
- Place instances on a 2.54 mm grid so pins land on grid (off-grid pins warn and
  may not connect in the GUI).

### 4. Verify everything

```bash
python3 hardware-design/archive/tools/build_schematic.py  # regenerate

# ERC must load and report 0 errors
kicad-cli sch erc --severity-error --exit-code-violations \
  -o /tmp/erc.rpt kicad/MESHTASTIC_NODE/MESHTASTIC_NODE.kicad_sch

python3 hardware-design/archive/tools/verify_nets.py      # nets vs firmware pin map

# fab / review outputs
kicad-cli sch export netlist -o /tmp/node.net kicad/MESHTASTIC_NODE/MESHTASTIC_NODE.kicad_sch
kicad-cli sch export bom --group-by Value -o /tmp/bom.csv kicad/MESHTASTIC_NODE/MESHTASTIC_NODE.kicad_sch

# eyeball it
kicad-cli sch export svg --output /tmp/ kicad/MESHTASTIC_NODE/MESHTASTIC_NODE.kicad_sch
uvx cairosvg /tmp/MESHTASTIC_NODE.svg -o /tmp/sch.png -s 2
```

A clean run is: ERC `0 errors`, `verify_nets.py` prints "all firmware nets
present", and the BOM groups match `Production Files/BOM`. `verify_nets.py` only
checks the firmware-confirmed nets; the inferred nets (power, strapping, RF -
marked `# INFER` in the generator) still need review against the copper before
fabrication.

## Generating the board programmatically (proven workflow)

Two scripts, run in order after the schematic is ERC-clean:

- `tools/board_setup.py` - creates the **4-layer** board (F.Cu / In1.Cu / In2.Cu /
  B.Cu; the inner layers are `signal`-typed because this board is too dense to
  route on two signal layers, so the autorouter is allowed to use all four and
  `tools/pour.py` floods the leftover inner-layer area with ground), its layer
  stack and the Edge.Cuts outline (30 x 40 mm, 3 mm rounded corners; the USB-C
  edge is straight - the substitute SMD connector needs no notch).
- `tools/build_board.py` - exports the schematic netlist, then for each component
  loads its footprint, places it at the manufactured X/Y/rotation from the CPL
  (with overrides from `tools/placement.py`), bakes the rotation into each pad,
  moves designators to the fab layer, and assigns every pad's net. Result: a
  placed, net-correct board. Footprints come from `kicad/libs/kicad-footprints`
  (the Wio module footprint lives in `kicad/libs/wio.pretty`).

```bash
# footprints must be the SAME 8.0.x tag as the symbols (kiutils can't read the
# KiCad 10 sharded format; kicad-cli 10 reads 8-format footprints fine)
git clone --depth 1 --branch 8.0.2 --filter=blob:none --sparse \
  https://gitlab.com/kicad/libraries/kicad-footprints.git kicad/libs/kicad-footprints
# then: git -C ... sparse-checkout set Resistor_SMD.pretty Capacitor_SMD.pretty ...

python3 tools/board_setup.py     # 4-layer board + outline
python3 tools/build_board.py     # place footprints + assign nets
kicad-cli pcb drc --schematic-parity --severity-error \
  -o /tmp/drc.rpt kicad/MESHTASTIC_NODE/MESHTASTIC_NODE.kicad_pcb
```

### Gotchas (each cost a debug cycle here)

- Re-loading the same `.kicad_mod` for many parts duplicates UUIDs - regenerate
  `footprint.tstamp` and every `pad.tstamp` per placement, or the board breaks.
- Picking a footprint out of a reference board can land it on `B.Cu`; select the
  right one (by `entryName`, not pad count) and check its layer.
- Nets: build a `{name: code}` map, set `pad.net = Net(code, name)`, and put every
  `Net` in `board.nets` (plus `Net(0, "")`).
- The netlist uses the indented `(comp` / `(net` form - split on `\(comp\b` /
  `\(net\b`, not `"(comp "`.
- **Substitute footprints differ in size from the originals** (the swapped USB-C,
  the module), so at the original CPL positions they overlap neighbours. Schematic
  parity is still 0 and nets are correct; the overlaps are placement cleanup -
  nudge the affected parts apart in pcbnew before routing.

### Routing and fab outputs (automated)

KiCad has no built-in autorouter, so `tools/route.py` drives one end to end:
export a Specctra DSN with the bundled `pcbnew` (kicad-cli cannot do Specctra),
autoroute the signals with **freerouting 2.2.4** headless, import the SES back,
close the few stragglers freerouting leaves (`tools/finish_route.py` - tries a
straight then L-shaped run on each layer), then pour the GND/+3V3 planes and the
stitching-via field (`tools/pour.py`). `pour.py` also drops a via field into any
exposed ground pad so the ESP32 paddle is grounded.

```bash
python3 tools/route.py            # DSN -> freerouting -> SES -> finish -> pour
python3 tools/fab_outputs.py      # Gerbers (+drill), CPL, BOM, netlist -> kicad/fab/
```

Or run the whole thing (schematic -> board -> route -> fab, gated at each stage):

```bash
python3 tools/build_all.py
```

DRC parity must stay 0 and `unconnected_items` reach 0; the pipeline asserts both.
The RF/antenna path is settled: AE1 (board U.FL) is the ESP32 2.4 GHz Bluetooth
antenna via the L2/C15/L1 match; LoRa uses the Wio module's onboard IPEX. The
USB D+/D- pair is short and direct but is not yet impedance-tuned - review it (and
the RF line) before a production run if controlled impedance matters.
