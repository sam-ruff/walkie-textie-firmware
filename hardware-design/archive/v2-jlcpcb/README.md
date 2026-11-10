# Walkie Textie rev 2 - JLCPCB order package

Everything JLCPCB needs, in the shape their upload flow expects. Built from
`../v2-production/`, which is what the designer delivered. Nothing here is
edited artwork: the Gerbers and drill files are his bytes, unchanged.

## What to upload where

| Step | File |
| --- | --- |
| PCB order, "Add gerber file" | `walkie-textie-rev2-gerbers.zip` |
| Assembly, BOM file | `bom.csv` |
| Assembly, CPL file | `cpl.csv` |

`gerbers/` is the unzipped copy of the same 14 files, for inspection.
`reference/` holds the schematic PDF, generated from the KiCad source with
`kicad-cli` because the designer never supplied one.

## Order settings, as selected

Uploading the zip auto-detects 4 layers and 30 x 40 mm, both correct. Only
four things then need changing from JLCPCB's defaults, marked **CHANGE**
below. Everything else is listed so the order can be reproduced exactly.

### PCB

| Setting | Value | Note |
| --- | --- | --- |
| Base Material | FR-4 | default |
| Layers | 4 | auto-detected |
| Dimensions | 30 x 40 mm | auto-detected. Correct: the 0.4 mm notch overshoot is trimmed by CAM |
| PCB Qty | 5 | |
| Product Type | Industrial/Consumer electronics | default |
| Deburring/Edge rounding | Yes | harmless, already on |
| Different Design | 1 | |
| Delivery Format | Single PCB | |
| PCB Thickness | 1.6 mm | design stackup totals 1.5842 mm |
| PCB Color | Green | cheapest and quickest |
| Silkscreen | White | |
| Material Type | FR4 TG135 | adequate for a single reflow |
| Surface Finish | **ENIG — CHANGE from HASL(with lead)** | fine-pitch module lands and the RF feed. HASL's uneven surface is poor for both |

### High-spec options

| Setting | Value | Note |
| --- | --- | --- |
| Outer Copper Weight | 1 oz | matches the 0.035 mm in the stackup |
| Inner Copper Weight | 0.5 oz | matches the 0.0152 mm in the stackup |
| Specify Layer Sequence | No | the file names are unambiguous |
| Specify Stackup | **Yes, then JLC04161H-3313 — CHANGE from No** | the RF feed is sized for this stackup's 0.0994 mm prepreg. JLCPCB's default 4-layer 1.6 mm build is the 7628 stackup with roughly double that, which puts the feed off 50 ohms |
| Via Covering | Plugged | default. The 0.15 mm vias are GND stitching in open copper, not in pads, so no resin fill is needed. "Tented" is greyed out and means the same thing here |
| Via Plating Method | Not Specified | default |
| Min via hole size | **0.15mm/(0.25/0.3mm) — CHANGE from 0.3mm** | 35 vias are drilled 0.15 mm with 0.3 mm pads. Any larger selection contradicts the drill file |
| Board Outline Tolerance | ±0.2 mm (Regular) | Precision is greyed out, and there is no enclosure yet |
| Confirm Production file | **Yes — CHANGE from No** | this package was delivered wrong once already |
| Mark on PCB | Remove Mark | default |
| Electrical Test | Flying Probe Fully Test | default |
| Gold Fingers, Castellated Holes, Press-Fit, Edge Plating, Blind Slots, UL Marking, Backdrill, Humidity Indicator | No | none apply |
| PCB Remark | leave empty | nothing needs explaining to CAM |

### Assembly

| Setting | Value | Note |
| --- | --- | --- |
| Side | Assemble top side | all 27 placed parts are top side |
| PCBA Type | Economic | nothing here needs the Standard process |
| Assembly Side | Top Side | |
| PCBA Qty | 5 | matches the PCB quantity |
| Tooling holes | Added by JLCPCB | they go in the rails, not the board |
| Confirm Parts Placement | **Yes — CHANGE from No** | the single most useful option on this page. JLCPCB's library orientations differ from KiCad's, and this is the check that catches a reversed D1, C4, J1, U1, U2, U5 or U6 before 5 boards are built wrong |
| Stencil Storage / Fixture Storage | No | only pays off on repeat orders |
| Parts Selection | By Customer (Self-Service) | the BOM carries LCSC numbers. This step is where U5's stock shows up |
| Solder Paste | High temp. | standard lead-free SAC. Keep it: leaded solder would compromise the RoHS position for a product intended for sale |
| Nitrogen reflow soldering | Yes (for Economic) | better wetting, included |
| Bake Components, Board Cleaning, Special stencil, Depanel, Flying Probe Test, Function test, Conformal Coating, Assembly remark | No | none apply to a 5-board prototype run |
| Photo Confirmation | Yes | photos of the assembled boards before they ship |
| Packaging | Antistatic bubble film | default |
| Stencil (separate section) | off | not needed when JLCPCB assembles |

## Not assembled by JLCPCB

Three designators are absent from both `bom.csv` and `cpl.csv`, which is how
JLCPCB expects a part to be left off. Two are design intent, one is sourcing.

**C11 and C12** are the pi network's shunt capacitors and are deliberately left
empty. They are the tuning point: their values are unknown until the antenna
match is measured with a VNA at bring-up.

Since no hand soldering is planned, be aware of what that means. Measure the
match first; with R9 fitted as a 0R link the antenna is connected and the board
works, and the match may well be good enough to leave both shunts empty. If it
is not, fitting two 0603 capacitors is a few minutes' work for any local
electronics repair shop, or the values can be rolled into the next JLCPCB batch
once they are known. Nothing needs deciding before the boards arrive.

**U5, the Wio-SX1262, has no JLCPCB part.** Their matcher returns "No Part
Selected" and offers Pre-order. The complication is that the board feeds the
antenna from the module's SMT ANT pad, and the IPEX-only variant leaves that
pad unconnected, so which variant arrives is a certification question rather
than a preference. Seeed SKU 113991436 is the "without IPEX" version that is
needed.

**JLCPCB confirmed on 21 August 2026 that C55348741 is the IPEX variant**, and
recommended consignment instead. Pre-ordering their catalogue part would have
produced five boards with the antenna pad unconnected. Their pre-order lead
time was quoted as 8 to 15 days, which is now moot.

The route is therefore consignment:

**Try Global Sourcing before consignment.** JLCPCB's "Request Sourcing"
service buys parts they do not stock from global distributors, quoted at 9 to
15 days, with no shipping, customs or paperwork at your end. Their chat agent
went straight to consignment without mentioning it.
https://jlcpcb.com/user-center/smtPrivateLibrary/orderParts/?global=1

Searched on 22 August 2026 by Seeed SKU `113991436` and by manufacturer part
number `Wio-SX1262-N`. **Both return nothing**, and the -N variant has no LCSC
or JLCPCB part number anywhere, which is why their agent said the component
team has to review it. Global Sourcing is therefore not a shortcut, but the
new part request is still the right next click, because it does double duty:
it asks them to source the part, and it creates the part number that
consignment requires.

Use "submit a new part request" on that page. The form takes a manufacturer
part number, one distributor chosen from a fixed list, a purchase link from
that distributor, the distributor's own part number, manufacturer and
quantity. There is no free-text field.

| Field | Value |
| --- | --- |
| MFR.Part # | `113991436` |
| Distributor | Digikey |
| Purchase link | https://www.digikey.com/en/products/detail/seeed-technology-co-ltd/113991436/26834461 |
| Digikey Part # | `1597-113991436-ND` |
| Manufacturer | Seeed Technology Co., Ltd |
| Required Qty | 7 |

The part number is `113991436`, **not** `Wio-SX1262-N`. Seeed use their shop
SKU as the manufacturer part number and DigiKey lists it that way, which is
why searching either the SKU or the -N designator on the sourcing page found
nothing. The purchase link also pins the exact variant, so the IPEX ambiguity
is settled by construction; there is no notes field, so tell the chat agent
separately that it must not be mapped onto C55348741.

**Submitted 22 August 2026.** Quote comes back by email in 2 to 3 business
days, with price and lead time. Track it on the "Part Request History" tab.
When it lands, the decision is that quoted lead time against buying from Seeed
and consigning; take global sourcing unless the lead time is unacceptable,
because it removes the shipping, customs and registration work entirely.

Sourcing checked 22 August 2026:

| Source | Price | Stock | Note |
| --- | --- | --- | --- |
| Seeed direct | 4.29 USD | in stock | not on the distributor list, so consignment only |
| DigiKey 1597-113991436-ND | 5.99 USD | non-stock, 4 week factory lead | on the list, link confirmed |
| Mouser | unknown | unknown | site blocks automated lookup, check by hand to compare |

RS, Farnell and Arrow do not appear to carry it; Seeed's catalogue
distribution is essentially DigiKey and Mouser. DigiKey being non-stock with a
four week lead is the thing to weigh against consignment, so wait for the
quote before committing either way.

### Consignment, if Global Sourcing cannot get it

The page is **Consign Components**, at
https://jlcpcb.com/user-center/smtPrivateLibrary/consignParts (sign in first;
also reachable from https://jlcpcb.com/parts or Account > Parts Manager).

There is a prerequisite that is easy to miss: **only parts that already have a
JLCPCB part number can be consigned, and new ones need their engineering team
to approve a submission.** C55348741 is the IPEX variant, so the -N variant
probably has no number yet. That approval is what the chat agent meant by
"make a registration for the part, then wait for our component team to
review", and it is step one, before any money is spent.

Registration then asks for shipment origin (inside or outside Mainland China;
getting this wrong means the shipment is rejected at your cost), then unit
selling price, manufacturer, goods description, application, country of
origin, unit weight and HS code, with an invoice uploaded to substantiate the
price, and acceptance of the Components Sale and Purchase Agreement. Values to
use:

   | Field | Value |
   | --- | --- |
   | Manufacturer | Seeed Technology Co., Ltd |
   | Description | Wio-SX1262-N LoRa transceiver module, SX1262, 12-pin SMT, 11.5 x 11 x 3 mm |
   | Application | component for our own PCBA order |
   | Country of origin | China |
   | Unit selling price | as actually paid, 4.29 USD at list |
   | Unit weight | weigh one; a shielded module this size is well under a gram |
   | HS code | 8517.62.00 is the usual code for radio transceiver modules, but follow whatever Seeed's invoice states |

2. Buy **Seeed SKU 113991436**, the Wio-SX1262 **without** IPEX, 4.29 USD,
   https://www.seeedstudio.com/Wio-SX1262-Wireless-Module-without-IPEX-Tape-Reel-p-6417.html
   Buy 7 for a five-board run: JLCPCB will not guarantee a build if consigned
   quantity runs short, and they do not test consigned parts on arrival.
   Keep the invoice, it is the price substantiation.
3. Wait for the price review, which they quote at two business days against
   third-party market data. Approved moves the registration to "Awaiting
   Payment"; rejected sends a "Confirm Price" notice to adjust and resubmit.
4. Pay. For an overseas origin that is import duty (declared value x duty
   rate) plus import VAT at 13% of value-plus-duty, both refundable deposits
   returned once the parts are consumed in a PCBA order, plus a
   non-refundable handling fee of 2% with a 10 USD minimum. Their consignment
   notes add a customs clearance charge of roughly 45 USD under 5000 CNY.
   Shipping from Seeed inside Mainland China avoids most of this, which is why
   the origin choice matters more than anything else here.
5. Ship only after they approve dispatch, entering courier and tracking in
   their system. The destination depends on origin: overseas goes to their
   Hong Kong warehouse, Mainland China goes to their SMT warehouse in Zhuhai,
   Guangdong. The form gives the correct address once origin is chosen, so do
   not copy an address out of a help article. Their guidance is to use DHL,
   UPS or FedEx on DDP terms and to avoid EMS and China Post, which do not
   notify them of customs problems. Label the shipment to the named recipient
   with your customer account ID, and make the commercial invoice match the
   declared value exactly.
6. They verify quantity on arrival and query any discrepancy. Parts then sit
   in My Parts Lib free for up to three years. Getting them back out again
   costs 30% with a 30 USD minimum and seven days' notice, so consign only
   what will be used.
7. Place the PCBA order. Matching prefers consignment stock automatically; if
   U5 does not auto-match, search it by MFR part number and confirm the
   selection, since only selected parts get assembled.

Routing the parts via the UK would attract UK import VAT inbound and then
JLCPCB's duty, VAT deposit, handling and clearance outbound, which on a 30 USD
order costs several times the parts. Ship Seeed to JLCPCB directly.

Ask the chat agent to confirm one thing while registering: the Consign Parts
listing for this module (C9900174795, JLCPCB Assembly) showed **Min: 442**. If
that is a real minimum consignment quantity rather than an artefact of their
handling-fee line, consigning 7 pieces is not possible and the plan needs
rethinking.

MSL 3 needs no action; JLCPCB bakes moisture-sensitive parts as part of their
normal flow, so leave "Bake Components" on No. They asked for a screenshot of
the "Assembly Type: Wave Soldering" line before commenting on it; that
question is unresolved and only matters for cost, not feasibility.

Because the schedule now waits on the module either way, **consider ordering
the five bare PCBs immediately** with the settings above and no assembly. They
are cheap next to the assembly run, they cost no extra time, and they let the
board outline, the USB-C notch and the overall dimensions be checked in the
hand before committing to a populated build. Given this package arrived wrong
once already, that is worth doing.

Do not pre-order an unconfirmed variant. An IPEX module leaves the antenna
unconnected and invalidates the certification route the whole design rests on.

**R9 is not DNP and must be fitted.** It is the series element of the same pi
network, so with R9 missing the antenna is disconnected from the radio
entirely. The designer's message described "DNP caps and resistor", but the
board makes R9 the series link and his own BOM includes it. Fitting the 0R is
correct.

## Changes made to the designer's BOM

His `MESHTASTIC NODE_LCSC.xlsx` was already in JLCPCB's column format. These
things were changed on the way into `bom.csv`, all of them reversible:

- **U1 re-sourced.** His C2827693 (TECH PUBLIC USBLC6-2P6) showed zero stock in
  JLCPCB's parts matcher. Replaced with **C5199178**, an ElecSuper
  USBLC6-2P6-ES in the same SOT-563 package with the same pinout, listed by
  JLCPCB as supported on both Economic and Standard assembly. **C22390016**
  (DOWO USBLC6-2P6, also SOT-563) is the fallback if that one is dry too. Note
  ST's own USBLC6-2P6 (C15999) is SOT-666, not SOT-563, so do not substitute it
  without checking the land pattern. U1 is the USB ESD protection device, which
  feeds into the EN 301 489 immunity desk assessment, so record which part
  actually goes on.

- **C10 part number corrected.** He gave C10 (1 uF) the part number C14663,
  which is the same number used for the 100 nF line, and C14663 is a Yageo
  100 nF X7R 0603. Left alone, C10 would have been fitted with 100 nF. It is
  now C15849, a Samsung 1 uF 50V X5R 0603. C10 sets the ESP32 EN reset delay
  with R7, so the wrong value shortens the power-on reset by a factor of ten.
- **"120惟" changed to "120 Ohm"** on L1. The original was a mis-encoded ohm
  sign that will not survive a CSV round trip.
- **Trailing space stripped** from R2's part number.

## Check these at upload, before paying

- **U5, the Wio-SX1262 (C55348741), showed out of stock at LCSC** when this
  package was built. If JLCPCB cannot source it the assembly order stalls, and
  the alternative is consigning the part.
- **Confirm U5 is the variant without the IPEX connector.** The LCSC listing
  does not say. The board feeds the antenna from the module's SMT ANT pad, and
  the IPEX-only variant leaves that pad unconnected, which would leave the
  radio with no antenna path and invalidate the certification route. See
  `COMPLIANCE.md` in the app repo.
- **Check part rotations in JLCPCB's preview.** Rotations here are KiCad's.
  JLCPCB's library orientation differs for some parts, and the ones to look at
  are the polarised or keyed parts: D1, C4, J1, U1, U2, U5, U6.
- Some of these are extended parts and carry a per-part setup fee.
- **J1 has two through-hole mounting slots** (the only non-SMD features on the
  board; the drill file's 0.5 mm tool is just those two routed slots). They are
  mechanical anchors on an otherwise surface-mount connector, so reflow handles
  it, but if JLCPCB's Economic process objects to the connector this is why,
  and switching to Standard PCBA is the fix.

## Known issues in the design, none of which block this order

Full detail in `PCB_DESIGN_NOTES.md` in the app repo. Carried here because
they are worth having in front of you when the boards arrive:

- The board is 4-layer and 30.5 x 40.1 mm. The brief asked for 2-layer 1.6 mm
  at the smallest practical size. Neither was done and neither has been put to
  the designer.
- The board is not DRC clean, which was a stated deliverable, but nothing in
  the 124 violations is dangerous. 70 are the 0.15 mm vias breaching the
  project's own stricter drill and annular rules, 44 are footprint and
  silkscreen cosmetics, five are sub-rule clearances on the RF feed that are
  still well inside fab capability, and the rest are a stray track fragment
  and copper islands. No pad is unconnected anywhere on the board.
- The two `invalid_outline` errors are a false alarm. The board is 30 x 40
  with 3 mm corner radii and a connector notch cut into the right edge from
  x = 26.79 across y = 15.8 to 24.2, for J1 to recess into. The notch edges
  overshoot the board edge by 0.4 mm on purpose, so the router breaks through
  cleanly, and KiCad calls the dangling ends unclosed. JLCPCB's CAM read the
  board as 30 x 40, which confirms it trimmed the overshoot correctly. No
  remark needed and nothing to fix.
- USB-C CC2 has no 5.1K pull-down, only CC1 does, so a C-to-C cable powers the
  board in one orientation only.
- There is no U.FL test point in the RF path, so tuning the pi network means
  soldering a coax pigtail to the feed.
- RF_SW1 on the LoRa module sits on GPIO38, which the firmware did not drive
  when this board was ordered. Since 10 November 2026 it drives the pin high
  to receive and low to transmit and to idle, as Seeed's datasheet asks.
