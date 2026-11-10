# CE testing the V3.1 board

`walkie-textie-flutter/docs/COMPLIANCE.md` is the plan for self-declaring a
product like this in Great Britain. It has the standards, eleven tests (T1 to
T11), three desk assessments and the paperwork. This file is how to run that
plan on the V3.1 board: what to fit, what to plug in, which state to hold the
board in for each test, and what to change if a test fails.

V3.1 is the hardware that plan asks for. It has the ESP32-S3-WROOM-1 module
with its own antenna, the Wio-SX1262 without IPEX, a chip antenna soldered to
the board behind a pi network, and no antenna connector on units that are
sold. J3 is a test port and stays unfitted in production.

JLCPCB builds the test boards as well as the ones for sale, so no test here
needs a soldering iron. `fab/` holds four orders that share one set of
Gerbers:

| Order | Differs from the product by | Use |
| --- | --- | --- |
| node (`fab/`) | Nothing. R37 holds the converter on | The radio product, and every chamber test of it |
| timed (`fab/timed/`) | R37 left out, so the wake timer cuts the power | The sensor product, and every chamber test of it |
| bench-test (`fab/bench-test/`) | J3 and R31 fitted, L5 and L6 left out: the radio is on the test connector and the antenna is cut off | The conducted tests at J3 |
| antenna-test (`fab/antenna-test/`) | J3 and R31 fitted, R30 left out: the antenna is on the test connector and the radio is cut off | Tuning the antenna on a VNA. Never power one |

But no V3.1 board has been built, so nothing here has been run. Three things
have to happen before a chamber is worth booking. The firmware has to be
proved on a board: on 10 November 2026 its LoRa bandwidth was halved to
125 kHz, because the 250 kHz it used was not going to pass T1 (see "What the
design predicts"), and that change has only been through host tests. The
factory test build has to be proved the same way: its radio commands are
covered by host tests and it builds for the ESP32-S3, but it has never keyed
a real transmitter. And the 868 MHz antenna match has to be tuned on a VNA,
with the steps in `hardware-design/CLAUDE.md`.

## The test firmware

Normal traffic never holds the transmitter on, and most radio measurements
need it held or need a steady run of identical packets. Build the test
firmware from the repo root:

```bash
source ~/export-esp.sh
cargo +esp build --features embedded,factory-test --release -Zbuild-std=core,alloc
```

Open the board's debug serial port (the second of its two USB serial ports)
and type one character. `c` holds an unmodulated carrier. `m` holds
continuous LoRa modulation. `p` sends a 64-byte test packet, waits a second
and sends the next, counting them on the port. `s` stops and returns to normal
operation. All three signals use the configured frequency and +22 dBm. The
same build advertises over Bluetooth every 20 ms, the minimum, for T5.

The test packet carries the 511-bit pseudo-random sequence that EN 300 220-2
prefers as test data. A second board running any build prints
`LoRa RX: 64 bytes` on its debug port for each one it hears, which is how the
receiver tests count.

Firmware that ships is built without `factory-test` and has no such commands.
Record the commit of the test build in the test report, and never flash it to
a unit that will be sold.

## Decide which product you are testing

A declaration covers one product: this board, one firmware build, one
enclosure and the cables it ships with. The board can be two products.

As the Walkie Textie radio it runs the firmware in this repo, talks Bluetooth
to a phone and follows COMPLIANCE.md as written. Order the node population,
which fits R37 (marked ALWAYS ON), because that firmware never signals the
power timer and the timer would otherwise cut the 3.3 V rail for 50 ms at the
end of each 15-minute period.

As the soil sensor it wakes on the timer, reads the sensor over I2C, sends one
LoRa packet and powers off. That firmware does not exist yet, and it needs
the timed population. If it leaves Bluetooth off, T5 drops out and the
technical file says so. Its duty cycle is a few seconds an hour, so T3
becomes a one-line calculation.

Test the product you will sell. If you will sell both, the radio is the worse
case for emissions because it never sleeps, but the sensor adds a cable, so
neither set of results covers the other.

## What this board adds to the plan

COMPLIANCE.md was written for a radio with one cable and a linear regulator.
V3.1 has three ports that take a wire: the USB plug, the battery leads to a
two-AA holder and the I2C sensor cable. A cable radiates whatever the board
puts on it, and below 300 MHz the cables are longer than the board, so they
set the result. Every test below names its cables. Use the longest sensor
cable you will ship, and the holder with its real leads.

V3.1 also has a switching converter. The TPS631000 switches at about 2 MHz
(1.8 to 2.2 MHz in its datasheet) and its harmonics reach into the 30 to
230 MHz band, where the T6 limit is lowest: 40 dBuV/m at 3 m.

The board plugs straight into a USB socket with no cable of its own. In any
test with USB power the host is part of the setup. Use a power bank or a
phone. A mains charger brings its own emissions, and if you sell one in the
box its mains port enters the scope of the EMC standard.

Batteries change three things in the plan. T9 applies, because it is for
battery-powered equipment. The supply extremes in T1 and T2 become the
battery's range, which the brief gives as 2.0 to 3.6 V. And the safety
checklist (D3) was written for a radio powered at 5 V from a phone with no
battery in it. A build that runs from two AA cells has to add them to that
checklist: Q1 blocks a reversed cell, U4 blocks current from USB into the
cells (the brief's own test allows 5 uA), and neither the board nor the brief
has a fuse, so the checklist needs a line on what limits the current if the
supply is shorted.

## What the design predicts

`tools/build.py` works these figures out from the datasheets, the firmware's
radio settings and the board's own geometry. They are predictions, not
results. They show which tests have room, and what a healthy board should
read.

| Test | Prediction | Limit |
| --- | --- | --- |
| T1 occupied bandwidth | 125 to 129 kHz at SF10 and 131 to 133 kHz at SF7, modelled, with 58 kHz or more clear each side | 250 kHz, with both edges inside the sub-band at every temperature |
| T2 radiated power | 18.5 dBm ERP (70 mW) with the antenna matched as on Pulse's board; 22 dBm with a 2.15 dBi antenna | 27 dBm ERP |
| T4 harmonics | -43 dBm at 1739 and 2609 MHz: the module's -45 dBm through a 2.15 dBi antenna | -30 dBm |
| T6, converter | 30 dBuV/m at 230 MHz and 43 dBuV/m at 1 GHz from its larger switching loop (3.3 mm2) | 40 and 47 dBuV/m |
| T6, cables | Cannot be calculated. 2.5 uA of common-mode current on one cable reaches the limit from 30 to 230 MHz, 5.6 uA above | 40 and 47 dBuV/m |
| T7 emission masks | 23 dB under at SF10 and 14 dB under at SF7, both 200 kHz outside the sub-band; modelled | The band edge mask |
| T10 sensitivity | -132 dBm at SF10 in 125 kHz, from the module's datasheet | -60 dBm |
| T11 blocking | 90 dB at 2 MHz and 99 dB at 10 MHz above a signal near sensitivity, from the SX1262 datasheet | -69 dBm and -44 dBm with the wanted signal at -90 dBm |
| Discharge to the plug's shell | C25 reaches 6 V at 4 kV, 12 V at 8 kV and 22 V at 15 kV | The part's 50 V |

T1 was the one test expected to fail, and the board had nothing to do with
it. Until 10 November 2026 the firmware sent a 250 kHz LoRa signal in a
sub-band 250 kHz wide, and it lets the host pick any spreading factor from 7
to 12. The standard measures the occupied bandwidth at the widest setting and
wants its edges inside the sub-band after adding the oscillator's drift over
temperature. The model is an ideal LoRa signal read through the analyser
filter the standard specifies. At 250 kHz and SF11 it left 1.3 kHz each side
at best, which is 1.5 parts per million of the carrier, and at the widest
filter the standard allows it was already outside. At SF7 it was 6 kHz
outside on each side.

The firmware now uses 125 kHz, with SF10 as the default. SF10 at 125 kHz has
the symbol time and sensitivity of SF11 at 250 kHz and nine tenths of its bit
rate. The same model leaves 58 kHz or more each side at every spreading
factor. `check_rf.py` prints the figures on every build, and prints a RISK
line without failing the build if a later setting stops fitting. The change
has not been on a board, and a radio flashed before it cannot hear one
flashed after.

The converter figure is a ceiling. It takes the TPS631000's 3.35 A current
limit, edges of no duration and free space. The ground plane sits 0.1 mm under
that loop and cancels most of its field, so the board will read far lower.

T2 cannot fail high, because the transmitter makes 158 mW and the limit is
500 mW. A reading well below 18 dBm means the antenna match is off. Fix that
before going on, because the same mismatch changes T4.

The chip antenna costs range. Pulse measured 29 per cent efficiency at 868 MHz
on a 20 x 40 mm board, so about 46 mW of the 158 mW leaves the antenna. Two of
these boards have 143 dB of link budget between them at the firmware's SF10
and 125 kHz, where lossless antennas would give 154 dB. Pulse's datasheet says
its figures depend on the size of the ground plane. Its board is as wide as
the antenna's clearance, so it has ground behind the antenna only. This board
is 45 x 54 mm and has ground beside the clearance as well, which will move
both the tuning and the efficiency. Measure it.

## Before the chamber

Write the build down first, because the results only cover that build: the
silkscreen revision (`V3.1 2026-11`), which order the board came from and
that order's `BOM.csv`, the values fitted at L5, L6 and L7 after tuning, the
firmware commit, the enclosure, the battery type and the sensor cable length.

### Check the transmitter at J3

The board has a 50 ohm test port, which lets you measure the radio without
the antenna in the way. A board from the bench-test order is built for it:
R30, R31 and J3 are fitted, and L5 and L6, which join the matching node to
ground and to the antenna, are not. The bench tests further down use the same
board.

1. Connect J3 to the spectrum analyser through an attenuator. The standard
   asks for 20 dB. The transmitter makes +22 dBm (158 mW), so use 30 dB if
   your analyser's input stops at 0 dBm.
2. With the carrier unmodulated (`c`), read the frequency. With modulation on
   (`m`), read the occupied bandwidth. That is the room-temperature half of
   T1, and it does not depend on the antenna. Expect about 125 to 130 kHz. A
   reading near 250 kHz means the board has firmware from before the
   bandwidth changed.
3. Read the conducted power and the harmonics at 1739 MHz and 2609 MHz. The
   Wio-SX1262 datasheet gives -45 dBm or better above 1 GHz. The limit in T4
   is -30 dBm, so a healthy module has 15 dB in hand before the antenna.

Never transmit on a board from the antenna-test order. Its radio has no load.

### Look for trouble with a near-field probe

A probe on a small spectrum analyser cannot pass or fail the product. It can
find a noise source for the price of an afternoon, where a chamber day finds
only that one exists. Hold the probe over each of these with the board running
and compare with the board switched off:

- L2 and the two pads of U5 beside it, for the converter's 2 MHz and its
  harmonics.
- The sensor cable while the firmware is reading the sensor.
- The battery leads, with USB unplugged.
- The shell of the USB plug, with the board in a power bank.

Anything that stands well clear of the switched-off trace between 30 MHz and
1 GHz is worth understanding before T6.

### Measure the current on each cable

Below 230 MHz, T6 is mostly decided by common-mode current: current that flows
the same way on every wire of a cable. The layout cannot predict it, but a
clamp-on RF current probe and the spectrum analyser can measure it on the
bench, and this is the one bench reading that forecasts the chamber.

Clamp the probe round the whole cable, close to the board, with the board
running as it will in T6. Do the sensor cable and the battery leads in turn.
Subtract the probe's transfer impedance in dB ohms (from its datasheet) from
the analyser's reading in dBuV to get dBuA.

A cable long enough to resonate reaches the 40 dBuV/m limit with 8 dBuA
(2.5 uA) on it between 30 and 230 MHz, and the 47 dBuV/m limit with 15 dBuA
(5.6 uA) above that. A quarter wave is 2.5 m at 30 MHz and 33 cm at 230 MHz,
and a shorter cable radiates less, so these figures err on the safe side.
Leave a few dB in hand all the same.

The readings are small. Through a probe of 1 ohm transfer impedance, 8 dBuA is
8 dBuV, which is -99 dBm. Use a narrow resolution bandwidth and a
preamplifier, and save a trace with the board switched off first.

With the board in a power bank there is no cable to clamp, since the bank
itself is the other half of the antenna. That case waits for the chamber.

## The chamber tests on this board

The method, limits and pass marks for each test are in COMPLIANCE.md. This
table is what to set up on V3.1.

| Test | Board state | Power and cables | On this board |
| --- | --- | --- | --- |
| T2 LoRa radiated power | Modulated transmit at +22 dBm (`m`) | Batteries in the holder, sensor cable attached, no USB | The antenna is at the corner by the LoRa module. Keep the holder and cable where the enclosure puts them |
| T4 LoRa spurious | As T2, then idle | As T2 | Watch 1739 and 2609 MHz |
| T5 Bluetooth | Advertising | Batteries | Only if the product's firmware uses Bluetooth |
| T6 EMC emissions | The product doing its job | Twice: batteries with the sensor cable, then in a power bank with the sensor cable | Watch 30 to 230 MHz for the converter and the sensor cable |
| T8 transient power | Test packets (`p`) | As T2 | Same position as T2's strongest reading |
| T10 sensitivity | Normal firmware, listening | As T2 | A second board in `p`, outside the chamber, feeds the measurement antenna through attenuators |

T3 needs no chamber. T1, T7, T9, T11 and the dynamic range half of T10 are
bench tests at J3, in the next section.

For T6 as the soil sensor, the job is one wake, read and transmit every
15 minutes, which gives the analyser almost nothing to hold. Run a test build
that repeats the cycle without sleeping, on a board from the node order,
whose R37 keeps the power on, and say so in the report.

EN 301 489-1 applies its conducted emission tests to mains ports and to DC
ports with long cables. This board has neither, as long as the sensor cable and
battery leads you ship stay under 3 m. Check that against clause 8 of the
version you cite.

For the immunity assessment (D2 in the plan), the metal a user can touch is
the USB plug's shell, the sensor connector and the three buttons. The shell
goes to ground through 1 megohm and 100 nF (R10 and C25). The capacitor takes
the charge of a discharge to the shell and rises to 6 V at the 4 kV contact
level and 12 V at the 8 kV air level, against its 50 V rating. The USB lines
have D1 to D3 and the I2C lines have U12. If you can borrow an ESD gun, those
are the points to hit.

A discharge that pulls the 3.3 V rail under 2.93 V makes U13 reset the ESP32,
which starts again 200 ms after the rail recovers. Write down every reset you
see. Whether one is allowed during the test depends on the performance
criteria in the version of EN 301 489 you cite.

Plugging USB in or pulling it out while the board runs from its battery can
do the same. The power mux disconnects both supplies for some microseconds as
it changes over, and three 22 uF capacitors feed the converter alone. With
both radios transmitting from a battery under about 2.3 V, the model's worst
case lets the converter stop, which takes the rail under 2.93 V. It is not
part of any test in the plan, but note it if a test has you change the supply
while the board runs.

## The bench tests at J3

Five of the plan's tests are conducted measurements, which the standard allows
at a temporary antenna connector. On V3.1 that is J3, on a board from the
bench-test order. It differs from the chamber board in nothing but the
connector, its link and the two matching parts that are left off.

| Test | Board state | What connects to J3 |
| --- | --- | --- |
| T1 occupied bandwidth and frequency stability | `c`, then `m` | Analyser through 20 dB. Repeat `c` in the temperature chamber |
| T7 emission masks | `m` | Analyser through 20 dB |
| T9 as the battery runs down | `p` | Analyser through 20 dB |
| T10 dynamic range | Normal firmware, listening | A second radio in `p` through attenuators |
| T11 blocking and spurious responses | Normal firmware, listening | A second radio in `p` through attenuators, and the signal generator, through a combiner |

J3 is a test port and not a calibrated one. R31 and the stub to L5 and L6's
pads are in the path, so read levels at the far end of the cable with the
analyser before each receiver test, as T11 says.

For the supply extremes in T1, and for T9, put a bench supply on the battery
connector in place of the cells, with USB unplugged. The bench-test board has
R37 fitted, so it stays on. Connect the supply before switching it on: one
that is already on rings with its leads when it is connected, and the mux
allows 6 V. The brief gives the battery range as 2.0 to 3.6 V. For T9 start
at 3.0 V and come down 0.3 V at a time. The mux is specified down to 1.6 V.
The TPS631000 holds 3.3 V until its input falls below its lockout, 1.4 to
1.5 V, and then stops, so expect the radio to send at full
power to somewhere under 2 V at the connector and then go silent. What the
radio does in the moment the rail collapses is the thing to look at. U13 puts
the ESP32 in reset once the rail is under 2.93 V, so no new packet starts
below that, but a packet already on air carries on until the module's own
supply fails.

The module maker's report may spare you some of this. Ask Seeed for the
Wio-SX1262's RED test report and see which clauses it covers, at which
bandwidth and power. A result measured at another bandwidth or spreading
factor does not stand for the one this firmware sends.

## If a test fails

The board has room for the usual fixes without a new layout.

- A LoRa harmonic is over the limit. L5, L6 and L7 are 0603 pads that take
  capacitors as well as inductors. A low-pass filter (capacitor to ground,
  inductor in series, capacitor to ground) fits the same three pads. Re-tune
  the match on the VNA afterwards and repeat T2 as well as T4.
- An emission follows the sensor cable: it moves when you move the cable, or
  goes away when you unplug it. R33 and R34 are 100 ohms in the two I2C lines.
  220 ohms raises a low level by 0.07 V against the sensor's own 10 kilohm
  pull-ups, and by 0.15 V if the board's unfitted 4.7 kilohm pull-ups (R18
  and R19) are added. A 3.3 V input reads anything under 0.99 V as low. The
  firmware can also lower the
  drive strength of GPIO1 and GPIO2 and run the bus at 100 kHz. A clip-on
  ferrite on the cable is the last resort, because it becomes part of the
  product.
- An emission follows the battery leads and sits at multiples of 2 MHz. That
  is the converter. Twist the leads and keep them short first. Then check C1
  and C26 are the 22 uF and 47 uF parts in the BOM, which is what TI's
  datasheet sizes them at for this converter.
- Narrow peaks at multiples of 40 MHz come from the ESP32 module's crystal.
  The module is pre-tested, so look at what changed around it: the enclosure,
  or a cable routed across the module.
- A discharge leaves the board in the ESP32's download mode, so it does not
  come back without a power cycle. The BOOT line was low when the chip
  restarted. C5's pads are on that line and unfitted: 100 nF there holds it
  up.

Any change to a part, the firmware's radio settings, the enclosure or a cable
means deciding which tests to repeat, and writing down why.

## Standards and versions

COMPLIANCE.md's radio tests are written from EN 300 220-2 V3.3.1 of March
2025, which
[ETSI publishes free](https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/03.03.01_60/en_30022002v030301p.pdf).
It names the other standards without versions. Take every version from the
consolidated list on the
[designated standards page](https://www.gov.uk/government/publications/designated-standards-radio-equipment)
on the day you sign the declaration. On 10 November 2026 that page was last
updated on 3 November 2026 and its consolidated list was version 11. The
notices behind it name EN 300 220-2 V3.3.1 (notice 0130/26), EN 300 328
V2.2.2 (0122/25), and EN 301 489-3 V2.3.2 and EN 301 489-17 V3.3.1 (0119/25).
Several entries carry restrictions, so read that column too.

V3.3.1 asks for more than the 2018 version did. It makes the mask at the band
edges a requirement of its own, applies three more receiver tests to a product
like this (sensitivity, dynamic range and spurious response rejection), and
carries its own test methods. A test report or a module report written
against V3.2.1 does not cover it.

One rule sits outside CE marking. The Product Security and
Telecommunications Infrastructure Act 2022 has applied to consumer connectable
products since 29 April 2024, and the radio is in scope: it holds Bluetooth to
a phone and LoRa to other radios at once, which is the case
[section 5](https://www.legislation.gov.uk/ukpga/2022/46/section/5) describes,
and no exception fits. COMPLIANCE.md now has a section on what that requires:
a published security contact, a published support period and a statement of
compliance with each unit. None of it needs a test.

## What this folder gives the technical file

`fab/schematic.pdf`, `fab/assembly.pdf`, the Gerbers and the `BOM.csv` of the
order that was tested are the design record. `datasheets/` has the antenna datasheet with its gain figure.
The output of `tools/build.py` is the evidence that the design was checked:
ERC, DRC against the schematic, the firmware's pins against the board, every
placed part against JLCPCB's own footprint, the fabrication files themselves,
and the predicted figures in the table above. Keep a copy of that output with
the build it came from.
