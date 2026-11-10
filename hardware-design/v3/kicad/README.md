# LoRa sensor board in KiCad (V3.1)

The designer's PCB_V3 arrived as fabrication files only: Gerbers, a BOM, a
placement file and pictures. There was nothing to edit. This folder rebuilds
that board as a KiCad 10 project from those files, then applies the changes
from our review of 11 September 2026. The result is called V3.1.

The design passes every check that can be made without a board in hand, but no
board has been made from it. The designer has not seen this version and
nothing here has been sent to him. Two jobs need the real thing: tuning the
868 MHz antenna match on a VNA, and the CE tests in `CE_TESTING.md`. One
finding was about the firmware and not the board: its 250 kHz LoRa bandwidth
did not fit the 250 kHz sub-band it transmits in. The firmware now uses
125 kHz, a change that has not yet been on a board. `CE_TESTING.md` has the
figures.

JLCPCB places every part. Nothing is left to solder when the boards arrive.
One part, the LoRa module, has to be sent to JLCPCB first, because they do not
stock it.

One thing is worth knowing before a board exists. The power mux
disconnects both supplies for some microseconds each time USB is plugged in
or pulled out with a battery fitted. On a nearly flat battery, with a radio
transmitting, that can stop the converter, and the supervisor then resets the
ESP32. Firmware should expect to be restarted by a change of supply. The
figures are under "On the first boards".

## What is here

`lora-sensor/` is the KiCad project: schematic, board, and its own symbol and
footprint libraries. Open `lora-sensor.kicad_pro` with KiCad 10.

`fab/` is what goes to the factory: Gerbers and drill files (also zipped), a
BOM and a placement file with JLCPCB's column names, and PDFs of the schematic
and the assembly drawing. There are four orders, which share the Gerbers and
differ in what is fitted:

| Order | Files | What it is for |
| --- | --- | --- |
| node | `fab/BOM.csv`, `fab/CPL.csv` | The default. R37 holds the converter on, for firmware that never signals the wake timer, such as the radio firmware in this repo |
| timed | `fab/timed/` | R37 left out, so the wake timer cuts the power between readings, and C40 left out to keep the current low while it is off. For firmware that signals DONE |
| antenna-test | `fab/antenna-test/` | The U.FL connector and its link fitted and the radio's link left out, for measuring the antenna on a VNA. Never power one of these |
| bench-test | `fab/bench-test/` | The U.FL connector and its link fitted and the two antenna matching parts left out, for the conducted compliance tests |

`as-delivered/` is PCB_V3 exactly as the designer delivered it, imported into
KiCad so it can be opened, measured and compared. Plotted back out, its copper
matches his Gerbers to within 4 micrometres. Running DRC on it shows his
outline, drill and thermal-relief problems directly.

`tools/` builds all of the above. `datasheets/` holds the documents the layout
and the part changes rest on: the drawings of the USB plug and of the plug the
designer used, the Pulse antenna datasheet, the TPS631000, TPS2116, TPS2595
and TLV803 datasheets, and the datasheet of the MOSFET that replaced the
brief's. `CE_TESTING.md` is how to run the compliance tests on this board.

## The project is generated

Everything in `lora-sensor/` and `fab/` is written by `tools/build.py` from
`tools/design.py`, which lists every part, its position, its nets and every
track. The board is routed by hand: each track and via is written out there
with the reason for its path, and no autorouter runs. Change the design there
and rebuild. An edit made in KiCad is lost at the next build. Two builds of
the same design write the same files, so a diff in git is a real change.

If you would rather carry on in KiCad by hand, that works too: the project is
complete and passes its checks. Stop running the build after that.

```bash
cd hardware-design/v3/kicad
uv venv --python /usr/bin/python3 --system-site-packages .venv
uv pip install --python .venv/bin/python -r tools/requirements.txt
.venv/bin/python tools/build.py
```

The Python has to be the one KiCad's `pcbnew` module is installed for, which
is why the virtual environment is allowed to see system packages. The build
takes under a minute and stops at the first failing step. A warning fails it
the same as an error. A part that is new to the BOM needs `--fetch` once, to
download JLCPCB's library entry for it. These are the checks it ends on:

- KiCad's ERC on the schematic, and DRC on the board with the board compared
  against the schematic.
- The rules the routing was drawn to. Only the feed, its match and ground go
  near the 868 MHz feed. No top-layer track runs under the ESP32 module or
  between the timer's pins. A line may have 2.5 mm of top-layer track under
  the LoRa module to reach its pad and no more. The log lists each long line
  with its length on each layer and its vias.
- The firmware in this repo against the board. The pin numbers are read from
  `src/main.rs` and each is followed to the part it has to reach, GPIO38 to
  the LoRa module's RF_SW pin among them. The level each output starts at
  is checked too.
- Every part of every order has a JLCPCB part number and a row in the
  placement file. A part with neither would be left for someone to solder.
- Every placed part against JLCPCB's own footprint for its part number, at
  the position and rotation in the placement file. A part that would be
  fitted turned shows up as pads that miss. Each connected pad's function is
  compared with JLCPCB's symbol for the part as well, so a substitute with
  another pinout is caught.
- The values that set the 3.3 V rail, the wake-up interval, the voltage at
  which the USB input's switch passes power, its current limit and how fast
  it raises its output. Each is worked out at the worst case of the
  tolerances, against the datasheet formulas. The reset supervisor's
  threshold is checked against that rail.
- The power mux: that its pins put it in the mode that passes the higher
  supply, and how far its output falls while it changes from one supply to
  the other (`tools/supply_change.py`).
- The Gerbers and drill file themselves: one closed rectangular outline, the
  two slots for the plug's legs, a board edge at either end of its tolerance
  still letting the widest leg into them, solder paste on the plug's pads
  and on the land round each leg with none of it on bare board, the inner
  planes 0.3 mm or more from those slots, 0.1 mm or more of solder mask
  between any two openings, no hole in a pad, the antenna area clear, the
  ground plane in one piece.
- The numbers behind the radio layout: feed impedance, antenna land pattern
  and the ESP32 antenna's overhang. Then what the datasheets predict for
  radiated power and harmonics at the power the firmware sets, against the
  legal limits. It also models the firmware's LoRa signal against the
  sub-band it uses and prints a RISK line when the fit is poor. That line is
  the one thing here that does not stop the build, because the remedy is a
  firmware setting.
- What the layout decides about emissions and static discharge: the area of
  the converter's switching loops and the field they could radiate, and the
  voltage a discharge to the plug's shell puts on the capacitor behind it.
  The same step models the ring on the USB input when the board is plugged
  into a live supply, and checks that only parts rated for it are ahead of
  the protection switch. It models a plug that loses contact and makes it
  again as well, when the switch is on and the ring reaches what is behind
  it, with the mux on USB and with the mux gone back to the battery.
- The battery and sensor connectors: pin 1 where JST's drawing puts it, and
  a silkscreen legend that names the net on each pad.

## Before ordering

- Send the LoRa modules to JLCPCB before placing the order. U11 has to be
  the Wio-SX1262 without the antenna connector, Seeed part 113991436. JLCPCB
  does not stock it. Their library has an entry for parts of that number
  that customers send in, C9900285183, and the BOM carries it. If JLCPCB
  gives your modules another number when they book them in, change `lcsc`
  on U11 in `tools/design.py` and rebuild. The module with the connector
  (their C55348741, none in stock on 10 November 2026) leaves the antenna
  pad unconnected and will not do. No other LoRa module JLCPCB stocks has
  this module's pads or the same control pins.
- Choose JLCPCB's standard assembly service, not the economic one. The USB
  plug (J1, C530607) is listed for standard assembly only, with a fixture,
  because its shell hangs 10.7 mm over the board edge.
- Tell JLCPCB in the order's remarks that two parts hang over the board. J1
  overhangs the left edge by 10.7 mm between 24 and 36 mm from the bottom.
  Its shell is thicker than the board: it stands about 0.15 mm below the
  bottom face, and its two legs about 0.8 mm, so no rail or tab can go
  there and the board does not lie flat. The ESP32 module's antenna
  overhangs the top edge by about 6 mm, level with the board. Let their
  engineers place the rails or the fixture to suit.
- JLCPCB's ordinary outline tolerance of 0.2 mm is enough. J1's shell stops
  against the left edge. The edge is drawn 0.1 mm back from where the
  plug's drawing has it, and each slot is 0.2 mm longer than the drawing's
  at the end nearer the edge, so that an edge cut proud still lets the legs
  in. The plug's own drawing allows its legs more variation than that
  covers. JLCPCB holds the plugs, so the first boards are where that shows.
- In the placement preview, check which way round U11 sits. Its number has
  no footprint in JLCPCB's library, so the rotation in the file was worked
  out from their entry for the module with the connector. Pad 1 is the one
  nearest the top right corner of the module's outline on the assembly
  drawing.
- Order 4 layers at 0.8 mm, which the antenna feed is sized for. The two
  slots for the plug's legs are 0.5 mm wide, the narrowest plated slot
  JLCPCB makes.
- The brief asks for lead-free HASL. ENIG is the better choice now: the
  plug's contacts are 0.27 mm pads at 0.5 mm pitch and U14 is a leadless
  package at the same pitch, and both solder more reliably on a flat
  finish. The owner has not chosen.
- When JLCPCB asks for the layer order, `In1_Cu.g1` is layer 2 (ground) and
  `In2_Cu.g2` is layer 3 (3.3 V). Solder paste is on the top face only.
- Pick the stack-up with 0.1 mm prepreg under the outer layers (JLCPCB's 3313
  family) if it is offered. The feed is 2.5 mm long, so the thicker prepreg
  would cost under 0.01 dB. It is not worth a delay.
- Pick the order. Boards that run the radio firmware from batteries need
  the default, which fits R37 (marked ALWAYS ON). That firmware never
  signals the power timer, which would otherwise drop the 3.3 V rail for
  50 ms every 15 minutes. A sensor whose firmware signals DONE needs the
  timed order, which leaves out R37 and C40.
- Run `.venv/bin/python tools/jlc_stock.py fab/BOM.csv 25` for today's stock
  at JLCPCB (25 is the number of boards). On 10 November 2026 every line
  JLCPCB supplies was in stock for 25 boards. The thinnest were the timer at
  416, the USB switch at 1174, the plug at 1242 and the antenna at 1970.
- Flash firmware that drives GPIO38, the LoRa module's RF_SW pin. The
  firmware in this repo does since 10 November 2026: high to receive, low
  to transmit and to idle, which is what Seeed's datasheet for the module
  asks. Older firmware leaves the pin alone, and R25 then holds it high
  all the time.
- The antenna match (L5, L6, with L7 unfitted) starts from the values in the
  Pulse datasheet. Tune it on a VNA on the real board, in its enclosure. The
  steps are in `hardware-design/CLAUDE.md`. A couple of boards from the
  antenna-test order arrive ready to measure: the test link R31 and the
  connector J3 are fitted and the radio's link R30 is not.

## On the first boards

- Look at J1 from underneath. Each of its two legs should stand in its slot
  with solder round it. That solder comes from paste printed on the top
  face on the land round each slot, as JLCPCB's own footprint for the plug
  has it. Check too that the plug's shell sits against the board edge or
  just clear of it, with both legs fully in.
- Watch the LoRa module's RF_SW pin on a scope, at the end of R25 nearer
  the module, on a board from the bench-test order. The firmware holds it
  high while the radio listens and low while it transmits or idles, so it
  should drop for the length of each packet sent. That code has only run
  in host tests. Then read the transmit power at J3 (the steps are in
  `CE_TESTING.md`). R25 holds the pin high until the firmware takes it,
  which costs 0.33 mA while the firmware holds it low.
- Put a scope on C7 and on C31 and plug the board into a live socket, then
  again at the end of the longest extension lead you expect. C7 is ahead of
  the protection switch and may ring to about 10 V, which the parts there
  are rated for. C31 is behind it and should rise smoothly over about
  12 milliseconds to the supply's voltage and no further.
- Repeat with a battery fitted, fresh and nearly flat, and watch C1 and the
  3.3 V rail as USB goes in and comes out. The mux passes whichever supply
  is the higher, so it changes over as the USB voltage crosses the
  battery's. It disconnects both for some microseconds as it does, and C1
  and C38 to C40 feed the converter alone. With 2.0 V at the battery
  connector and LoRa transmitting, the model's worst case for one such
  break leaves 1.76 V on C1 as USB goes in and 1.61 V as it comes out, and
  the converter stops at 1.5 V. With both radios transmitting it passes
  only from 2.05 V up. Below that the supervisor resets the ESP32, which is
  a clean reset, and the board carries on.
- Boards from the timed order have no C40, which leaves 40 uF at the worst
  case where the others have 90 uF. From a 2.0 V battery they ride a
  change of supply while listening (1.79 V left going in, 1.60 V coming
  out). With LoRa transmitting they may not: the same break leaves 1.50 V
  going in and 1.32 V coming out. A timed sensor is awake for seconds in
  each quarter of an hour and restarts cleanly, so that was given up for
  the current the board draws while it is off.
- On a board from the timed order, measure the battery current while the
  timer has the rail off. The brief's target is under 5 uA at 25 C. C40 is
  left out of that order because its datasheet lets it leak 3.6 uA at
  3.6 V on its own.
- Count how often the mux changes over at one crossing. Its datasheet gives
  no hysteresis between the two inputs and no maximum for the break, so
  both are assumptions in `tools/supply_change.py`. A tired battery, whose
  voltage moves a good deal as the load comes on and off it, could make
  the mux change over more than once, and how often is not known. In the
  same model two such breaks in a row with LoRa transmitting leave 1.56 V
  and three leave 1.33 V, which stops the converter.
- With 3.6 V on the battery connector and USB in, wiggle the plug and watch
  C31. A battery that high lets the mux go back to it while the protection
  switch is still on, and a plug that makes contact again would then ring
  C31 past 6 V if D6 were not there. With D6 it should rise to the
  supply's voltage and stop there.
- TP2 makes the power-off edge by hand: touch it to 3.3 V and let go, and
  only while the firmware leaves IO4 as an input. Shorting TP3 to ground
  and letting go makes the same edge. Do either through 1 kohm, because a
  slip is easy: the pads round TP2 are ground, and the pad of R24 beside
  TP3 is on the supply.
- Firmware for a timed sensor has to cut power with IO4 high, then low. It
  starts about 200 ms after the rail comes up, because the reset supervisor
  waits that long. The brief's "wake within 40 ms" is now true of the rail
  only.
- The board has no UART pads and is flashed over USB. If that ever fails,
  the ESP32's UART0 is on module pads 36 (receive) and 37 (transmit), which
  take fine wires.
- The sensor connector follows Adafruit's STEMMA order: pin 1 SCL (green),
  pin 2 SDA (white), pin 3 3.3 V (red), pin 4 ground (black). A lead with a
  plug on both ends can be made either way round, so check its colours
  against the silkscreen before plugging a sensor in.

## What changed from PCB_V3

The first nine are items from the review. The rest came out of checking the
design for production.

- USB-C plug: one CC resistor on A5 only, and the data pair on A6 and A7
  only, as a plug has them.
- The mux status pin goes to a test pad only. IO37 is left alone.
- Converter: 22 uF in, 47 uF out, a 4.3 A inductor, all placed as in TI's
  layout, power-save mode selected, and 22 uF at the ESP32.
- Battery: reverse-polarity MOSFET, connector pin order as the brief, polarity
  on the silkscreen and in copper underneath.
- Timer: the DONE transistor stage from the brief, with test pads. TP2 is on
  IO4 ahead of the base resistor.
- Radio: Wio-SX1262 with its decoupling, series resistors on SPI and a pull-up
  on the pin that enables its antenna switch, which the firmware drives
  from GPIO38.
- Antenna: Pulse W3000 with a pi network, the VNA test structure, a feed over
  ground and the copper-free area and tuning line from the Pulse datasheet.
- I2C connector moved up the edge, with ESD protection and decoupling.
- Board outline is a single closed shape. Ground is stitched around the edge
  and the antenna area. Inner layer 2 is a 3.3 V plane.
- The plug is an HRO TYPE-C-31-G-07, which sits on the top face with two
  legs through slots. The designer's plug clamped the board edge between
  two rows of tails and could only be soldered by hand. The new one needs
  no tongue on the board, so the outline is a plain rectangle. Its pads and
  slots are where its drawing puts them, with each slot 0.2 mm longer at
  the end nearer the edge. The contact pads are 0.27 mm wide and the paste
  on the legs' lands is as in JLCPCB's footprint for the part. The inner
  planes stop 0.35 mm from the slots, where JLCPCB asks for 0.3 mm.
- U14, a TPS259531 protection switch, stands between the plug and the rest
  of the board. Plugged into a supply that is already on, the lead's
  inductance rings with whatever capacitance is on the input, and the mux,
  the converter and the timer allow 6 V on a supply that may be 5.5 V. U14
  is rated for 20 V. It waits for the ring to die on its own input, where
  the model gives 10.7 V at worst across C7, a 50 V part. Then it raises
  VBUS at 0.42 V a millisecond, so nothing behind it sees a step and the
  capacitors charge at under 100 mA. It passes USB power from 4.0 V, stops
  under 3.7 V and limits the current to 1.37 A. Once its input passes 5.5
  to 5.9 V it holds its output down, so VBUS cannot stay over 5.9 V. The
  capacitance straight across the plug is 0.1 uF, inside the 10 uF that
  USB 2.0 allows. The model runs on every build. It is a model, and its
  assumptions are at the top of `tools/hot_plug.py`.
- The power mux passes whichever of USB and the battery is the higher. Its
  select and mode pins are on ground, and R14, half of the divider that
  set a threshold on VBUS, is gone. A threshold above the battery's voltage
  joins USB to a lower output, which pulls VBUS back under the threshold,
  and the mux can then switch back and forth. A threshold below it drags
  the output down to the threshold at every unplug. R9 is now 10 k from
  VBUS to ground, to empty C31 when USB goes. C38 and C39 (22 uF each) and
  C40 (100 uF) join C1 on the mux's output for the microseconds in which
  it has neither supply connected. The timed order leaves C40 out.
- D6, a silicon diode from VBUS to the mux's output, is there for one
  case. A battery over about 3.4 V, such as two fresh lithium cells, lets
  the mux go back to it while U14 is still on. Only C7 and C31 are then
  behind U14, and a plug that loses contact and makes it again would ring
  them to about 7 V, on parts that allow 6 V. D6 puts the capacitors on
  the mux's output behind U14 in that state too, which damps the ring:
  VBUS then rises to the supply's voltage and, in the model, no more than
  a tenth of a volt past it.
- R37, a 0 ohm link, takes the place of a solder jumper. Whether it is
  fitted is a matter of which order is placed.
- One part number serves each value: the designer's 10 k, 1 k, 5.1 k and
  1 uF parts are on the numbers the rest of the board uses, from JLCPCB's
  basic range.
- R33 and R34 put 100 ohms in each I2C line, to slow the edges on the sensor
  cable before an emissions test finds them.
- Q1 is Vishay's Si2333DS, not the brief's Si2367DS, which JLCPCB does not
  stock. It is specified at 59 milliohms with 1.8 V on the gate, which is what
  two tired AA cells give. D4 is the designer's B5819W from a maker JLCPCB
  holds far more of.
- D5, which lets USB power hold the converter on, is a 1N4148W where the
  designer had a second B5819W. A warm Schottky leaks from the enable line
  into the capacitance on VBUS, and that charge then holds the converter
  on through the 50 ms in which the timer means to cut power.
- U13, a TLV803S, holds the ESP32 in reset while the 3.3 V rail is under
  2.93 V and for 200 ms after, with its own 100 nF (C35). R36, 1 k in its
  output, keeps that output under its 5 mA rating while it discharges the
  1 uF on EN. This board switches the rail on and off by design. Espressif's
  hardware guidelines recommend a supervisor in that case, because the
  pull-up and capacitor on EN do not reset the chip when the rail dips
  without reaching zero.
- C25, between the plug's shell and ground, is 100 nF where the designer had
  1 nF. The review asked whether his 50 V part would survive a static
  discharge to the shell. It would not: 4 kV puts about 520 V on 1 nF. On
  100 nF the same part size sees 6 V, and 22 V at 15 kV. All eight 100 nF
  capacitors on the board are now that one 50 V part from JLCPCB's basic
  range.
- L6, the 39 nH in series with the antenna, is a wire-wound Murata part with
  0.26 ohms of resistance. The designer's multilayer part has 1 ohm and a
  self-resonance that can be as low as 1.4 GHz.

A designator is on the silkscreen only where it sits beside its own part and
plainly nearer to it than to any other. On a board this dense that leaves 40
of the 92 off. Every designator is on `fab/assembly.pdf`, inside its part's
outline, with a dot at pad 1 and a bar at each diode's cathode. The three
buttons carry what they do in place of a designator: RST, BOOT and WAKE.
The test pads TP2 and TP3 carry what is on them: IO4 and DONE.

One thing differs from the brief and is kept as the designer had it. The
wake timer is supplied from the mux's output, where the brief has it on the
battery. It then runs from USB as well, and it sees the mux's break: a dip
under the 1.8 V it is specified from can restart its interval.
