# Hardware design working notes

Orientation for anyone (human or agent) picking up the boards. This file
covers what each directory actually is, which decisions are settled and why,
and the mistakes that have already been made here so they are not repeated.
`archive/README.md` covers the scripted v1 pipeline and tool installation.

For the radio board, the authoritative records live in the app repo, not here:
`walkie-textie-flutter/docs/PCB_DESIGN_NOTES.md` (decisions and findings),
`PCB_CORRESPONDENCE.md` (verbatim thread with the designer) and
`COMPLIANCE.md` (CE self-certification plan). Update those in the same change
as any work here. The soil sensor has a different designer; its log of what
was sent and received is `v3/PCB_CORRESPONDENCE.md`.

## What is where

| Path | What it is |
| --- | --- |
| `v3/` | LoRa soil-sensor hardware: the handover brief, the designer's drops (`PCB_V3/` is current, older ones in `old/`), our review next to each drop, and `PCB_CORRESPONDENCE.md`, the log of what was sent and received. A from-scratch design, separate from the earlier radio boards. `kicad/` is our own KiCad version of PCB_V3 with the review applied (V3.1), described below. This is the board being worked on |
| `datasheets/` | Datasheets for the radio board's main parts, with a `SUMMARY.md` |
| `archive/v1-production/` | The original as-built 4-layer radio board. `Production Files/` are the fab outputs, `kicad/` is the scripted rebuild |
| `archive/v2-production/` | Exactly what the external designer delivered for rev 2. Treat as read-only evidence |
| `archive/v2-jlcpcb/` | The rev 2 order package, restructured for JLCPCB |
| `archive/v1-soil-sensor/` | A KiCad project named `PCB_Updated`, last changed on 23 August 2026, two days before the soil-sensor brief. v3 does not use it |
| `archive/tools/` | The v1 scripted schematic-to-production pipeline. Does not apply to rev 2, which is hand-laid by the designer |
| `archive/diagrams/` | Generated views of the v1 board |

The v1 and v2 material was moved under `archive/` on 10 November 2026, when
the owner asked for the old designs to be archived. The v1 scripts and
`archive/README.md` still name `tools/`, `kicad/` and `Production Files/` as
they were before the move, and the pipeline has not been run since. The
vendored KiCad libraries it needs (`archive/v1-production/kicad/libs/`) are
not in git.

The KiCad project and manufacturing package for the current board also exist
outside this repo in `~/RustroverProjects/walkie-textie-hardware/`.

## Soil-sensor v3: decisions that are settled

The handover brief of 25 August 2026 (`v3/`) is the specification, with these
changes accepted by the owner on 11 September 2026. The review of the PCB_V3
drop that records them is `v3/PCB_V3/PCB_V3-design-review.pdf`, sent to the
designer on 11 September 2026.

- **868 MHz antenna: the Pulse W3000 chip antenna**, not the TI DN038 printed
  antenna. It still needs a pi-network footprint, the VNA test structure below
  and a feed line over ground. Its datasheet match (39 nH series, 6.8 nH shunt)
  is for Pulse's 20 x 40 mm reference board, so it must be tuned on this board.
- **USB-C plug, not the HRO socket.** See the USB-C section below.
- **USB-C shell to GND through 1 Mohm and 1 nF** (the designer's circuit), not
  straight to GND, provided it works. C25 is a 50 V 0402 part, and it does not
  survive ESD on the shell: the discharge network's 150 pF shares its charge
  with C25, so 4 kV by contact puts 520 V on 1 nF and 8 kV puts 1040 V. This
  was worked out on 10 November 2026 and has not been sent to the designer.
  The KiCad V3.1 board keeps his circuit with C25 at 100 nF, which sees 6 V at
  4 kV and 22 V at 15 kV. On any drop, check the shell capacitor's value
  against its voltage rating this way.
- **Deliverables: what this designer supplies is enough for now** (EasyEDA
  files, Gerbers, BOM, pick-and-place, OBJ). The owner orders and fabricates
  the boards, so the designer gets no factory or ordering instructions. The
  brief's full list (KiCad project, zero ERC/DRC with parity, fabrication notes,
  STEP) still applies to future boards designed by other people.
- **Designators: the designer's PCB_V3 numbering is the reference**, not the
  brief's. He only renames parts with the wrong letter (U2 to C2, U6 to R14, U7
  and U9 to D4 and D5, U3 to J2, U8 to J1, L1 to ANT1), and new parts take the
  next free numbers. The brief's acceptance tests and the VNA test use the
  brief's designators, so map them first:

  | Brief | PCB_V3 | Part |
  | --- | --- | --- |
  | U2 | U5 | TPS631000 buck-boost |
  | U4 | U10 | TPL5111 timer |
  | U5 | U11 | LoRa module (Wio pad 8 VCC is pad 13 on the Vollgo) |
  | U6 | U1 | ESP32-S3-WROOM-1 |
  | U7 | U4 | TPS2116 power mux |
  | J1, J2, J3 | U8, U3, CN1 | USB-C plug, sensor connector, battery connector |
  | R10, R11 | R18, R19 | I2C pull-ups |
  | R13 | R20 | timer resistor |
  | L1 | L2 | 1 uH inductor |

  So the brief's droop test at "U2 VIN, U5 pad 8, U6 pad 2" is U5 VIN, U11
  pad 13 and U1 pad 2 on PCB_V3.
- Firmware pin differences on PCB_V3 (I2C on GPIO2/GPIO1, the DONE polarity,
  the LoRa module) are in the repo-root `CLAUDE.md`.

## Soil-sensor v3: the KiCad version (V3.1)

PCB_V3 came with no editable source, so `v3/kicad/` rebuilds it as a KiCad 10
project from the Gerbers, drill file, BOM and placement file, then applies the
review of 11 September 2026. It was made on 10 November 2026. The designer has
not seen it, nothing about it is in `v3/PCB_CORRESPONDENCE.md`, and no board
has been ordered from it. `v3/kicad/README.md` says what is in the folder and
what to check before ordering.

- The owner means to use the board as a general LoRa node for I2C sensors, not
  only the soil sensor (said 10 November 2026). So the silkscreen carries no
  product name, only `V3.1 2026-11` and the owner's goblin logo, and the KiCad
  project is called `lora-sensor`.
- `lora-sensor/` and `fab/` are generated. Change `tools/design.py` and run
  `tools/build.py`. Do not edit the KiCad files by hand unless the generator is
  being retired. Any finding fails the build, warnings included. Its gates are
  ERC, DRC with schematic parity, `check_routes.py` (the rules the hand
  routing is drawn to), `check_firmware.py` (reads the pins from
  `src/main.rs`, follows each to its part and checks the level each output
  starts at), `check_jlc.py` (puts JLCPCB's
  footprint for each LCSC number at the placement file's position and rotation
  and compares pads), `check_fab.py` (reads the plotted Gerbers and drill
  file and each order's BOM and placement file, and checks the outline, the
  slots for the plug's legs and that an edge at either end of its tolerance
  lets the widest leg into them, the solder paste on its pads and on the
  lands round its legs with none on bare board, the inner planes' distance
  from those slots, the solder mask left between openings, and that every
  part an order fits has a JLCPCB number and a placement row), `check_rf.py`
  (feed impedance, antenna land pattern, ESP32 antenna
  overhang, and the radiated power and harmonics the datasheets predict at
  the firmware's settings), `check_emc.py` (converter loop areas and the
  field they could radiate, the voltage a discharge puts on the plug
  shell's capacitor, the ring on the USB input when it is plugged into
  a live supply, which has to stay on parts rated for it, and the ring
  behind the switch when a plug loses contact and makes it again, with the
  mux on USB and with it back on the battery),
  `check_connectors.py` (pin 1 of the battery and
  sensor connectors against KiCad's footprints for the JST parts, and the
  silkscreen legend against the nets) and `check_values.py` (the 3.3 V rail,
  the wake-up interval, the USB switch's thresholds, current limit and
  clamp, from the part values at their worst case, the mode the mux's pins
  select and how far its output falls while it changes supply, and the
  reset supervisor's threshold against that rail).
  `check_jlc.py` also compares every
  connected pad's function with JLCPCB's symbol for the part, which is an
  independent check of each chip's pinout.
- Every part is placed by JLCPCB (the owner's rule of 10 November 2026: see
  "Mistakes made here"). `design.ORDERS` lists four orders that share the
  Gerbers: `node` (the default, R37 fitted), `timed` (R37 left out),
  `antenna-test` (J3 and R31 fitted, R30 left out) and `bench-test` (J3
  and R31 fitted, L5 and L6 left out). Each gets its own BOM and placement
  file under `fab/`. A build option that would once have been a solder
  jumper or a part swapped by hand is an order. `check_values.py` and the
  USB input part of `check_emc.py` run for every order that is powered,
  with the parts it fits, and hold each to the same marks
  (`parts.for_each_order`). The log has the default order in full and
  another order's blocks only where they differ.
- The `timed` order differs from `node` by R37 alone. For one push
  (10 November 2026) it left C40 out as well, because the brief wants
  under 5 uA from the battery while the timer has the rail off and
  Samsung's limit for a part rated 16 V or less (100 megohm microfarads)
  lets C40 leak 3.6 uA at 3.6 V. Do not do that again. Without C40 a plug
  that makes contact again rings VBUS to 5.78 V in the model, on parts
  whose absolute maximum is 6 V, which the margin the build now asks
  would have stopped. And the same yardstick fails the board anyway: on
  makers' limits the mux alone
  may take 3.7 uA and D6 5 uA. `check_values.py` now adds the off state up
  for an order with no R37 and prints a RISK line: 2.1 uA typical for the
  mux, the converter, the timer and D6, and 4.1 to 6.1 uA allowed to the
  capacitors, for which no typical figure exists. Nobody has measured it:
  do it on the first `timed` board. If it is over and a capacitor is the
  cause, change the part and rebuild, never just leave it off. One to
  look at is TDK's 47 uF 25 V in the same size (C76659, 40,160 at JLCPCB
  on 10 November 2026). TDK's site refused the download here, and a copy
  of its datasheet reached only through a search result gave 2 megohms as
  its least insulation resistance, which would be 1.8 uA: read TDK's own
  sheet first. Then put the part in `tools/design.py` and rebuild, so
  that the hold-up and the contact ring are worked out for it.
- The fitted timer resistor R20 is 68 k, which gives 887 s. The brief's
  68.4 k for 900 s is not a standard value.
- The antenna follows "Case #2" of the two 868 MHz layouts in the Pulse
  datasheet: the W3000 lies along the board edge, fed at one end through
  39 nH in series with 6.8 nH to ground, and its other end goes to an open
  printed tuning line. JLCPCB's symbol calls that pad a ground. It is not
  one.
- What those two checks predict is in `v3/kicad/CE_TESTING.md`. The chip
  antenna radiates 29 per cent on Pulse's reference board, so expect 18.5 dBm
  ERP against the 27 dBm limit and 143 dB of link budget between two boards.
  Common-mode current on the cables is the one emissions cause the layout
  cannot bound: 2.5 uA on a cable reaches the limit below 230 MHz.
- `check_rf.py` also models the firmware's LoRa signal
  (`tools/lora_spectrum.py`) against EN 300 220-2 V3.3.1. At the 250 kHz the
  firmware used until 10 November 2026 the occupied bandwidth did not fit the
  250 kHz sub-band (247 to 250 kHz at SF11, 262 kHz at SF7), so the firmware
  was changed to 125 kHz with SF10 as the default, which leaves 58 kHz or
  more each side. That change has not been on a board: the repo-root
  `CLAUDE.md` has the details and how to undo it. If a later setting stops
  fitting, the check prints a RISK line and does not fail the build, because
  the remedy is a firmware setting.
- The compliance plan was rewritten against V3.3.1 on 10 November 2026: it
  now has eleven tests, and T7 to T11 use the firmware's `p` test signal.
  The 2018 version (V3.2.1) asks for less, so do not read old reports or old
  notes as covering the current one.
- All eight 100 nF capacitors are one part, Samsung CL05B104KB54PNC (C307331,
  50 V, JLCPCB basic), so that the same line serves on the plug's shell.
- Two builds of one design write byte-identical files, the `fab/` folder
  included. KiCad 10.0.8 writes the time of plotting into every Gerber, drill
  file and PDF and ignores `SOURCE_DATE_EPOCH`, so `fab_outputs.py` puts
  `design.DATE` in its place and zips with fixed entry dates. The project
  files needed KiCad's item ids seeded (`KIID.SeedGenerator`) in every
  script. Do not let a script depend on the order of KiCad's DRC report: its
  list of unconnected items changes order and endpoints between runs.
- Added after the review, for production: R37 (a 0 ohm link from SYS_OUT to
  the converter's enable, marked ALWAYS ON) for firmware that never signals
  DONE, and R33 and R34 (100 ohms in SDA and SCL). The nets on the ESP32 side
  of those resistors are `SDA_MCU` and `SCL_MCU`; `SDA` and `SCL` are the
  connector side.
- Added on 10 November 2026 after someone who had not made the design read
  it (see "Mistakes made here"): U13, a TLV803S that holds EN low while the
  3.3 V rail is under 2.93 V and for 200 ms after, with C35 at its supply
  pin and R36 (1 k) in its output; D5 as a 1N4148W; TP2 moved from Q2's base
  to IO4; a ground via beside L5; and L6 as a wire-wound part.
- The USB input is plug, D3, L3 (bead), C7 (100 nF), then U14, a TPS259531
  protection switch, then VBUS to the mux. The mux, the converter and the
  timer allow 6 V and a USB supply may be 5.5 V, so a plug-in ring cannot be
  let onto them. U14 is rated for 20 V and is off while its input rings
  (10.7 V at worst in `tools/hot_plug.py`, on C7's 50 V). It then raises
  VBUS at 0.42 V/ms (C37, 100 nF), which charges what is behind it at
  71 mA, and limits the current to 1.37 A (R40, 1.5 k). The limit is that
  high because the mux hands a flat battery's load to USB while VBUS is
  still at the battery's voltage, which takes 1.03 A for a moment. R38 and
  R39 (110 k and 47 k) turn it on at 4.0 V and off at 3.7 V (3.39 V at the
  least), as high as a USB supply at 4.4 V allows, and keep the ring off
  its enable pin, which allows 6 V. The TPS259531 also holds its output
  down once its input passes 5.5 to 5.9 V, so VBUS cannot stay over 5.9 V.
  That takes it 10 us, so it backs the damping up and is no answer to a
  fast ring. The TPS259571 (C471038) has the same pads and no clamp.
  Nothing has measured any of this. The first two attempts were dampers on
  the input: see "Mistakes made here".
- D6, an ES1D from VBUS to the mux's output, covers the one state in which
  U14 is on and the big capacitors are not behind it. A battery over
  U14's turn-off voltage (two fresh lithium cells are 3.6 V) lets the mux
  go back to it while U14 is still on, and then only C7 and C31 are behind
  the lead. A plug that makes contact again would ring them to about 7 V.
  D6 passes that ring on to the capacitors on the mux's output, a diode's
  drop below VBUS, which damps it. `hot_plug.py` steps through that state:
  5.63 V at the worst case, against 5.58 V with USB selected. That path
  has U14's resistance in it and not the mux's, which is why it is the
  higher of the two. `check_emc.py` holds both 5 per cent under 6 V, and
  under 6 V with capacitors at 35 per cent and switches at three quarters
  of their typical resistance (5.73 and 5.70 V). The mux lets no current
  back into the battery, so D6 does not hold VBUS at the battery's
  voltage: it charges the mux's output up towards USB, and the mux then
  changes over.
  It must stay a silicon diode: a Schottky would leak the battery into
  VBUS, where R9 would drain it and D5 could hold the converter on. With
  USB selected the mux's own switch is across D6 and it carries nothing.
- The mux passes whichever of USB and the battery is the higher: U4's
  select and mode pins (4 and 5) are both on ground, the last rows of the
  truth table in the TPS2116 datasheet. Do not go back to a threshold on
  VBUS. Above the battery's voltage, as the drop's 15 k had it near 4 V,
  a threshold joins VBUS to a lower output, VBUS sags under it and the mux
  can switch back and forth. Below the battery's voltage, as we had it at
  2.0 V for a day, it drags the output down to the threshold at every
  unplug, however good the cells are. R9 is 10 k from VBUS to ground, to
  empty C31 once USB is gone. An LM66200 (C3235556) fits U4's pads and
  does the same.
- The mux disconnects both supplies before it connects the new one, for
  17.7 us typical at 1.8 V (no maximum is given). C1, C38 and C39 (22 uF
  each) and C40 (100 uF, a 6.3 V part) feed the converter alone for that
  time. `tools/supply_change.py` models it at twice that break with the
  capacitors at 60 and 50 per cent, starting from what the battery gives
  the mux's output through 145 milliohms of MOSFET, mux and track. With
  2.0 V at the battery connector and LoRa transmitting, one break leaves
  1.76 V as USB goes in, and the converter stops at 1.5 V. As USB comes
  out the model lets the output fall 0.2 V under the battery before the
  mux changes over (`UNPLUG_SAG`, an assumption), and one break then
  leaves 1.61 V. The gate asks for 10 per cent over the converter's stop
  going in and only for the converter to keep running coming out, where
  the figure has 7 per cent. The mux's reaction time is not in its
  datasheet and not in the model: each 10 us of it costs another 0.05 V
  with LoRa transmitting. With both radios transmitting one break passes
  only from 2.05 V up going in and 2.11 V coming out. Every worst-case
  break but one also takes the timer's supply under the 1.8 V it is
  specified from, and a restart of the timer wakes the board and begins a
  new interval. The datasheet states no hysteresis between the two inputs.
  Its test conditions hold them 0.1 and 0.2 V apart, which may be it. A
  tired battery, whose voltage moves more than that as the load comes on
  and off, can make the mux change over more than once at one crossing.
  How often is not known, and nothing says the capacitors are topped up
  between: two breaks in a row leave 1.56 V with LoRa transmitting and
  three leave 1.33 V. So a change of supply on a nearly flat battery can
  still reset the ESP32, and how often the mux changes over has to be
  seen on a scope.
- R36 is there because the TLV803's output is rated for 5 mA and has to
  discharge the 1 uF on EN at every reset.
- D5 must stay a silicon diode and D4 a Schottky. A Schottky at D5 leaks from
  the converter's enable into the capacitance on VBUS when warm, and that
  charge holds the converter on through the 50 ms in which the timer cuts
  power. A silicon diode at D4 would leave the enable under its 1.2 V
  turn-on with two tired cells.
- J1 is an HRO TYPE-C-31-G-07 (C530607): a plug that sits on the top face
  with two rows of pads, two shell pads and two legs through 0.5 x 1.8 mm
  slots, its shell hanging 10.7 mm over a straight board edge. JLCPCB lists
  it as "SMT Assembly [Fixture Required]", standard assembly only. Its
  footprint is drawn in `tools/make_footprints.py`. Pad and slot positions
  are from the drawing in `v3/kicad/datasheets/`. The contact pads are
  0.27 mm wide as in JLCPCB's footprint for C530607, where the drawing's
  0.36 mm leaves no room for solder mask, and there is solder paste on the
  land round each leg's slot, also as JLCPCB's has: that paste is what
  solders the leg. Their paste is the outline of the two pads, 2.85 mm2
  and all on copper. The shell's rear face stops against the board edge
  and a leg at the wide end of its tolerance has 0.075 mm of play in the
  drawing's slot. So the whole footprint sits 0.1 mm nearer the edge than
  the drawing has it (`PLUG_SET_BACK`) and each slot is 2.0 mm long, 0.2 mm
  more than the drawing's at the end nearer the edge: an edge cut 0.2 mm
  proud then still lets the legs in. The drawing's general tolerance on
  where the legs sit is wider than that covers, and only built boards will
  show whether it matters. The shell stands 0.15 mm below the bottom face
  of the 0.8 mm board and the legs about 0.8 mm. The slots are plated, and
  JLCPCB asks for 0.3 mm between a plated hole and copper on an inner
  layer. The board's general clearance let the planes come within 0.2 mm,
  so the project carries a rule that holds them 0.35 mm off
  (`SLOT_TO_PLANE`), and `check_fab.py` measures it on the Gerbers.
  Only A6 and A7 carry the data pair and only A5 a CC resistor. Each
  ground and VBUS contact is joined to its twin in the other row by a
  short track.
- U11 must be the Wio-SX1262 without IPEX (Seeed SKU 113991436). JLCPCB does
  not stock it and places it from modules the owner sends them (the owner
  agreed to that on 10 November 2026). The BOM carries C9900285183, JLCPCB's
  entry for sent-in parts of that number. That entry has no footprint in
  their library, so `footprint_as` in `tools/design.py` names C55348741,
  their entry for the IPEX version, for the placement check. C55348741
  itself will not do: its antenna pad is not connected, and it was out of
  stock on 10 November 2026.
- The LoRa module's RF_SW pin (pad 1) is on GPIO38 with R25, 10 k, to
  3.3 V. Since 10 November 2026 the firmware drives GPIO38: high to
  receive, low to transmit and to idle (`rx_enable` in
  `src/lora/driver.rs`). Host tests check the level at every command that
  changes the radio's mode, after a transmit that completes and one that
  fails to start, and when the receiver or `init` fails. That is what
  Seeed's datasheet for the module asks, what the
  brief has, and what Meshtastic's build for the same Seeed kit does
  (`SX126X_RXEN 38`). It has not run on a board. Firmware from before that
  date leaves the pin alone: R25 then holds it high all the time on this
  board, and on the Seeed kit it floats. Seeed's staff say on their forum
  that RF_SW is the /CTRL input (pin 6) of the module's antenna switch and
  DIO2 its CTRL input (pin 4). On a switch with those pins a high level on
  pin 6 leaves CTRL alone in charge, which is why R25 pulls up, but nobody
  has named the part. R25 stays: it keeps the receive path on until the
  firmware takes the pin, and costs 0.33 mA while the pin is held low.
- `v3/kicad/CE_TESTING.md` is how to run the compliance plan
  (`walkie-textie-flutter/docs/COMPLIANCE.md`) on this board.
- V3.1 designators differ from both the brief and PCB_V3. Carried over under a
  new name: J1 (plug, was U8), J2 (sensor connector, was U3), C2 (was U2), R14
  (was U6), D4 and D5 (were U7 and U9), ANT1 (was L1). U11 is now the Wio
  module, and C1, C9, L2 and L3 are different parts under the old names. TL1
  is the antenna's printed tuning line, not a part.
- The tools import KiCad's `pcbnew` module, so they run against the system
  KiCad 10.0.8 from the KiCad PPA (`/usr/bin/kicad-cli`), not the 10.0.3
  AppImage that `kicad-cli` on PATH resolves to. Both read the same files.
- `as-delivered/` is PCB_V3 itself imported into KiCad, matching the delivered
  copper to within 4 micrometres. Use it to measure, or to run DRC on what the
  designer delivered.
- JLCPCB reads placement rotations against its own footprint for the exact
  LCSC number, and two parts in one package can be drawn different ways round:
  ST's USBLC6-2P6 (C15999) and a clone of it (C49451919) differ by 180
  degrees. So `fab_outputs.py` takes each rotation from JLCPCB's footprint for
  that number (cached in `tools/data/jlc/`, fetched from
  `https://easyeda.com/api/products/<C number>/components`), and
  `check_jlc.py` verifies the file as written. Never correct rotations by
  package name. On V3.1 four parts end up turned from what KiCad shows: Q1,
  Q2, U12 and U13. JLCPCB also places a footprint by its own origin and
  numbers its own pads. Its U.FL connector (C88373) has the origin 0.7 mm
  from KiCad's and calls the centre contact pad 2, so `jlc_pads` on J3 maps
  the numbers and the placement file gives the position of JLCPCB's origin.
- For stock, ask JLCPCB's live search (`tools/jlc_stock.py`), not the parts
  catalogue snapshot that the KiCad MCP server downloads. On 10 November 2026
  that snapshot lacked 16 of this board's lines that were in stock, the ESP32
  module and ST's USBLC6-2P6 among them, and led to a clone being chosen for
  U12 until the live search showed 19,993 of the ST part.
- Vishay's Si2367DS-T1-GE3 (C727297) really was at zero stock on 10 November
  2026. Q1 is therefore Vishay's Si2333DS-T1-GE3 (C727544): same pinout, 12 V,
  59 milliohms at 1.8 V gate drive, 100 nA gate leakage. Do not fall back to
  the TECH PUBLIC SI2367DS (C28646392): its datasheet stops at 2.5 V gate
  drive, and two AA cells sag to 2.0 V. D4 is a B5819W from JLCPCB's basic
  range (C8598), the designer's diode from a better-stocked maker, and D5 is
  a 1N4148W (C81598).
- `kicad-cli` sees a project's own symbol and footprint libraries only once
  the `.kicad_pro` exists.
- The board is routed by hand. Every track and via is written out in
  `tools/design.py` with the reason for its path, and the build runs no
  autorouter. The owner asked for this on 10 November 2026, after Freerouting
  2.2.4 had never finished on this board and a home-made grid router had
  taken its place. The owner's rule since then: after one failed autoroute,
  route by hand. `check_routes.py` holds the routes to their rules (what may enter the
  feed's keep-out, no top-layer track under the ESP32 module or between the
  timer's pins, at most 2.5 mm of top-layer track under the LoRa module) and
  prints each long line's length and vias. The method is in the `pcb-design`
  skill.
- The routing's plan, for anyone changing it. The bottom layer carries a line
  wherever it passes under a module or crosses another. Two tracks kept from
  the designer's drop are barriers on the bottom layer: BOOT, from the left
  of the ESP32 to its lower right pad, and the LED's track along y 33.
  SPI comes along the corridor between the two modules on the bottom, in
  three lanes. Chip select and reset come down under the ESP32's right-hand
  pads on the bottom and cross the LED's track on the top. BUSY and DIO1 go
  round the end of the LED's track and under the LoRa module's lower edge.
  The antenna switch enable has nothing to cross and stays on the top.

## Soil-sensor v3: antenna test when the first boards arrive

Remind the owner to check the 868 MHz antenna before approving a production
order. This practical checklist is intentionally kept here rather than in the
PCB-designer handover.

The test needs the VNA structure from the brief: the LoRa module's ANT pad
reaches the antenna's matching node through a 0 ohm isolation link (R18 in the
brief), and a U.FL test connector (J4) reaches the same node through a second
0 ohm test link (R19). Production fits the isolation link only.

Designators change between drops, so identify each part by what it connects to
on that board's own schematic before removing anything:

- PCB_V3 (6 September 2026 drop) does not have the structure. Its R18 and R19
  are the I2C SDA and SCL pull-ups, there is no J4, and the module's ANT pad
  runs straight into the match. Following the steps below by designator on that
  board would remove the SDA pull-up and leave the radio on the antenna.
- The KiCad V3.1 board has it: R30 is the isolation link, R31 the test link and
  J3 the U.FL connector. Production fits R30 only. JLCPCB builds boards ready
  for this test from the `antenna-test` order (`v3/kicad/fab/antenna-test/`),
  with R31 and J3 fitted and R30 left out, so the "prepare the board" steps
  below are already done on those and they must never be powered. Changing
  the matching parts after a measurement is still rework.
- If boards arrive without the structure, do not improvise. Isolating the radio
  would mean cutting the feed trace, so hand the board to the PCB engineer or an
  RF test house.

What is needed:

- A VNA that covers 868 MHz. A NanoVNA-class instrument is adequate.
- A short coaxial test cable for the U.FL test connector.
- The VNA's open, short and 50 ohm load calibration pieces.
- The intended enclosure, battery and sensor cable. Nearby materials can move
  the antenna frequency.
- Suitable equipment for reworking the small RF resistors and matching parts.
  Use the PCB engineer or an RF test house if this rework is unfamiliar.

Prepare the board:

1. Disconnect USB and unplug the battery connector (J3 in the brief, CN1 on
   PCB_V3). Keep the board electrically unpowered throughout the measurement.
2. Remove the isolation link between the LoRa module's ANT pad and the matching
   node (R18 in the brief). This disconnects the transmitter from the antenna
   and the VNA.
3. Fit the test link as 0 ohms and fit the U.FL connector (R19 and J4 in the
   brief). This connects the VNA to the antenna feed.
4. Put the unpowered board and physically disconnected battery in their normal
   enclosure positions. Route the sensor cable as it will be used.

Make the measurement:

1. Set the VNA sweep to 800-930 MHz.
2. Calibrate at the loose end of the cable with the open, short and load pieces.
   This removes the cable's error from the displayed result.
3. Connect the calibrated cable to the U.FL connector. Keep hands, tools and
   metal objects away from the antenna end of the enclosure.
4. Display VSWR or S11 and locate the lowest point of the curve. This is roughly
   the antenna's resonant frequency.
5. The low point should be near 868 MHz, with VSWR no greater than 2:1 across
   863-870 MHz. Do not approve the match if the dip is outside the band or VSWR
   is above 2:1.
6. Have the PCB engineer use the VNA Smith chart to adjust the pi network at the
   feed (one series part and two shunt positions). Do not guess replacement
   values: published matches, such as TI's 1.0 pF and 12 nH for DN038, only hold
   on the maker's reference board. Re-measure after each component change.
7. Record the final component values and save a screenshot. Repeat on at least
   three boards, if available, to check unit-to-unit variation.
8. Disconnect the VNA, remove the U.FL connector and the test link, and refit
   the isolation link as 0 ohms. The board can then be powered for normal LoRa
   range testing.

Never transmit a LoRa packet into the VNA. Keep the board unpowered, and check on
the schematic that the link you removed is the one on the ANT pad before
attaching the instrument.

## Soil-sensor v3: the USB-C plug sets the board thickness

This section is about the plug on the designer's drops. The KiCad V3.1 board
no longer uses it: JLCPCB cannot place a plug that clamps the board edge, so
V3.1 has an HRO TYPE-C-31-G-07 that sits on one face (see the V3.1 section
above). What follows is what to check on any further drop from the designer,
and why his plug was dropped.

The soil sensor uses a USB-C **plug**, not a socket, so the board plugs straight
into a USB-C socket. This is intended and overrides the HRO TYPE-C-31-M-12
receptacle in the brief. The part is U8, `TYPE-C 24P-GTJB 040`, LCSC
C3151751. Its manufacturer drawing labels it "TYPE-C PLUG"; the LCSC listing
title says receptacle and is wrong.

With the PCB_V2 drop of 30 August 2026 the designer wrote that this plug has
two rows of mounting pins about 0.9 mm apart, that a 1.6 mm board will not go
between them, and that the board should be ordered 0.9 mm thick. His words are
in `v3/PCB_CORRESPONDENCE.md`.

It is a cable plug: its two rows of solder tails clamp both faces of the board
edge like a cable's paddle card, and its body sits about 10 mm beyond the edge.
The drawing's "Cable Side PCB Layout" gives the board there as 0.80 +/- 0.05 mm.
Its side view gives the gap between the two rows of tails as 0.70 +/- 0.10 mm
at the contacts and 0.90 +/- 0.10 mm at the shell latch; the latch figure is
the gap the designer called "around 0.9mm". The Gerbers of both drops agree:
the plug has pads on both `GTL` and `GBL`, and it carries the only bottom-side
solder paste on the board. The drawing is kept at
`v3/kicad/datasheets/TYPE-C-24P-GTJB-040_plug_drawing.pdf`.

The board needs two things besides the 24 pads, both from that drawing:

- A tongue on the board edge that slots into the back of the plug: 6.10 mm
  wide, 0.90 mm long, 5.50 mm wide at its tip. The signal pads start 0.30 mm
  behind the tongue's shoulder and the latch pads 0.40 mm behind it.
- A latch pad on each face. The shell's two latch tails sit on opposite faces
  of the board, one at each end of the pad row.

PCB_V3 draws the tongue only as a second, open shape on the outline layer and
puts both latch pads on the top face. This was found on 9 November 2026 and has
not been sent to the designer. The review's "only one closed shape on the
outline layer" could be met by deleting the tongue, so check both points on
every drop.

The tongue also has to be narrower than the drawing says. The drawing's rear
view gives the opening that takes it as 6.25 +/- 0.15 mm, and JLCPCB routes an
outline to +/- 0.2 mm, or +/- 0.1 mm when asked. A tongue drawn at 6.10 mm can
therefore be cut wider than the narrowest opening: draw it 6.00 mm wide and
ask for the +/- 0.1 mm option. The pads must have no solder paste, because the
plug is slid on and soldered by hand: reflowed paste would leave bumps on pads
that the plug's tails, 0.7 mm apart, have to pass over on a 0.8 mm board.
Check the width and the paste on every drop. The router's radius in the two
corners at the root of the tongue can hold the plug up to 0.2 mm off the board
edge, which the 1.5 mm pads allow for.

All of that is hand work, which the owner ruled out on 10 November 2026. A
drop that keeps this plug cannot be built to that rule. Ask for a plug that
sits on one face of the board, as V3.1 has.

Wire it as a plug, not as a socket:

- 5.1 kohm to GND on A5 (CC) only. B5 is VCONN and stays unconnected. Rd on both
  A5 and B5 makes a source see a debug accessory, and most chargers and laptops
  then leave VBUS off. PCB_V3 has this mistake (R3 on B5).
- D+/D- are on A6/A7 only; B6/B7 are not populated in the plug.

**Order 0.8 mm, not 0.9 mm.** Two reasons:

- 0.9 mm is not an orderable thickness. JLCPCB's 4-layer options are 0.8, 1.0,
  1.2, 1.6 and 2.0 mm, and only 0.8 mm is inside the plug's 0.75-0.85 mm window.
- 0.8 mm finished is already what the handover brief specifies, so the RF feed
  and the impedance stack-up are meant for it anyway.

Order-time consequences, none of which are in the delivered package:

- Select the 4-layer 0.8 mm impedance stack-up explicitly and get the released
  version before the RF feed is finalised. Do not accept the fab's default.
  On the KiCad V3.1 board this matters less than it sounds: the 50 ohm feed is
  2.5 mm long, 4.6 degrees at 868 MHz, so even the thicker default prepreg
  costs under 0.01 dB (`v3/kicad/tools/check_rf.py` prints the figures). Prefer
  the 0.1 mm prepreg build there, but do not hold an order for it.
- Tell the fab the plug clamps that board edge, so the thickness and the outline
  tolerance on that edge are held. JLCPCB holds a 0.8 mm board to +/- 0.1 mm,
  wider than the +/- 0.05 mm on the plug's PCB layout. The plug's own tail gaps
  (0.6 to 0.8 mm at the contacts, 0.8 to 1.0 mm at the latch) take a board from
  0.7 to 0.9 mm, so this is acceptable, but measure the boards on arrival. The
  pads stopped 0.241 mm short of the edge on PCB_V2.
- Surface finish is lead-free HASL per the brief. ENIG is flatter on the plug's
  0.5 mm pitch pads; the owner has not chosen between them. On 0.8 mm confirm
  the fab will not add stiffeners or panel tabs across the connector edge.
- Ask for the outline to +/- 0.1 mm, for the tongue's sake, and push a plug
  onto a bare board before soldering the first one.

## Soil-sensor v3: ideas for a future revision

Deliberately left out of the PCB_V3 review to keep the designer's changes small.

- **USB detection.** Let the firmware know when USB power is connected, for
  example to stay on for setup instead of shutting down after a reading. The
  cheapest way reuses the TPS2116 ST pin: it is open drain, released while USB
  (VIN1) powers the board and pulled low on battery. Pull it up to the switched
  3.3 V rail, not VBUS, and route it to a free GPIO (IO5 is unused on PCB_V3).
  The alternative is a divider from VBUS: 68 kohm to the GPIO and 100 kohm to
  GND gives 2.6 V at 4.4 V and 3.3 V at 5.5 V. Never use IO35-IO37 (the N8R8's
  octal PSRAM) or a strapping pin (IO0, IO3, IO45, IO46). PCB_V3 put ST on IO37
  with its pull-up on VBUS, which breaks the PSRAM.

Left out of the KiCad V3.1 board for want of room or of a decision, noted on
10 November 2026:

- Mounting holes. The board has none, so an enclosure has to hold it by its
  edges.
- Test pads on the 3.3 V rail, SYS_OUT and VBUS. The brief's droop test has to
  probe the pads of parts.
- Pads for UART0. Flashing and logs go over USB only. The fallback is fine
  wires on module pads 36 (receive) and 37 (transmit).
- The battery voltage on an ADC pin, through a divider that is switched off
  in sleep, so that a sensor can report the state of its cells.
- A change of supply with no break. The mux disconnects both supplies for
  some microseconds whenever USB goes in or comes out with a battery
  fitted, and with both radios transmitting from a nearly flat battery the
  three 22 uF capacitors on its output may not carry the converter through.
  Closing that would take a make-before-break stage (an ideal-diode
  controller for each supply) or several times the capacitance.
- A fuse or resettable fuse in the battery lead. Neither the board nor the
  brief has one, and the safety checklist in the compliance plan asks what
  limits the current into a short.
- The firmware declares 100 mA to the USB host (`usb_config.max_power` in
  `src/main.rs`). The review of the design estimated up to about 0.45 A while
  the radios transmit. Hosts rarely enforce the figure, so nothing breaks,
  but the declaration should be raised when the firmware is next touched.

## Rev 2 decisions that are settled

- **4-layer, 30.5 x 40.1 mm.** The brief asked for 2-layer 1.6 mm at the
  smallest practical size. The delivered board is neither. This has not been
  put to the designer and remains the one substantive open question.
- **Stackup is JLCPCB JLC04161H-3313**, not a generic default: 0.035 mm outer
  copper, 0.0994 mm prepreg, 0.0152 mm inner copper, 1.265 mm core, 1.5842 mm
  total. The RF feed is sized for it, so the order must select that stackup
  explicitly. JLCPCB's default 4-layer 1.6 mm build is the 7628 stackup with
  roughly double the prepreg.
- **35 vias at 0.15 mm drill / 0.3 mm pad are intentional.** The designer
  confirmed 0.15 mm is the minimum manufacturable size and is staying. They are
  free GND stitching vias in open copper, tented. Order "Min via hole size" as
  0.15mm; 0.3 mm would fail the drill file.
- **The pi network at ANT1 is the antenna tuning point.** C12 shunt, R9 series,
  C11 shunt, feeding ANT1. C11 and C12 are fitted empty on purpose and are
  tuned against a VNA at bring-up. **R9 is the series link and must be
  populated**, or the antenna is disconnected. The designer's phrase "DNP caps
  and resistor" is loose; his own BOM fits R9.
- **JLCPCB, not PCBWay**, on cost.

## Verifying anything here

`kicad-cli` 10.0.3 is installed and matches the version the board was exported
with, so the delivered files can be checked rather than trusted. Work on a copy;
do not write into `archive/v2-production/`.

```bash
SRC="archive/v2-production/MESHTASTIC NODE_source/MESHTASTIC NODE"
kicad-cli pcb drc --refill-zones --severity-error --format json -o drc.json "$SRC/MESHTASTIC NODE.kicad_pcb"
kicad-cli sch erc --severity-error --format json -o erc.json "$SRC/MESHTASTIC NODE.kicad_sch"
kicad-cli sch export pdf -o schematic.pdf "$SRC/MESHTASTIC NODE.kicad_sch"
kicad-cli pcb export gerbers --no-protel-ext --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" -o out/ "$SRC/MESHTASTIC NODE.kicad_pcb"
```

Current state as of 21 August 2026: DRC reports 124 violations after a zone
refill (263 before, the difference being a stale saved fill). ERC reports 13,
almost all missing power flags. An ERC/DRC-clean project was a stated
deliverable and has not been met. The substantive DRC items are a malformed
board outline where the USB connector footprint's edge cuts do not close, 35
vias breaching the project's own minimum drill and annular rules, and five
clearance breaches on the RF feed track.

`gerbonara` (see `archive/README.md`) renders Gerbers to SVG and is the sane way to
look at artwork.

## Coordinate systems, which is where the mistakes come from

The rev 2 board sits at an offset in the KiCad file. Board coordinates, as used
by the Gerbers, the drill files and the `.pos`, relate to the raw `.kicad_pcb`
numbers as:

```
x_board = x_kicad - 100
y_board = 100 - y_kicad      # note the flip
```

Footprint pad positions additionally need the footprint rotation applied, and
the pad's own `(at x y angle)` angle is already absolute rather than relative.
Getting that wrong is easy and is exactly what happened below.

## Mistakes made here, and how to catch them

Four wrong conclusions were reached on this board in a single day, two of which
were sent to the designer. The pattern in all of them is the same: a claim was
derived from the design source when the fabrication outputs would have answered
it directly, or a default was assumed without checking the number.

**Claimed vias were sitting inside U5's pads.** Pad positions were derived from
`.kicad_pcb` by applying the footprint rotation by hand, with the sign
backwards, which put U5's pads 1 to 3 at board y = 12.4 instead of y = 2.0. A
row of stitching vias happened to run along y = 12.45, so it looked like
via-in-pad. It went to the designer before it was checked.

> Catch it by testing drill coordinates against the **`F_Mask` apertures**, not
> against computed pad positions. A hole that can wick solder is a hole inside a
> solder-mask opening, and both files are already in board coordinates. The real
> answer was zero of 77 holes inside any of 139 mask openings.

**Claimed the stackup was KiCad's untouched default.** The reasoning was that
`copper_finish` was "None" and `dielectric_constraints` was "no". Those are
unset KiCad switches and say nothing about the geometry. The thicknesses were
JLC04161H-3313's exactly.

> Catch it by comparing the actual layer thicknesses against the fab's published
> stackup table before calling anything a default. A suspiciously specific number
> like 0.0994 mm is a fab's prepreg spec, not a default.

**Nearly claimed the delivered Gerbers carried a stale zone fill.** DRC on the
saved board showed 145 GND and 141 +3V3 items at 0.000 mm clearance, which looks
like a short. The saved fill was indeed stale, but plotting refills zones, so
the delivered artwork was correct all along.

> Catch it by testing the Gerber geometry itself: parse the `G36`/`G37` copper
> regions and check whether the via centre is inside the polygon or in a void.
> The delivered `B_Cu` had a proper 0.4 mm void around every flagged via.
> Remember that `kicad-cli pcb export gerbers` refills zones, so a regenerated
> export is not evidence about the saved fill either way.

**Trusted `MESHTASTIC NODE.net`.** It is a 19 June rev 1 leftover that still
references U3, U4 and C13, none of which exist on rev 2.

> Check file dates inside the source drop before reading anything as current.
> `.kicad_pcb` is the authority for the current board; the netlist and
> `fp-info-cache` in that folder are stale.

**Recorded a drafted message as if it were the sent one.** A draft was written
into `PCB_CORRESPONDENCE.md` marked SENT; four differently worded messages had
actually gone out.

> That file is a verbatim record. Only write what has been confirmed sent, and
> ask for the actual text rather than assuming a draft went out unchanged.

**Soil sensor: called the USB-C plug a straddle-mount socket.** The PCB_V2
review and this file described LCSC C3151751 as a receptacle the board edge
slides into, inferred from the footprint and the designer's thickness note. The
0.8 mm advice happened to be right, but nobody asked how a plug's CC contact is
wired, so the socket-style pair of CC resistors on PCB_V3 went unquestioned.

> Read the part's own drawing before saying what a part is; the packaging list
> and pin table are quickest. The LCSC listing title was wrong.

**Soil sensor: left vias under and against pads in the KiCad version.** Two
ground vias carried over from PCB_V3 ended up inside the 3.3 V pad of a
capacitor added later. KiCad gives copper the net of the one pad it touches
when it loads a board, so they came back as 3.3 V vias and DRC stayed clean.
Seven more vias, placed by the router and the stitching, touched pads of their
own net, which KiCad's DRC does not look at.

> Catch it on the fabrication outputs: test every drill hit against the
> solder-mask openings, as `v3/kicad/tools/check_fab.py` does. The project also
> carries a DRC rule for it (`lora-sensor.kicad_dru`), because the stock rules
> compare a via only with pads of other nets.

**Soil sensor: carried a part the review had questioned into the KiCad
version.** The review of 11 September 2026 asked the designer to check that
C25, 1 nF and 50 V between the plug's shell and ground, survives a static
discharge. V3.1 kept the part unchecked through three rounds of production
checks. It fails: 4 kV by contact puts 520 V on it.

> A review line that asks the designer to check something is an open question
> in our own version until we have done the sum. For touchable metal the sum
> is charge sharing with the test network's 150 pF, and
> `v3/kicad/tools/check_emc.py` now does it on every build. The review's other
> such line, the battery connector's pin 1, is `check_connectors.py`.

**Soil sensor: said two builds wrote identical files after comparing only the
KiCad project.** The `fab/` folder differed on every build, because KiCad
writes the time of plotting into each Gerber, drill file and PDF. The README
and this file both said a diff in git was a real change.

> Hash every generated file, the fabrication folder included, across two
> builds made more than a second apart.

**Soil sensor: called V3.1 ready for production on our own checks alone.**
Every gate in the build tested something we had already thought of. A reviewer
given only the files and the datasheets found six things in one pass: the
plug's tongue drawn at the drawing's 6.10 mm for an opening that can be
6.10 mm, before the factory's tolerance; solder paste on pads that are soldered
by hand after the plug is slid on; no reset supervisor on a rail that is
switched by design; a USB input that can ring past the 6 V rating of the parts
on it; a Schottky diode whose leakage holds the converter on when warm; and a
test pad labelled IO4 that sat on the transistor's base.

> Have someone who did not make the design read it against the datasheets
> before calling it done. For anything that has to fit, stack the tolerance of
> the part on the tolerance of the factory: a size that matches the drawing's
> nominal proves nothing. The supervisor's threshold is a gate in
> `v3/kicad/tools/check_values.py`. The tongue and the bare pads went when
> the plug was replaced.

**Soil sensor: sized a part from one run of a model.** The fix for the ringing
USB input was a 10 uF capacitor behind 0.47 ohms, chosen because a model gave
5.7 V with one lead, one supply and the capacitor's typical value at 5 V. The
README and this file then said "under 5.7 V". Run over the range of leads,
supplies and capacitor values that can occur, the same model gave 6.3 to
7.5 V, over the 6 V limit in every case.

> A model that passes at one point is not evidence. Sweep every input it
> assumes over the range that can occur and quote the worst case, with the
> assumptions beside it. The sweep is now `v3/kicad/tools/hot_plug.py` and a
> gate in `check_emc.py`. Keep a model that a document quotes in the repo, not
> in a scratch folder.

**Soil sensor: modelled the USB input with no battery fitted.** The damper
that replaced that capacitor was sized against a sweep, and held 5.87 V
against a 6 V limit. A second reviewer asked what the mux does when cells are
in: it switches to USB in the middle of the ring and puts the converter's
22 uF across the input, which the model had left out. His own sum gave 6.05 V.
The margin was 0.13 V before that, on parts whose ratings are not negotiable.

> A margin of two per cent on a model with assumed inputs is not a pass. And
> list the states the board can be in (each supply present or not, each load
> on or off) before modelling one of them. The fix was to stop defending the
> margin: a switch rated for 20 V now takes the ring, and nothing rated for
> 6 V is ahead of it, which `check_emc.py` checks from the netlist.

**Soil sensor: designed in parts that someone has to solder.** V3.1 kept the
designer's plug, which clamps the board edge and is soldered on both faces,
and marked it "fit by hand" with gates to keep paste off its pads. It also
had a solder jumper for one use and a LoRa module with no JLCPCB number. The
owner's answer on 10 November 2026: everything must be placeable by the
manufacturer.

> Before choosing a part, look up how the assembler builds it. JLCPCB's part
> page says "SMT Assembly", and for awkward parts "Fixture Required" and
> "Standard Only". A build option is an order with its own BOM and placement
> file, never a jumper. A part the assembler does not stock is sent to them
> and still carries their number. `fab_outputs.py` and `check_fab.py` stop
> the build on a fitted part with no number or no placement row.

**Soil sensor: drew the new plug's legs with no solder paste.** The footprint
for the HRO plug gave its two through-slot legs copper and no paste, so
nothing would have soldered them, and the gate counted paste on the surface
pads only. The file also said the land pattern was the drawing's when the pad
sizes were JLCPCB's. A reviewer found both by laying JLCPCB's footprint for
C530607 over ours: theirs has one stencil opening over each leg and the shell
pad beside it.

> Compare a footprint drawn by hand with the assembler's own footprint for
> the part, layer by layer, paste included. Say in the file where each size
> comes from. A leg through a slot is soldered by paste printed over it.

**Soil sensor: set the mux's threshold for plugging in and did not work out
unplugging.** A threshold of 2.0 V on VBUS cured the switching back and forth
at plug-in. At unplug it kept USB selected until VBUS had fallen to 2.0 V,
which dragged the converter's input there with fresh cells fitted. The check
then printed "the output is not let under 1.82 V", a sentence no line of the
check computed, and it was untrue: the break after the threshold takes the
output lower.

> Work out every change of state in both directions, at the load's peak. And
> a sentence a check prints is a claim like any other: print only what the
> check has computed. The mux now takes the higher input, and
> `tools/supply_change.py` computes what its break leaves.

**Soil sensor: placed a plug that stops against the board edge at its drawing's
nominal.** The plug's shell meets the edge and its legs have 0.15 mm of play in
their slots. JLCPCB cuts an outline to 0.2 mm, so an edge cut proud would have
held the legs out of the slots. This is the tongue mistake again, with a
different part.

> For every part that touches or hangs over an edge, find what stops against
> what and stack the outline tolerance on it, with the part at the bad end
> of its own tolerance. `check_fab.py` now does the sum for the plug.

**Soil sensor: read a shape's bounding box as the shape.** To give the plug's
legs paste "as JLCPCB's footprint has it", a script printed the extent of
their paste region, 1.475 by 3.15 mm, and the footprint got a rectangle that
size: 4.5 mm2, a third of it on solder mask beside the corner contacts.
Their region is the outline of the two pads, 2.85 mm2, all on copper.

> Take the area of a shape and plot it before copying it. The gate now
> fails on paste that is not over copper.

**Soil sensor: modelled the plug losing contact with the mux in one position
only.** The check for a plug that makes contact again kept every capacitor
behind the protection switch. With a battery over the switch's turn-off
voltage, the mux has gone back to the battery while the switch is still on,
and only 1.1 uF is behind it: the same formula gives about 7 V on parts that
allow 6 V. This is the "modelled with no battery fitted" mistake again, one
part further on.

> When a model covers a path with two switches in it, write down the
> positions of both before modelling any of them. D6 now clamps that
> state and `check_emc.py` works out both.

**Soil sensor: started the hand-over sum from the battery connector's
voltage.** The hold-up model took the mux's output to start at the battery's
2.0 V. The MOSFET, the mux and the tracks drop 0.06 V at that current, and
that was all the margin the figure had.

> A voltage quoted at a connector is not the voltage at the part. Follow the
> current through everything in between before using it.

**Soil sensor: let "the firmware never drives it" stand for "it need not be
driven".** The module's RF_SW pin got a pull-up because the firmware leaves
GPIO38 alone, and the build printed "ok". The module's datasheet says the pin
is low while transmitting. It may well not matter, but nothing here showed
that.

> When firmware leaves a pin alone, read what the part's datasheet wants on
> that pin in every mode, and say which modes the default does not meet.
> The firmware now drives the pin, and `check_firmware.py` follows GPIO38
> to it.

**Soil sensor: gave up margin on a hard rating to meet a soft target, on one
part's limit.** C40, 100 uF, went on the mux's output to carry the converter
through the mux's break. A reviewer pointed out that the brief wants under
5 uA from the battery while the timer has the rail off and that this part's
datasheet allows 3.6 uA of leakage on its own. So the `timed` order left C40
out, and that was pushed. The next reviewer added up the whole node: the
mux's limit is 3.7 uA and D6's is 5 uA, so the target fails on limits with
or without C40. Leaving it out had meanwhile taken the contact ring on VBUS
from 5.58 to 5.78 V, against an absolute maximum of 6 V, behind a gate that
only failed at 6.00 V.

> Before acting on one part's limit, apply the same yardstick to every part
> on the node and print the sum. A target for battery life is soft and an
> absolute maximum is not: never pay for the first with the second. Give a
> gate on a rating a margin, and a second run with harsher inputs, so that
> a thin pass stops the build.

**Soil sensor: printed a bound the check had not computed, again.** With the
battery selected, `check_emc.py` said the ring through D6 "stays under" the
figure for the USB-selected state, on the argument that the same capacitors
damp it. Stepped through time it is 5.63 V against 5.58 V: that path has no
mux resistance in it. The fix for the earlier mistake of this kind had
replaced one unsupported sentence with another.

> An argument for a bound is not the bound. Model the state, check the model
> against a second method (`peak_from` agrees with a fine time-step run to
> a millivolt) and print its number.

**Soil sensor: passed inner planes 0.2 mm from the plug's plated slots.**
JLCPCB asks for 0.3 mm between a plated hole and copper on an inner layer,
and the board's general clearance is less.

> A fabricator's rule that the project's rules do not carry needs its own
> rule and its own gate on the Gerbers.
